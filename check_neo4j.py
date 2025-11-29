import asyncio
import os
from dotenv import load_dotenv
from src.neo4j_adapter import Neo4jDatabase

load_dotenv()

async def check_counts():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    auth = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password"))
    
    db = Neo4jDatabase(uri, auth)
    await db.connect()
    
    try:
        print("--- Neo4j Counts ---")
        
        # Count Entities
        res = await db.execute("MATCH (n:Entity) RETURN count(n) as count")
        print(f"Entities: {res[0]['count']}")
        
        # Count Relationships
        res = await db.execute("MATCH ()-[r]->() RETURN count(r) as count")
        print(f"Relationships: {res[0]['count']}")
        
        # Count Contradictions
        res = await db.execute("MATCH (c:Contradiction) RETURN count(c) as count")
        print(f"Contradictions: {res[0]['count']}")
        
        # Sample Entity
        print("\n--- Sample Entity ---")
        res = await db.execute("MATCH (n:Entity) RETURN n LIMIT 1")
        if res:
            print(res[0])
            
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(check_counts())

