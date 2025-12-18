import asyncio
import os
from dotenv import load_dotenv
from src.db.neo4j_adapter import Neo4jDatabase

load_dotenv()

async def apply_constraints():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    auth = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password"))
    
    db = Neo4jDatabase(uri, auth)
    
    try:
        await db.connect()
        
        queries = [
            # Enforce canonical identity uniqueness per entity type
            "CREATE CONSTRAINT unique_entity_normalized IF NOT EXISTS FOR (e:Entity) REQUIRE (e.entity_type, e.normalized_name) IS UNIQUE"
        ]
        
        print("🚀 Applying Canon Identity Constraints...")
        for q in queries:
            await db.execute(q)
            print(f"   -> Executed: {q}")
            
        print("✅ Constraints applied successfully.")
        
    except Exception as e:
        print(f"❌ Failed to apply constraints: {e}")
        print("   Note: This may fail if duplicate normalized entities already exist. Run scripts/repair_canon_entities.py first.")
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(apply_constraints())

