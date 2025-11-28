from neo4j import AsyncGraphDatabase
import logging

class Neo4jDatabase:
    def __init__(self, uri, auth, db_name="neo4j"):
        self.uri = uri
        self.auth = auth
        self.db_name = db_name
        self.driver = None

    async def connect(self):
        """Establishes the connection pool."""
        if not self.driver:
            try:
                self.driver = AsyncGraphDatabase.driver(self.uri, auth=self.auth)
                await self.driver.verify_connectivity()
                print(f"🔌 Connected to Neo4j ({self.uri})")
            except Exception as e:
                print(f"❌ Connection Failed: {e}")
                raise e

    async def close(self):
        """Closes the connection pool."""
        if self.driver:
            await self.driver.close()
            print("🔒 Connection Closed")

    async def execute(self, query, params=None):
        """
        Executes a Cypher query (Write/Read).
        Returns the raw result records.
        """
        if not self.driver:
            await self.connect()

        if params is None:
            params = {}

        try:
            # We use execute_query which handles sessions/transactions automatically in Neo4j 5.x
            records, summary, keys = await self.driver.execute_query(
                query,
                parameters_=params,
                database_=self.db_name
            )
            # print(f"   ⚡ Cypher Executed: {summary.counters}") # Optional: Debug noise
            return records
        except Exception as e:
            print(f"❌ Query Error: {e}")
            print(f"   Query: {query}")
            return None
            
    async def fetch_all(self, query, params=None):
        """Alias for execute, for compatibility."""
        return await self.execute(query, params)