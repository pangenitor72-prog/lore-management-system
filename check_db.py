"""Quick script to check Neo4j database contents."""
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

if not URI:
    URI = "bolt://localhost:7687"
    print("⚠️  NEO4J_URI not set; defaulting to bolt://localhost:7687 for local development.")

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

with driver.session() as session:
    print("=" * 50)
    print("  NEO4J DATABASE CONTENTS")
    print("=" * 50)
    
    # Entity counts
    result = session.run("MATCH (n) RETURN labels(n)[0] AS type, count(n) AS count ORDER BY count DESC")
    print("\n📦 ENTITIES BY TYPE:")
    total = 0
    for record in result:
        print(f"   {record['type'] or 'No Label'}: {record['count']}")
        total += record['count']
    print(f"   ─────────────────")
    print(f"   TOTAL: {total}")
    
    # Relationship counts
    result = session.run("MATCH ()-[r]->() RETURN type(r) AS rel, count(r) AS count ORDER BY count DESC LIMIT 15")
    print("\n🔗 RELATIONSHIPS:")
    for record in result:
        print(f"   {record['rel']}: {record['count']}")
    
    # Sample entities
    result = session.run("MATCH (n) WHERE n.name IS NOT NULL RETURN n.name AS name, labels(n)[0] AS type LIMIT 20")
    print("\n📋 SAMPLE ENTITIES:")
    for record in result:
        print(f"   • {record['name']} ({record['type']})")

driver.close()
print("\n" + "=" * 50)



