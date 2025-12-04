from src.db.neo4j_adapter import Neo4jDatabase
import asyncio
import uuid
import json
import re
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from src.services.embedding_service import EmbeddingService
from src.services.audit_log import AuditLogger
from src.services.extraction_service import ExtractionService

# Configure module logger
logger = logging.getLogger(__name__)

# Regex pattern for safe Cypher identifiers (labels, relationship types)
CYPHER_IDENTIFIER_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

# Default values for data model compliance
DEFAULT_CONFIDENCE_LEVEL = "AI_GENERATED"
DEFAULT_PARTY_KNOWLEDGE = "SECRET"


class LoreIngestor:
    """
    Handles parsing, AI extraction, and graph ingestion of lore files.
    """

    # Configuration constants
    MAX_CHUNK_SIZE = 4000
    CHUNK_OVERLAP = 200

    def __init__(
        self,
        db: Neo4jDatabase,
        extraction_service: ExtractionService,
        embedding_service: Optional[EmbeddingService] = None
    ):
        """
        Initialize the ingestor with necessary services.
        """
        self.db = db
        self.extraction_service = extraction_service
        self.embedding_service = embedding_service
        self.enable_embeddings = embedding_service is not None

    @staticmethod
    def sanitize_cypher_identifier(name: str, default: str = "Entity") -> str:
        """
        Sanitize a string for use as a Cypher label or relationship type.

        Rules:
        - Must start with a letter or underscore
        - Can only contain alphanumeric characters and underscores
        - Returns default if sanitization fails

        Args:
            name: The identifier to sanitize
            default: Fallback value if name cannot be sanitized

        Returns:
            A safe Cypher identifier
        """
        if not name:
            logger.warning(f"Empty identifier provided, using default: {default}")
            return default

        # First, replace spaces and hyphens with underscores
        sanitized = name.replace(" ", "_").replace("-", "_")

        # Remove any other invalid characters
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '', sanitized)

        # Ensure it starts with a letter or underscore (not a digit)
        if sanitized and sanitized[0].isdigit():
            sanitized = "_" + sanitized

        # Final validation
        if not sanitized or not CYPHER_IDENTIFIER_PATTERN.match(sanitized):
            logger.warning(f"Invalid identifier '{name}' sanitized to default: {default}")
            return default

        return sanitized

    def chunk_text(self, text: str) -> List[str]:
        """Split large text into overlapping chunks."""
        if len(text) <= self.MAX_CHUNK_SIZE:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + self.MAX_CHUNK_SIZE
            if end < len(text):
                # Try to break at paragraph or sentence
                para_break = text.rfind("\n\n", start, end)
                if para_break > start + self.MAX_CHUNK_SIZE // 2:
                    end = para_break
                else:
                    sentence_break = text.rfind(". ", start, end)
                    if sentence_break > start + self.MAX_CHUNK_SIZE // 2:
                        end = sentence_break + 1

            chunks.append(text[start:end].strip())
            start = end - self.CHUNK_OVERLAP if end < len(text) else end

        return chunks

    def merge_extractions(self, extractions: List[Dict]) -> Dict[str, Any]:
        """Merge multiple chunk extractions."""
        all_nodes: Dict[str, Dict[str, Any]] = {}
        all_rels: List[Dict[str, Any]] = []

        for data in extractions:
            if not data:
                continue

            for node in data.get("nodes", []):
                node_id = node.get("id", "")
                if not node_id:
                    continue

                if node_id not in all_nodes:
                    # Ensure properties exists
                    if "properties" not in node or node["properties"] is None:
                        node["properties"] = {}
                    all_nodes[node_id] = node
                else:
                    # Merge properties
                    existing_props = all_nodes[node_id].setdefault("properties", {})
                    new_props = node.get("properties", {}) or {}
                    existing_props.update(new_props)

            all_rels.extend(data.get("relationships", []))

        return {
            "nodes": list(all_nodes.values()),
            "relationships": all_rels
        }

    async def _generate_node_embedding(self, node: Dict) -> Optional[List[float]]:
        """
        Generate embedding for a node using the embedding service.
        """
        if not self.enable_embeddings or not self.embedding_service:
            return None

        node_id = node.get("id", "Unknown")

        # The AI extraction uses "id" for the node name. Pass the whole node
        # object to the embedding service for a richer embedding.
        # The service's method is synchronous, so run it in an executor.
        loop = asyncio.get_event_loop()
        try:
            embedding = await loop.run_in_executor(
                None,
                lambda: self.embedding_service.embed_entity(node)
            )
            return embedding
        except Exception as e:
            await AuditLogger.log(
                f"Embedding generation failed for node {node_id}: {str(e)}",
                level=logging.ERROR
            )
            return None

    async def process_file_content(self, filename: str, content: str) -> Dict[str, Any]:
        """
        Process file content: Chunk -> Extract -> Return Data (does not save yet).
        Useful for UI preview.
        """
        chunks = self.chunk_text(content)

        # Concurrent extraction using the dedicated service
        tasks = [
            self.extraction_service.extract_graph_from_chunk(chunk, i)
            for i, chunk in enumerate(chunks)
        ]
        extractions = await asyncio.gather(*tasks)

        # Check for empty results which might indicate errors (already logged in the service)
        errors: List[str] = []

        merged_data = self.merge_extractions(extractions)
        return {
            "filename": filename,
            "data": merged_data,
            "chunks_count": len(chunks),
            "errors": errors,
        }

    async def save_to_neo4j(self, data: Dict[str, Any], filename: str) -> Dict[str, int]:
        """
        Save extracted data to Neo4j using the provided driver.

        Ensures all nodes adhere to the data model by injecting default values:
        - confidence_level: "AI_GENERATED" (unless specified)
        - party_knowledge: "SECRET" (unless specified)
        - source: The filename the entity was extracted from
        - created_at: ISO timestamp of ingestion

        All labels and relationship types are sanitized to prevent Cypher injection.

        Returns counts of saved nodes and relationships.
        """
        nodes = data.get("nodes", []) or []
        rels = data.get("relationships", []) or []
        nodes_saved = 0
        rels_saved = 0

        # Timestamp for this ingestion batch
        ingestion_timestamp = datetime.now(timezone.utc).isoformat()

        # Sanitize filename for use as source reference
        safe_filename = re.sub(r'[<>:"/\\|?*]', "_", filename) if filename else "unknown_source"

        # 1. Prepare Nodes with Embeddings
        if self.enable_embeddings and self.embedding_service and nodes:
            embedding_tasks = [self._generate_node_embedding(node) for node in nodes]
            embeddings = await asyncio.gather(*embedding_tasks)

            for node, embedding in zip(nodes, embeddings):
                if embedding:
                    props = node.setdefault("properties", {})
                    if props is None:
                        props = {}
                        node["properties"] = props
                    props["embedding"] = embedding

        # Prepare batch data for nodes with default value injection
        node_batch: List[Dict[str, Any]] = []
        for node in nodes:
            node_id = node.get("id", "")
            if not node_id:
                continue

            # Sanitize label using the proper identifier sanitizer
            label = node.get("label", "Entity")
            safe_label = self.sanitize_cypher_identifier(label, "Entity")

            # Get existing properties as a copy so we don't mutate original dict unexpectedly
            props = dict(node.get("properties", {}) or {})

            # === INJECT DEFAULT VALUES IF MISSING ===
            # confidence_level: How much to trust this data
            if "confidence_level" not in props:
                props["confidence_level"] = DEFAULT_CONFIDENCE_LEVEL

            # party_knowledge: Who knows about this entity
            if "party_knowledge" not in props:
                props["party_knowledge"] = DEFAULT_PARTY_KNOWLEDGE

            # source: Where this data came from
            if "source" not in props:
                props["source"] = safe_filename

            # created_at: When this entity was ingested (don't overwrite if updating)
            if "created_at" not in props:
                props["created_at"] = ingestion_timestamp

            # updated_at: Always update this timestamp
            props["updated_at"] = ingestion_timestamp

            node_batch.append(
                {
                    "name": node_id