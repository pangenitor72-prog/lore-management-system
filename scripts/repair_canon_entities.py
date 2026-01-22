import asyncio
import os
import logging
from dotenv import load_dotenv
from src.mantle.db.neo4j_adapter import Neo4jDatabase
from src.mantle.core.normalization import normalize_entity_name

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def repair_canon_entities():
    """
    One-Time Data Repair Plan for Canonical Identity.
    1. Backfills normalized_name for all entities.
    2. Identifies duplicates based on (entity_type, normalized_name).
    3. Merges duplicates using apoc.refactor.mergeNodes.
    """
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    auth = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password"))
    
    db = Neo4jDatabase(uri, auth)
    
    try:
        await db.connect()
        print("🚀 Starting Canonical Identity Repair...")
        
        # ---------------------------------------------------------
        # 1. Backfill normalized_name
        # ---------------------------------------------------------
        print("   -> Backfilling normalized_name...")
        query = "MATCH (e:Entity) WHERE e.normalized_name IS NULL RETURN e.canon_id as id, e.name as name"
        records = await db.execute(query)
        
        updates = []
        for row in records:
            name = row.get("name")
            if not name:
                continue
            norm = normalize_entity_name(name)
            updates.append({"id": row["id"], "norm": norm})
        
        # Batch update in chunks of 500
        chunk_size = 500
        for i in range(0, len(updates), chunk_size):
            chunk = updates[i:i + chunk_size]
            update_query = """
            UNWIND $updates as up
            MATCH (e:Entity {canon_id: up.id})
            SET e.normalized_name = up.norm
            """
            await db.execute(update_query, {"updates": chunk})
            print(f"      Backfilled {len(chunk)} entities (Batch {i//chunk_size + 1}).")
            
        print(f"      Total backfilled: {len(updates)}")
        
        # ---------------------------------------------------------
        # 2. Identify & Merge Duplicates
        # ---------------------------------------------------------
        print("   -> Identifying duplicates...")
        dup_query = """
        MATCH (e:Entity)
        WHERE e.normalized_name IS NOT NULL
        WITH e.entity_type as type, e.normalized_name as norm, collect(e) as nodes, count(e) as c
        WHERE c > 1
        RETURN type, norm, nodes
        """
        duplicates = await db.execute(dup_query)
        
        if not duplicates:
            print("✅ No duplicates found.")
            return

        print(f"⚠️ Found {len(duplicates)} sets of duplicates.")
        
        for row in duplicates:
            nodes = row["nodes"]
            # Logic: Keep the one with the most relationships? 
            # Or just the oldest? (canon_id is UUID so not sortable by time easily unless we have created_at).
            # We'll rely on the one that was found first in the list?
            # To be deterministic, sort by canon_id.
            
            node_ids = sorted([n["canon_id"] for n in nodes])
            primary_id = node_ids[0]
            secondary_ids = node_ids[1:]
            
            print(f"      Merging {len(secondary_ids)} entities into {primary_id} ({row['type']}: {row['norm']})...")
            
            # Using APOC to merge
            # properties: 'discard' -> keep primary's properties if conflict
            # mergeRels: true -> move relationships to primary
            merge_query = """
            MATCH (primary:Entity {canon_id: $primary_id})
            MATCH (secondary:Entity) WHERE secondary.canon_id IN $secondary_ids
            WITH primary, secondary
            ORDER BY secondary.canon_id
            WITH primary, collect(secondary) as secondaries
            CALL apoc.refactor.mergeNodes([primary] + secondaries, {
                properties: 'discard', 
                mergeRels: true
            }) YIELD node
            RETURN node.canon_id
            """
            
            try:
                await db.execute(merge_query, {"primary_id": primary_id, "secondary_ids": secondary_ids})
                print("         Success.")
            except Exception as e:
                print(f"         FAILED: {e}")
                
        print("✅ Repair complete. You may now run scripts/apply_canon_constraints.py.")
        
    except Exception as e:
        print(f"❌ Repair failed: {e}")
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(repair_canon_entities())

