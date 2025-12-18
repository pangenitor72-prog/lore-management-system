# src/services/vector_service.py

import logging
import asyncio
from typing import List, Optional, Dict, Any

from src.services.embedding_orchestrator import EmbeddingOrchestrator
from src.db.neo4j_adapter import Neo4jDatabase

logger = logging.getLogger(__name__)


class VectorService:
    """
    Handles embedding generation, storage, and vector similarity search.

    Keeps vector logic OUT of the core Neo4j adapter, which is responsible
    only for safe Cypher execution and connection pooling.
    """

    def __init__(self, db: Neo4jDatabase, orchestrator: EmbeddingOrchestrator):
        self.db = db
        self.orchestrator = orchestrator

    async def store_embedding(
        self,
        entity_id: str,
        text: str,
        label: str = "Entity"
    ) -> Optional[List[float]]:
        """
        Generate and store a 768-d vector embedding for an entity.
        """

        embedding = self.orchestrator.generate_embedding(text)
        if not embedding:
            logger.error(f"Failed to generate embedding for: {entity_id}")
            return None

        cypher = f"""
        MATCH (e:{label} {{entity_id: $entity_id}})
        SET e.embedding = $embedding
        RETURN e.entity_id AS id
        """

        await self.db.execute(cypher, {
            "entity_id": entity_id,
            "embedding": embedding
        })

        return embedding

    async def vector_search(
        self,
        query_text: str,
        label: str = "Entity",
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Perform similarity search using Neo4j native vector indexing
        (db.index.vector.queryNodes).
        """

        # 1. Generate embedding for query
        query_embedding = self.orchestrator.generate_embedding(query_text)
        if not query_embedding:
            return []

        # 2. Query Neo4j vector index
        cypher = """
        CALL db.index.vector.queryNodes(
            'entity_embedding_index',
            $limit,
            $embedding
        )
        YIELD node, score
        RETURN node.entity_id AS id,
               node.name AS name,
               score
        ORDER BY score DESC
        LIMIT $limit
        """

        return await self.db.execute(cypher, {
            "embedding": query_embedding,
            "limit": limit
        })

