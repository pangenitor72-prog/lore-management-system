import asyncio
import os
from dotenv import load_dotenv
from src.neo4j_adapter import Neo4jDatabase

load_dotenv()

async def create_constraints():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    auth = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password"))
    
    db = Neo4jDatabase(uri, auth)
    await db.connect()
    
    queries = [
        # Session constraints
        "CREATE CONSTRAINT session_id_unique IF NOT EXISTS FOR (s:Session) REQUIRE s.session_id IS UNIQUE",
        
        # Instance constraints
        "CREATE CONSTRAINT instance_id_unique IF NOT EXISTS FOR (i:Instance) REQUIRE i.instance_id IS UNIQUE",
        
        # Index on session_id for performance
        "CREATE INDEX session_id_index IF NOT EXISTS FOR (s:Session) ON (s.session_id)",
        
        # Index on instance relationship to session for fast lookup
        "CREATE INDEX instance_session_index IF NOT EXISTS FOR (i:Instance) ON (i.session_id)" 
    ]
    
    try:
        print("🚀 Creating Graph Schema for AIRpg...")
        for q in queries:
            await db.execute(q)
            print(f"   -> Executed: {q.split('FOR')[0]}...")
            
        print("✅ Schema setup complete.")
        
    except Exception as e:
        print(f"❌ Schema setup failed: {e}")
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(create_constraints())

