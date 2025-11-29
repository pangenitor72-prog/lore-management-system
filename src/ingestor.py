import asyncio
import os
import json
import re
import google.generativeai as genai
from typing import List, Dict, Any
from .neo4j_adapter import Neo4jDatabase
from .audit_log import AuditLogger

class LoreIngestor:
    """
    Handles parsing, AI extraction, and graph ingestion of lore files.
    """
    
    # Configuration constants
    MAX_CHUNK_SIZE = 4000
    CHUNK_OVERLAP = 200
    
    EXTRACTION_PROMPT = """You are a Knowledge Graph Extractor for a D&D Campaign.
Analyze the following text and extract entities and relationships.

**Entities to Extract (Labels):**
- Character (NPCs, PCs, villains)
- Location (Places, regions, buildings)
- Item (Weapons, artifacts, objects)
- Faction (Organizations, groups, cults)
- Event (Battles, ceremonies, historical moments)
- Concept (Abstract ideas, magic types, prophecies, curses)

**Output Format:**
Return ONLY a valid JSON object with two keys: "nodes" and "relationships".
Do NOT include markdown code fences or any other text.

Example:
{"nodes": [{"id": "Kael", "label": "Character", "properties": {"class": "Paladin", "description": "A sworn protector"}}, {"id": "Void Corruption", "label": "Concept", "properties": {"type": "Curse"}}], "relationships": [{"source": "Kael", "target": "Void Corruption", "type": "VULNERABLE_TO"}]}

**Rules:**
1. Use consistent, simple IDs (e.g., "Kael" not "Kael the Paladin").
2. Always include a "description" in properties when possible.
3. Extract relationship types like: LOCATED_IN, MEMBER_OF, OWNS, CREATED, DEFEATED, ALLIED_WITH, ENEMY_OF, KNOWS, WIELDS, etc.
4. If no entities found, return: {"nodes": [], "relationships": []}
5. CRITICAL: Return ONLY valid JSON. No markdown, no explanations."""

    def __init__(self, neo4j_driver, api_key: str):
        """
        Initialize the ingestor with a Neo4j driver and Gemini API key.
        """
        self.driver = neo4j_driver
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')

    def chunk_text(self, text: str) -> List[str]:
        """Split large text into overlapping chunks."""
        if len(text) <= self.MAX_CHUNK_SIZE:
            return [text]
        
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.MAX_CHUNK_SIZE
            if end < len(text):
                # Try to break at paragraph or sentence
                para_break = text.rfind('\n\n', start, end)
                if para_break > start + self.MAX_CHUNK_SIZE // 2:
                    end = para_break
                else:
                    sentence_break = text.rfind('. ', start, end)
                    if sentence_break > start + self.MAX_CHUNK_SIZE // 2:
                        end = sentence_break + 1
            
            chunks.append(text[start:end].strip())
            start = end - self.CHUNK_OVERLAP if end < len(text) else end
        
        return chunks

    def parse_json_response(self, text: str) -> Dict[str, Any]:
        """Parse JSON from AI response with robust error recovery."""
        cleaned = text.strip()
        cleaned = re.sub(r'^```json\s*', '', cleaned)
        cleaned = re.sub(r'^```\s*', '', cleaned)
        cleaned = re.sub(r'\s*```$', '', cleaned)
        cleaned = cleaned.strip()
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        
        # Regex fallback
        match = re.search(r'\{[\s\S]*\}', cleaned)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        
        # Fallback for trailing commas
        fixed = re.sub(r',(\s*[}\]])', r'\1', cleaned)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass
            
        return {"nodes": [], "relationships": []}

    def merge_extractions(self, extractions: List[Dict]) -> Dict[str, Any]:
        """Merge multiple chunk extractions."""
        all_nodes = {}
        all_rels = []
        
        for data in extractions:
            if not data: continue
            
            for node in data.get("nodes", []):
                node_id = node.get("id", "")
                if node_id:
                    if node_id not in all_nodes:
                        all_nodes[node_id] = node
                    else:
                        # Merge properties
                        all_nodes[node_id]["properties"].update(node.get("properties", {}))
            
            all_rels.extend(data.get("relationships", []))
        
        return {
            "nodes": list(all_nodes.values()),
            "relationships": all_rels
        }

    def process_file_content(self, filename: str, content: str) -> Dict[str, Any]:
        """
        Process file content: Chunk -> Extract -> Return Data (does not save yet).
        Useful for UI preview.
        """
        chunks = self.chunk_text(content)
        extractions = []
        errors = []
        
        for i, chunk in enumerate(chunks):
            try:
                response = self.model.generate_content(
                    self.EXTRACTION_PROMPT + "\n\nTEXT:\n" + chunk,
                    generation_config={"temperature": 0.1}
                )
                data = self.parse_json_response(response.text)
                extractions.append(data)
            except Exception as e:
                errors.append(f"Chunk {i+1} failed: {str(e)}")
        
        merged_data = self.merge_extractions(extractions)
        return {
            "filename": filename,
            "data": merged_data,
            "chunks_count": len(chunks),
            "errors": errors
        }

    def save_to_neo4j(self, data: Dict[str, Any], filename: str) -> Dict[str, int]:
        """
        Save extracted data to Neo4j using the provided driver.
        Returns counts of saved nodes and relationships.
        """
        nodes = data.get("nodes", [])
        rels = data.get("relationships", [])
        nodes_saved = 0
        rels_saved = 0
        
        # 1. Save Nodes
        for node in nodes:
            node_id = node.get("id", "")
            label = node.get("label", "Entity")
            props = node.get("properties", {})
            
            if node_id:
                # Sanitize label
                safe_label = re.sub(r'[^a-zA-Z0-9_]', '', label) or "Entity"
                
                query = f"""
                MERGE (n:`{safe_label}` {{name: $name}})
                SET n += $props
                SET n:Entity
                RETURN n.name
                """
                try:
                    with self.driver.session() as session:
                        session.run(query, {"name": node_id, "props": props})
                    nodes_saved += 1
                except Exception as e:
                    print(f"Error saving node {node_id}: {e}")

        # 2. Save Relationships
        for rel in rels:
            source = rel.get("source")
            target = rel.get("target")
            rel_type = rel.get("type", "RELATED_TO").upper().replace(" ", "_")
            rel_type = re.sub(r'[^a-zA-Z0-9_]', '_', rel_type)
            
            if source and target:
                query = f"""
                MATCH (a {{name: $source}})
                MATCH (b {{name: $target}})
                MERGE (a)-[r:`{rel_type}`]->(b)
                """
                try:
                    with self.driver.session() as session:
                        session.run(query, {"source": source, "target": target})
                    rels_saved += 1
                except Exception as e:
                     print(f"Error saving rel {source}->{target}: {e}")

        # 3. Link File Source
        try:
            with self.driver.session() as session:
                session.run("MERGE (f:File {name: $filename})", {"filename": filename})
        except:
            pass

        return {"nodes_saved": nodes_saved, "rels_saved": rels_saved}
