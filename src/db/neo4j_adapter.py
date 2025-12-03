import re
from neo4j import AsyncGraphDatabase
from typing import List, Dict, Any, Optional
import logging

# Configure module logger
logger = logging.getLogger(__name__)

# Embedding dimension for Gemini text-embedding-004
EMBEDDING_DIMENSION = 768

# Regex pattern for safe Cypher identifiers
IDENTIFIER_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


class Neo4jDatabase:
    """
    Async Neo4j database adapter with vector search support.

    This is the low-level database boundary in the LMS/MANTLE architecture.

    Responsibilities:
    - Manage the async driver lifecycle
    - Execute parameterized Cypher safely
    - Manage vector indexes
    - Store and query embeddings
    - Provide hybrid (graph + vector) search utilities

    IMPORTANT:
    - All higher-level subsystems should depend on this adapter,
      not on the raw Neo4j driver.
    """

    def __init__(self, uri: str, auth: Any, db_name: str = "neo4j"):
        self.uri = uri
        self.auth = auth
        self.db_name = db_name
        self.driver: Optional[AsyncGraphDatabase] = None

    @staticmethod
    def validate_identifier(name: str) -> str:
        """
        Strictly validate identifiers to prevent Cypher injection.

        Allows only alphanumeric characters and underscores,
        and must start with a letter or underscore.
        """
        if not name or not IDENTIFIER_PATTERN.match(name):
            raise ValueError(
                f"Invalid Cypher identifier: '{name}'. "
                "Must start with letter/underscore and contain only alphanumeric/underscore."
            )
        return name

    @staticmethod
    def _sanitize_cypher_identifier(name: str, default: str) -> str:
        """
        Sanitize an identifier for use in Cypher f-strings.
        Returns the default if the name is invalid.

        This is defensive: it avoids runtime failure AND avoids
        unsanitized identifiers from reaching Cypher.
        """
        if not name:
            logger.warning(f"Empty identifier provided, using default: {default}")
            return default
        if not IDENTIFIER_PATTERN.match(name):
            logger.warning(f"Invalid identifier '{name}' sanitized to default: {default}")
            return default
        return name

    async def connect(self) -> None:
        """Establish the connection pool and verify connectivity."""
        if self.driver is not None:
            return

        try:
            self.driver = AsyncGraphDatabase.driver(self.uri, auth=self.auth)
            await self.driver.verify_connectivity()
            logger.info(f"Connected to Neo4j ({self.uri})")
        except Exception as e:
            logger.error(f"Neo4j connection failed: {e}")
            # Ensure driver is not left in a half-initialized state
            self.driver = None
            raise

    async def close(self) -> None:
        """Closes the connection pool."""
        if self.driver:
            try:
                await self.driver.close()
            finally:
                self.driver = None
                logger.info("Neo4j connection closed")

    async def execute(self, query: str, params: Optional[Dict[str, Any]] = None):
        """
        Execute a Cypher query (read/write) and return raw records.

        IMPORTANT BEHAVIOR:
        - On success: returns a list of records.
        - On failure: logs and RAISES the exception.
        - It NEVER returns None.

        This ensures that database errors are not silently treated as
        "no results", which was a previous source of hidden bugs.
        """
        if self.driver is None:
            await self.connect()

        if params is None:
            params = {}

        try:
            records, summary, keys = await self.driver.execute_query(
                query,
                parameters_=params,
                database_=self.db_name,
            )
            logger.debug(f"Cypher executed. Counters: {summary.counters}")
            return records
        except Exception as e:
            logger.error(f"Query error: {e}")
            logger.debug(f"Failed query: {query}")
            # Propagate so callers can distinguish "error" from "empty result"
            raise

    async def fetch_all(self, query: str, params: Optional[Dict[str, Any]] = None):
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
        similarity_function: str = "cosine",
    ) -> bool:
        """
        Create a vector index for semantic similarity search.

        Returns True if the index create command was issued successfully.
        """
        if similarity_function not in ["cosine", "euclidean"]:
            logger.error(f"Invalid similarity function: {similarity_function}")
            return False

        clean_index = self._sanitize_cypher_identifier(index_name, "entity_embeddings")
        clean_label = self._sanitize_cypher_identifier(label, "Entity")
        clean_prop = self._sanitize_cypher_identifier(property_name, "embedding")

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
            "similarity_function": similarity_function,
        }

        try:
            await self.execute(query, params)
            logger.info(f"Vector index '{clean_index}' created (or already exists)")
            return True
        except Exception as e:
            logger.error(f"Failed to create vector index: {e}")
            return False

    async def drop_vector_index(self, index_name: str = "entity_embeddings") -> bool:
        """Drop a vector index by name."""
        clean_index = self._sanitize_cypher_identifier(index_name, "entity_embeddings")
        query = f"DROP INDEX {clean_index} IF EXISTS"

        try:
            await self.execute(query)
            logger.info(f"Vector index '{clean_index}' dropped")
            return True
        except Exception as e:
            logger.error(f"Failed to drop vector index: {e}")
            return False

    async def list_indexes(self) -> List[Dict[str, Any]]:
        """List all indexes in the database."""
        query = "SHOW INDEXES"
        try:
            records = await self.execute(query)
            return [dict(r) for r in records] if records else []
        except Exception as e:
            logger.error(f"Failed to list indexes: {e}")
            return []

    # ==========================================
    # EMBEDDING STORAGE
    # ==========================================

    @staticmethod
    def _validate_embedding_dimension(embedding: List[float]) -> bool:
        if len(embedding) != EMBEDDING_DIMENSION:
            logger.error(
                f"Invalid embedding length: expected {EMBEDDING_DIMENSION}, "
                f"got {len(embedding)}"
            )
            return False
        return True

    async def store_embedding(
        self,
        node_id: str,
        embedding: List[float],
        id_property: str = "canon_id",
    ) -> bool:
        """
        Store an embedding vector on a single node.

        Returns True if a node was updated.
        """
        if not self._validate_embedding_dimension(embedding):
            return False

        clean_id_prop = self._sanitize_cypher_identifier(id_property, "canon_id")

        query = f"""
        MATCH (n {{{clean_id_prop}: $node_id}})
        SET n.embedding = $embedding
        RETURN n.name AS name
        """
        params = {"node_id": node_id, "embedding": embedding}

        try:
            records = await self.execute(query, params)
            return bool(records)
        except Exception as e:
            logger.error(f"Failed to store embedding for node '{node_id}': {e}")
            return False

    async def store_embeddings_batch(
        self,
        embeddings: List[Dict[str, Any]],
        id_property: str = "canon_id",
    ) -> int:
        """
        Store embeddings for multiple nodes in a batch.

        Each item in 'embeddings' must be a dict with:
        - 'node_id'
        - 'embedding'
        """
        if not embeddings:
            return 0

        # Validate all embeddings
        valid_items = []
        for item in embeddings:
            vec = item.get("embedding")
            node_id = item.get("node_id")
            if not isinstance(node_id, str):
                logger.warning(f"Skipping embedding with invalid node_id: {item}")
                continue
            if not isinstance(vec, list) or not self._validate_embedding_dimension(vec):
                logger.warning(f"Skipping embedding with invalid vector for node '{node_id}'")
                continue
            valid_items.append({"node_id": node_id, "embedding": vec})

        if not valid_items:
            return 0

        clean_id_prop = self._sanitize_cypher_identifier(id_property, "canon_id")

        query = f"""
        UNWIND $items AS item
        MATCH (n {{{clean_id_prop}: item.node_id}})
        SET n.embedding = item.embedding
        RETURN count(n) AS updated
        """
        params = {"items": valid_items}

        try:
            records = await self.execute(query, params)
            if records and len(records) > 0:
                return records[0].get("updated", 0)
            return 0
        except Exception as e:
            logger.error(f"Batch embedding storage failed: {e}")
            return 0

    async def get_nodes_without_embeddings(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Find nodes (by default, entities) that don't have embeddings yet.

        NOTE: We restrict to label :Entity to avoid scanning the entire graph.
        """
        query = """
        MATCH (n:Entity)
        WHERE n.embedding IS NULL AND n.name IS NOT NULL
        RETURN n.canon_id AS canon_id,
               n.name AS name,
               labels(n)[0] AS type,
               n.description AS description,
               n.content AS content
        LIMIT $limit
        """
        params = {"limit": limit}

        try:
            records = await self.execute(query, params)
            return [dict(r) for r in records] if records else []
        except Exception as e:
            logger.error(f"Failed to fetch nodes without embeddings: {e}")
            return []

    async def count_embeddings(self) -> Dict[str, int]:
        """
        Count nodes with and without embeddings (for :Entity nodes).
        """
        query = """
        MATCH (n:Entity)
        WHERE n.name IS NOT NULL
        RETURN 
            count(CASE WHEN n.embedding IS NOT NULL THEN 1 END) AS with_embedding,
            count(CASE WHEN n.embedding IS NULL THEN 1 END) AS without_embedding
        """
        try:
            records = await self.execute(query)
            if records and len(records) > 0:
                return {
                    "with_embedding": records[0].get("with_embedding", 0),
                    "without_embedding": records[0].get("without_embedding", 0),
                }
            return {"with_embedding": 0, "without_embedding": 0}
        except Exception as e:
            logger.error(f"Failed to count embeddings: {e}")
            return {"with_embedding": 0, "without_embedding": 0}

    # ==========================================
    # VECTOR SIMILARITY SEARCH
    # ==========================================

    async def vector_search(
        self,
        query_embedding: List[float],
        limit: int = 10,
        min_score: float = 0.5,
        index_name: str = "entity_embeddings",
    ) -> List[Dict[str, Any]]:
        """
        Find nodes most similar to a query embedding using a vector index.
        """
        if not self._validate_embedding_dimension(query_embedding):
            return []

        query = """
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
            "min_score": min_score,
        }

        try:
            records = await self.execute(query, params)
            return [dict(r) for r in records] if records else []
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    async def hybrid_search(
        self,
        query_embedding: List[float],
        start_node_id: str,
        max_hops: int = 2,
        limit: int = 10,
        min_score: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search: vector similarity + graph proximity.

        - Restricts to nodes connected to a start node within N hops.
        - Uses cosine similarity on embedding vectors.
        """
        if not self._validate_embedding_dimension(query_embedding):
            return []

        if not isinstance(max_hops, int) or max_hops < 1 or max_hops > 10:
            logger.warning(f"Invalid max_hops value '{max_hops}', clamping to [1,10]")
            try:
                max_hops = int(max_hops)
            except Exception:
                max_hops = 2
            max_hops = max(1, min(10, max_hops))

        query = f"""
        MATCH (start {{canon_id: $start_node_id}})
        MATCH (start)-[*1..{max_hops}]-(related)
        WHERE related.embedding IS NOT NULL

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
            "limit": limit,
        }

        try:
            records = await self.execute(query, params)
            return [dict(r) for r in records] if records else []
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            return []