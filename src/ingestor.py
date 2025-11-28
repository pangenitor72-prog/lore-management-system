import asyncio
import os
import json
import re
import google.generativeai as genai
from dotenv import load_dotenv
from neo4j_adapter import Neo4jDatabase

# ==========================================
# CONFIGURATION
# ==========================================
load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

if not API_KEY:
    print("❌ ERROR: Could not find 'GOOGLE_API_KEY' or 'GEMINI_API_KEY' in your .env file.")
    exit()

LORE_DIR = "./lore"
DB_URI = "bolt://localhost:7687"
DB_AUTH = ("neo4j", "password")

# Chunking settings
MAX_CHUNK_SIZE = 4000  # characters per chunk
CHUNK_OVERLAP = 200    # overlap between chunks for context

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# ==========================================
# THE SCHEMA PROMPT
# ==========================================
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

# ==========================================
# TEXT CHUNKING
# ==========================================
def chunk_text(text: str, max_size: int = MAX_CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list:
    """Split large text into overlapping chunks for better extraction."""
    if len(text) <= max_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + max_size
        
        # Try to break at paragraph or sentence boundary
        if end < len(text):
            # Look for paragraph break
            para_break = text.rfind('\n\n', start, end)
            if para_break > start + max_size // 2:
                end = para_break
            else:
                # Look for sentence break
                sentence_break = text.rfind('. ', start, end)
                if sentence_break > start + max_size // 2:
                    end = sentence_break + 1
        
        chunks.append(text[start:end].strip())
        start = end - overlap if end < len(text) else end
    
    return chunks

# ==========================================
# JSON PARSING WITH REPAIR
# ==========================================
def parse_json_response(text: str) -> dict:
    """Parse JSON from AI response with error recovery."""
    # Clean up common issues
    cleaned = text.strip()
    cleaned = re.sub(r'^```json\s*', '', cleaned)
    cleaned = re.sub(r'^```\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    cleaned = cleaned.strip()
    
    # Try direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    
    # Try to find JSON object in response
    match = re.search(r'\{[\s\S]*\}', cleaned)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    
    # Try to fix common issues
    # Fix trailing commas
    fixed = re.sub(r',(\s*[}\]])', r'\1', cleaned)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass
    
    # Return empty structure if all else fails
    return {"nodes": [], "relationships": []}

# ==========================================
# MERGE EXTRACTED DATA
# ==========================================
def merge_extractions(extractions: list) -> dict:
    """Merge multiple chunk extractions, deduplicating nodes."""
    all_nodes = {}
    all_rels = []
    
    for data in extractions:
        if not data:
            continue
            
        # Deduplicate nodes by ID
        for node in data.get("nodes", []):
            node_id = node.get("id", "")
            if node_id:
                if node_id not in all_nodes:
                    all_nodes[node_id] = node
                else:
                    # Merge properties
                    existing_props = all_nodes[node_id].get("properties", {})
                    new_props = node.get("properties", {})
                    all_nodes[node_id]["properties"] = {**existing_props, **new_props}
        
        # Collect relationships (may have duplicates, Neo4j MERGE handles it)
        all_rels.extend(data.get("relationships", []))
    
    return {
        "nodes": list(all_nodes.values()),
        "relationships": all_rels
    }

# ==========================================
# DATABASE LOGIC
# ==========================================
async def save_to_graph(db, data, filename):
    if not data or not data.get("nodes"):
        print(f"   ⚠️ No data extracted for {filename}")
        return

    nodes = data["nodes"]
    rels = data.get("relationships", [])
    
    print(f"   💾 Saving {len(nodes)} nodes and {len(rels)} edges...")

    # 1. Merge Nodes (handle missing properties gracefully)
    node_query = """
    UNWIND $nodes AS n
    CALL apoc.merge.node(
        [n.label], 
        {name: n.id}, 
        CASE WHEN n.properties IS NULL THEN {} ELSE n.properties END
    ) YIELD node
    RETURN count(node)
    """
    await db.execute(node_query, {"nodes": nodes})

    # 2. Merge Relationships (only if we have any)
    if rels:
        rel_query = """
        UNWIND $rels AS r
        MATCH (a {name: r.source})
        MATCH (b {name: r.target})
        CALL apoc.merge.relationship(a, r.type, {}, {}, b) YIELD rel
        RETURN count(rel)
        """
        await db.execute(rel_query, {"rels": rels})
    
    # 3. Link File Metadata
    source_query = """
    MERGE (f:File {name: $filename})
    WITH f
    UNWIND $node_ids AS node_name
    MATCH (n {name: node_name})
    MERGE (n)-[:SOURCE_IS]->(f)
    """
    node_ids = [n.get("id") for n in nodes if n.get("id")]
    await db.execute(source_query, {"filename": filename, "node_ids": node_ids})


async def process_file(db, filepath):
    filename = os.path.basename(filepath)
    print(f"\n📖 Reading: {filename}...")
    
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    # Chunk large files
    chunks = chunk_text(text)
    total_chunks = len(chunks)
    
    if total_chunks > 1:
        print(f"   📄 Large file detected. Split into {total_chunks} chunks.")
    
    extractions = []
    
    for i, chunk in enumerate(chunks):
        if total_chunks > 1:
            print(f"   🧠 Processing chunk {i+1}/{total_chunks}...")
        else:
            print("   🧠 Asking Gemini to extract knowledge...")
        
        try:
            response = model.generate_content(
                EXTRACTION_PROMPT + "\n\nTEXT:\n" + chunk,
                generation_config={"temperature": 0.1}
            )
            data = parse_json_response(response.text)
            extractions.append(data)
            
            if total_chunks > 1:
                node_count = len(data.get("nodes", []))
                rel_count = len(data.get("relationships", []))
                print(f"      Found {node_count} nodes, {rel_count} relationships")
                
        except Exception as e:
            print(f"   ❌ Chunk {i+1} extraction failed: {e}")
            continue
    
    if not extractions:
        print(f"   ❌ No data extracted from {filename}")
        return
    
    # Merge all extractions
    merged_data = merge_extractions(extractions)
    
    await save_to_graph(db, merged_data, filename)
    print(f"   ✅ Success: {filename}")


async def main():
    db = Neo4jDatabase(DB_URI, DB_AUTH)
    await db.connect()
    
    if not os.path.exists(LORE_DIR):
        print("❌ Lore folder not found.")
        return

    for root, _, files in os.walk(LORE_DIR):
        for file in files:
            if file.endswith((".md", ".txt", ".json")):
                await process_file(db, os.path.join(root, file))

    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
