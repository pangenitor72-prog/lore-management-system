import asyncio
import os
import json
import re
import logging
from typing import List, Dict, Any, Optional
import google.generativeai as genai
from .embedding_service import EmbeddingService
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

    def __init__(self, neo4j_driver, api_key: str, enable_embeddings: bool = True):
        """
        Initialize the ingestor with a Neo4j driver and Gemini API key.
        """
        self.driver = neo4j_driver
        self.api_key = api_key
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        self.enable_embeddings = enable_embeddings
        self.embedding_service = EmbeddingService(api_key) if enable_embeddings else None

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

    async def _extract_chunk(self, chunk: str, index: int) -> Dict[str, Any]:
        """
        Extract entities from a single chunk using Gemini in an executor.
        """
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: self.model.generate_content(
                    self.EXTRACTION_PROMPT + "\n\nTEXT:\n" + chunk,
                    generation_config={"temperature": 0.1}
                )
            )
            return self.parse_json_response(response.text)
        except Exception as e:
            await AuditLogger.log(f"Chunk {index+1} extraction failed: {str(e)}", level=logging.ERROR)
            return {"nodes": [], "relationships": []}

    async def _generate_node_embedding(self, node: Dict) -> Optional[List[float]]:
        """
        Generate embedding for a node based on its content.
        Combines node ID, description, and content into embedding text.
        """
        if not self.enable_embeddings or not self.embedding_service:
            return None

        node_id = node.get("id", "")
        props = node.get("properties", {})
        description = props.get("description", "")
        content = props.get("content", "")

        # Construct text for embedding
        embedding_text = f"ID: {node_id}\nDescription: {description}\nContent: {content}"
        
        loop = asyncio.get_event_loop()
        try:
            # EmbeddingService.embed_text is synchronous, run in executor
            embedding = await loop.run_in_executor(
                None,
                lambda: self.embedding_service.embed_text(embedding_text)
            )
            return embedding
        except Exception as e:
            await AuditLogger.log(f"Embedding generation failed for node {node_id}: {str(e)}", level=logging.ERROR)
            return None

    async def process_file_content(self, filename: str, content: str) -> Dict[str, Any]:
        """
        Process file content: Chunk -> Extract -> Return Data (does not save yet).
        Useful for UI preview.
        """
        chunks = self.chunk_text(content)
        
        # Concurrent extraction
        tasks = [self._extract_chunk(chunk, i) for i, chunk in enumerate(chunks)]
        extractions = await asyncio.gather(*tasks)
        
        # Check for empty results which might indicate errors (already logged in _extract_chunk)
        errors = [] # We rely on AuditLogger for details now, but keep list for return compatibility if needed
        
        merged_data = self.merge_extractions(extractions)
        return {
            "filename": filename,
            "data": merged_data,
            "chunks_count": len(chunks),
            "errors": errors 
        }

    async def save_to_neo4j(self, data: Dict[str, Any], filename: str) -> Dict[str, int]:
        """
        Save extracted data to Neo4j using the provided driver.
        Returns counts of saved nodes and relationships.
        """
        nodes = data.get("nodes", [])
        rels = data.get("relationships", [])
        nodes_saved = 0
        rels_saved = 0
        
        # 1. Prepare Nodes with Embeddings
        # Generate embeddings concurrently for better performance
        if self.enable_embeddings and self.embedding_service:
            embedding_tasks = []
            nodes_to_embed = []
            
            for node in nodes:
                nodes_to_embed.append(node)
                embedding_tasks.append(self._generate_node_embedding(node))
            
            if embedding_tasks:
                embeddings = await asyncio.gather(*embedding_tasks)
                
                # Assign embeddings back to nodes
                for i, node in enumerate(nodes_to_embed):
                    if embeddings[i]:
                        if "properties" not in node:
                            node["properties"] = {}
                        node["properties"]["embedding"] = embeddings[i]

        # Prepare batch data for nodes
        node_batch = []
        for node in nodes:
            node_id = node.get("id", "")
            if not node_id: continue
            
            label = node.get("label", "Entity")
            # Sanitize label
            safe_label = re.sub(r'[^a-zA-Z0-9_]', '', label) or "Entity"
            props = node.get("properties", {})
            
            node_batch.append({
                "name": node_id,
                "label": safe_label,
                "props": props
            })

        # Prepare batch data for relationships
        rel_batch = []
        for rel in rels:
            source = rel.get("source")
            target = rel.get("target")
            rel_type = rel.get("type", "RELATED_TO").upper().replace(" ", "_")
            rel_type = re.sub(r'[^a-zA-Z0-9_]', '_', rel_type)
            
            if source and target:
                rel_batch.append({
                    "source": source,
                    "target": target,
                    "type": rel_type
                })

        # 1. Save Nodes (Batch)
        if node_batch:
            # Group by label to optimize MERGE
            nodes_by_label = {}
            for item in node_batch:
                lbl = item["label"]
                if lbl not in nodes_by_label:
                    nodes_by_label[lbl] = []
                nodes_by_label[lbl].append(item)
            
            async with self.driver.session() as session:
                for label, items in nodes_by_label.items():
                    query = f"""
                    UNWIND $items AS item
                    MERGE (n:`{label}` {{name: item.name}})
                    SET n += item.props
                    SET n:Entity
                    """
                    try:
                        await session.run(query, {"items": items})
                        nodes_saved += len(items)
                    except Exception as e:
                        await AuditLogger.log(f"Error saving nodes batch for label {label}: {e}", level=logging.ERROR)

        # 2. Save Relationships (Batch)
        if rel_batch:
            # Group by type
            rels_by_type = {}
            for item in rel_batch:
                rtype = item["type"]
                if rtype not in rels_by_type:
                    rels_by_type[rtype] = []
                rels_by_type[rtype].append(item)
                
            async with self.driver.session() as session:
                for rtype, items in rels_by_type.items():
                    query = f"""
                    UNWIND $items AS item
                    MATCH (a {{name: item.source}})
                    MATCH (b {{name: item.target}})
                    MERGE (a)-[r:`{rtype}`]->(b)
                    """
                    try:
                        await session.run(query, {"items": items})
                        rels_saved += len(items)
                    except Exception as e:
                        await AuditLogger.log(f"Error saving rels batch for type {rtype}: {e}", level=logging.ERROR)

        # 3. Link File Source
        async with self.driver.session() as session:
            try:
                await session.run("MERGE (f:File {name: $filename})", {"filename": filename})
            except Exception as e:
                await AuditLogger.log(f"Error creating File node: {e}", level=logging.ERROR)

        return {"nodes_saved": nodes_saved, "rels_saved": rels_saved}
