#!/usr/bin/env python3
"""
Clear Neo4j Database Script

Deletes all nodes and relationships from the Neo4j database.
This is a destructive operation and cannot be undone.

Usage:
    python scripts/clear_db.py
"""
import asyncio
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dotenv import load_dotenv
from neo4j_adapter import Neo4jDatabase

# Load environment
load_dotenv()

# Configuration
DB_URI = os.getenv("NEO4J_URI")
DB_USER = os.getenv("NEO4J_USER", "neo4j")
DB_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

if not DB_URI:
    DB_URI = "bolt://localhost:7687"
    print("⚠️  NEO4J_URI not set; defaulting to bolt://localhost:7687 for local development.")


async def clear_database(db: Neo4jDatabase):
    """Deletes all nodes and relationships from the database."""
    print("🔥 WARNING: This will delete ALL data from the Neo4j database.")
    print(f"   Database: {DB_URI}")
    
    confirm = input("   Type 'ERASE' to confirm and proceed: ")
    
    if confirm != "ERASE":
        print("\n🚫 Operation cancelled. No changes were made.")
        return

    print("\n💥 Deleting all nodes and relationships...")
    try:
        await db.execute("MATCH (n) DETACH DELETE n")
        count_query = await db.fetch_one("MATCH (n) RETURN count(n) as count")
        remaining_nodes = count_query["count"]
        if remaining_nodes == 0:
            print("   ✅ Database cleared successfully. Node count: 0.")
        else:
            print(f"   ⚠️ Something went wrong. {remaining_nodes} nodes still remain.")
    except Exception as e:
        print(f"   ❌ An error occurred: {e}")


async def main():
    """Main function to connect and clear the database."""
    print("=" * 60)
    print("  CLEAR NEO4J DATABASE")
    print("=" * 60)
    
    print("\n🔌 Connecting to Neo4j...")
    db = Neo4jDatabase(uri=DB_URI, auth=(DB_USER, DB_PASSWORD))
    
    try:
        await db.connect()
        print("   ✅ Connected successfully.")
        await clear_database(db)
    except Exception as e:
        print(f"   ❌ Failed to connect to the database: {e}")
    finally:
        await db.close()
        print("\n🔌 Connection closed.")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
