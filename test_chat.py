import asyncio
import os
from dotenv import load_dotenv
from src.neo4j_adapter import Neo4jDatabase
from src.query_agent import QueryAgent 

load_dotenv()

DB_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
DB_AUTH = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password"))
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

async def test_agent():
    print("🤖 Initializing Query Agent...")
    db = Neo4jDatabase(DB_URI, DB_AUTH)
    await db.connect()
    
    # Initialize Agent with the connected DB and Gemini key
    agent = QueryAgent(db, GEMINI_KEY)
    
    query = "Summarize the Vulture Clan. Who are their enemies?"
    print(f"\n❓ Asking: '{query}'")
    
    # Use the async ask() method (RAG-powered)
    response = await agent.ask(query) 
    
    print(f"\n💡 Answer:\n{response}")
    
    await db.close()

if __name__ == "__main__":
    asyncio.run(test_agent())
