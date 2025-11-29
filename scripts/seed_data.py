from neo4j import GraphDatabase

# Config
URI = "bolt://localhost:7687"
AUTH = ("neo4j", "password")

def seed_graph():
    query = """
    CREATE (sword:Item {name: "Blade of Whispers"})
    CREATE (paladin:Character {name: "Kael"})
    CREATE (flavor:Concept {name: "Void Corruption"})
    
    CREATE (sword)-[:IMBUED_WITH]->(flavor)
    CREATE (paladin)-[:WIELDS]->(sword)
    CREATE (paladin)-[:VULNERABLE_TO]->(flavor)
    """
    
    print("🔌 Connecting to Brain...")
    with GraphDatabase.driver(URI, auth=AUTH) as driver:
        driver.execute_query(query)
        print("✅ Data Injected! Go check the browser.")

if __name__ == "__main__":
    seed_graph()