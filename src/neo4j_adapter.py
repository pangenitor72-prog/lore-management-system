import re
from neo4j import AsyncGraphDatabase
from typing import List, Dict, Any, Optional
import logging

# Embedding dimension for Gemini text-embedding-004
EMBEDDING_DIMENSION = 768


class Neo4jDatabase:
    """
    Async Neo4j database adapter with vector search support.
    
    Supports Neo4j 5.x vector indexes for semantic similarity search
    combined with traditional graph traversal.
    """
    
    def __init__(self, uri, auth, db_name="neo4j"):
        self.uri = uri
        self.auth = auth
        self.db_name = db_name
        self.driver = None

    def _sanitize_cypher_identifier(self, identifier: str, fallback: str = "default") -> str:
        """
        Sanitize identifiers for use in Cypher queries.
        Only allows alphanumeric characters and underscores.
        """
        if not identifier:
            return fallback
        
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '', identifier)
        
        if sanitized and sanitized[0].isdigit():
            sanitized = f"_{sanitized}"
        
        return sanitized if sanitized else fallback

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
    
    # ==========================================
    # VECTOR INDEX MANAGEMENT
    # ==========================================
    
    async def create_vector_index(
        self, 
        index_name: str = "entity_embeddings",
        label: str = "Entity",
        property_name: str = "embedding",
        dimensions: int = EMBEDDING_DIMENSION,
        similarity_function: str = "cosine"
    ) -> bool:
        """
        Create a vector index for semantic similarity search.
        
        Args:
            index_name: Name of the index
            label: Node label to index (use "Entity" for all entities)
            property_name: Property containing the embedding vector
            dimensions: Vector dimensions (768 for Gemini text-embedding-004)
            similarity_function: "cosine" or "euclidean"
        
        Returns:
            True if successful, False otherwise
        """
        # Validate inputs
        if similarity_function not in ["cosine", "euclidean"]:
            print(f"❌ Invalid similarity function: {similarity_function}")
            return False
            
        clean_index = self._sanitize_cypher_identifier(index_name, "entity_embeddings")
        clean_label = self._sanitize_cypher_identifier(label, "Entity")
        clean_prop = self._sanitize_cypher_identifier(property_name, "embedding")
        
        # Neo4j 5.x vector index creation syntax
        query = f"""
        CREATE VECTOR INDEX {clean_index} IF NOT EXISTS
        FOR (n:{clean_label})
        ON (n.{clean_prop})
        OPTIONS {{
            indexConfig: {{
                `vector.dimensions`: $dimensions,
                `vector.similarity_function`: $similarity_function
            }}
        }}
        """
        params = {
            "dimensions": dimensions,
            "similarity_function": similarity_function
        }
        
        try:
            await self.execute(query, params)
            print(f"✅ Vector index '{clean_index}' created (or already exists)")
            return True
        except Exception as e:
            print(f"❌ Failed to create vector index: {e}")
            return False
    
    async def drop_vector_index(self, index_name: str = "entity_embeddings") -> bool:
        """Drop a vector index."""
        clean_index = self._sanitize_cypher_identifier(index_name, "entity_embeddings")
        query = f"DROP INDEX {clean_index} IF EXISTS"
        try:
            await self.execute(query)
            print(f"🗑️ Vector index '{clean_index}' dropped")
            return True
        except Exception as e:
            print(f"❌ Failed to drop vector index: {e}")
            return False
    
    async def list_indexes(self) -> List[Dict[str, Any]]:
        """List all indexes in the database."""
        query = "SHOW INDEXES"
        records = await self.execute(query)
        if records:
            return [dict(r) for r in records]
        return []
    
    # ==========================================
    # EMBEDDING STORAGE
    # ==========================================
    
    async def store_embedding(
        self,
        node_id: str,
        embedding: List[float],
        id_property: str = "canon_id"
    ) -> bool:
        """
        Store an embedding vector on a node.
        
        Args:
            node_id: The node's identifier (canon_id by default)
            embedding: The embedding vector (list of floats)
            id_property: Property name used to identify the node
        
        Returns:
            True if successful
        """
        query = f"""
        MATCH (n {{{id_property}: $node_id}})
        SET n.embedding = $embedding
        RETURN n.name AS name
        """
        params = {"node_id": node_id, "embedding": embedding}
        
        try:
            records = await self.execute(query, params)
            if records and len(records) > 0:
                return True
            return False
        except Exception as e:
            print(f"❌ Failed to store embedding: {e}")
            return False
    
    async def store_embeddings_batch(
        self,
        embeddings: List[Dict[str, Any]],
        id_property: str = "canon_id"
    ) -> int:
        """
        Store embeddings for multiple nodes in a batch.
        
        Args:
            embeddings: List of dicts with 'node_id' and 'embedding' keys
            id_property: Property name used to identify nodes
        
        Returns:
            Number of nodes updated
        """
        query = f"""
        UNWIND $items AS item
        MATCH (n {{{id_property}: item.node_id}})
        SET n.embedding = item.embedding
        RETURN count(n) AS updated
        """
        params = {"items": embeddings}
        
        try:
            records = await self.execute(query, params)
            if records and len(records) > 0:
                return records[0]["updated"]
            return 0
        except Exception as e:
            print(f"❌ Batch embedding storage failed: {e}")
            return 0
    
    async def get_nodes_without_embeddings(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Find nodes that don't have embeddings yet.
        
        Returns:
            List of nodes missing embeddings
        """
        query = """
        MATCH (n)
        WHERE n.embedding IS NULL AND n.name IS NOT NULL
        RETURN n.canon_id AS canon_id,
               n.name AS name,
               labels(n)[0] AS type,
               n.description AS description,
               n.content AS content
        LIMIT $limit
        """
        params = {"limit": limit}
        
        records = await self.execute(query, params)
        if records:
            return [dict(r) for r in records]
        return []
    
    async def count_embeddings(self) -> Dict[str, int]:
        """
        Count nodes with and without embeddings.
        
        Returns:
            Dict with 'with_embedding' and 'without_embedding' counts
        """
        query = """
        MATCH (n)
        WHERE n.name IS NOT NULL
        RETURN 
            count(CASE WHEN n.embedding IS NOT NULL THEN 1 END) AS with_embedding,
            count(CASE WHEN n.embedding IS NULL THEN 1 END) AS without_embedding
        """
        records = await self.execute(query)
        if records and len(records) > 0:
            return {
                "with_embedding": records[0]["with_embedding"],
                "without_embedding": records[0]["without_embedding"]
            }
        return {"with_embedding": 0, "without_embedding": 0}
    
    # ==========================================
    # VECTOR SIMILARITY SEARCH
    # ==========================================
    
    async def vector_search(
        self,
        query_embedding: List[float],
        limit: int = 10,
        min_score: float = 0.5,
        index_name: str = "entity_embeddings"
    ) -> List[Dict[str, Any]]:
        """
        Find nodes most similar to a query embedding using vector index.
        
        Args:
            query_embedding: The query vector (768 dimensions)
            limit: Maximum number of results
            min_score: Minimum similarity score (0-1 for cosine)
            index_name: Name of the vector index to use
        
        Returns:
            List of nodes with similarity scores, ordered by score desc
        """
        # Neo4j 5.x vector search syntax
        query = f"""
        CALL db.index.vector.queryNodes($index_name, $limit, $embedding)
        YIELD node, score
        WHERE score >= $min_score
        RETURN node.canon_id AS canon_id,
               node.name AS name,
               labels(node)[0] AS type,
               node.description AS description,
               properties(node) AS properties,
               score
        ORDER BY score DESC
        """
        params = {
            "index_name": index_name,
            "limit": limit,
            "embedding": query_embedding,
            "min_score": min_score
        }
        
        try:
            records = await self.execute(query, params)
            if records:
                return [dict(r) for r in records]
            return []
        except Exception as e:
            print(f"❌ Vector search failed: {e}")
            return []
    
    async def hybrid_search(
        self,
        query_embedding: List[float],
        start_node_id: str,
        max_hops: int = 2,
        limit: int = 10,
        min_score: float = 0.5,
        index_name: str = "entity_embeddings"
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search: Vector similarity + graph proximity.
        
        Finds nodes that are both semantically similar AND connected
        to a starting node within N hops.
        
        Args:
            query_embedding: The query vector
            start_node_id: canon_id of the starting node
            max_hops: Maximum relationship distance
            limit: Maximum results
            min_score: Minimum similarity score
            index_name: Vector index name
        
        Returns:
            Nodes matching both criteria with similarity scores
        """
        query = f"""
        // First, find the start node
        MATCH (start {{canon_id: $start_node_id}})
        
        // Find nodes within N hops
        MATCH (start)-[*1..{max_hops}]-(related)
        WHERE related.embedding IS NOT NULL
        
        // Calculate similarity
        WITH related, 
             vector.similarity.cosine(related.embedding, $embedding) AS score
        WHERE score >= $min_score
        
        RETURN related.canon_id AS canon_id,
               related.name AS name,
               labels(related)[0] AS type,
               related.description AS description,
               score
        ORDER BY score DESC
        LIMIT $limit
        """
        params = {
            "start_node_id": start_node_id,
            "embedding": query_embedding,
            "min_score": min_score,
            "limit": limit
        }
        
        try:
            records = await self.execute(query, params)
            if records:
                return [dict(r) for r in records]
            return []
        except Exception as e:
            print(f"❌ Hybrid search failed: {e}")
            return []