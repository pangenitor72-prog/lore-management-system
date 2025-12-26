from src.lms.db.neo4j_adapter import Neo4jDatabase
import asyncio
import uuid
import re
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from src.lms.services.embedding_service import EmbeddingService
from src.lms.services.audit_log import AuditLogger
from src.lms.services.extraction_service import ExtractionService

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

        # Replace spaces and hyphens with underscores
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
        """
        Split large text into overlapping chunks for extraction.
        """
        if len(text) <= self.MAX_CHUNK_SIZE:
            return [text]

        chunks: List[str] = []
        start = 0

        while start < len(text):
            end = start + self.MAX_CHUNK_SIZE
            if end < len(text):
                # Try to break at paragraph or sentence
                para_break = text.rfind('\n\n', start, end)
                if para_break > start + self.MAX_CHUNK_SIZE // 2:
                    end = para_break
                else:
                    sentence_break = text.rfind('. ', start, end)
                    if sentence_break > start + self.MAX_CHUNK_SIZE // 2:
                        end = sentence_break + 1

            chunks.append(text[start:end].strip())
            start = end - self.CHUNK_OVERLAP if end < len(text) else end

        return chunks

    def merge_extractions(self, extractions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge multiple chunk extractions into a single node/relationship set.
        """
        all_nodes: Dict[str, Dict[str, Any]] = {}
        all_rels: List[Dict[str, Any]] = []

        for data in extractions:
            if not data:
                continue

            for node in data.get("nodes", []):
                node_id = node.get("id", "")
                if not node_id:
                    continue

                # Normalize properties dict
                node.setdefault("properties", {})
                node_props = node["properties"]

                if node_id not in all_nodes:
                    all_nodes[node_id] = node
                else:
                    # Merge properties for duplicate IDs across chunks
                    all_nodes[node_id]["properties"].update(node_props)

            all_rels.extend(data.get("relationships", []))

        return {
            "nodes": list(all_nodes.values()),
            "relationships": all_rels
        }

    async def _generate_node_embedding(self, node: Dict[str, Any]) -> Optional[List[float]]:
        """
        Generate embedding for a node using the embedding service.
        """
        if not self.enable_embeddings or not self.embedding_service:
            return None

        node_id = node.get("id", "Unknown")
        props = node.get("properties", {})

        # Flatten for embedding service to ensure it sees 'content' and 'name'
        # node has 'id' but embedding service looks for 'name'
        entity_data = {
            "name": node_id,
            "label": node.get("label"),
            **props
        }

        loop = asyncio.get_event_loop()
        try:
            # Pass the flattened object for richer embeddings
            embedding = await loop.run_in_executor(
                None,
                lambda: self.embedding_service.embed_entity(entity_data)
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
        Process file content: Chunk -> Extract -> Merge (no DB writes).

        This is used by the UI for previewing what will be ingested.
        """
        logger.info(f"[INGEST] Processing file: {filename}, content length: {len(content)}")
        chunks = self.chunk_text(content)

        # Concurrent extraction using the dedicated service
        tasks = [
            self.extraction_service.extract_graph_from_chunk(chunk, i)
            for i, chunk in enumerate(chunks)
        ]
        extractions = await asyncio.gather(*tasks)
        logger.info(f"[INGEST] Extraction returned {len(extractions)} chunks: {extractions}")

        # Placeholder for future error reporting; currently handled in ExtractionService
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
        print("[INGEST] save_to_neo4j called", flush=True)
        logger.info(f"[SAVE] Received data structure: {type(data)}")
        if isinstance(data, dict):
            logger.info(f"[SAVE] Data keys: {list(data.keys())}")
            entities = data.get("nodes", []) or []
            relationships = data.get("relationships", []) or []
            logger.info(f"[SAVE] Found {len(entities)} nodes, {len(relationships)} relationships")
        nodes: List[Dict[str, Any]] = data.get("nodes", []) or []
        rels: List[Dict[str, Any]] = data.get("relationships", []) or []

        # GUARDRAIL: Filter out nodes without narrative content
        valid_nodes = []
        for node in nodes:
            props = node.get("properties", {})
            content = props.get("content")
            if not content or not str(content).strip():
                node_id = node.get("id", "Unknown")
                error_msg = f"Skipping entity '{node_id}': Missing narrative content."
                logger.error(f"[INGEST] {error_msg}")
                # Log to audit log asynchronously? save_to_neo4j is async.
                # But we don't want to slow down the loop too much.
                # Just keeping it in valid_nodes list.
                continue
            valid_nodes.append(node)
        
        nodes = valid_nodes

        nodes_saved = 0
        rels_saved = 0

        # Timestamp for this ingestion batch
        ingestion_timestamp = datetime.now(timezone.utc).isoformat()

        # Sanitize filename for use as source reference
        safe_filename = re.sub(r'[<>:"/\\|?*]', '_', filename) if filename else "unknown_source"

        # Optional mapping for future canon_id-aware features
        name_to_canon: Dict[str, str] = {}

        # --------------------------------------------------
        # 1. Generate embeddings (optional, concurrent)
        # --------------------------------------------------
        if self.enable_embeddings and self.embedding_service and nodes:
            embedding_tasks = []
            nodes_to_embed = []

            for node in nodes:
                nodes_to_embed.append(node)
                embedding_tasks.append(self._generate_node_embedding(node))

            if embedding_tasks:
                embeddings = await asyncio.gather(*embedding_tasks)

                for i, node in enumerate(nodes_to_embed):
                    embedding = embeddings[i]
                    if embedding:
                        node.setdefault("properties", {})
                        node["properties"]["embedding"] = embedding

        # --------------------------------------------------
        # 2. Prepare node batch with defaults + canon_id
        # --------------------------------------------------
        node_batch: List[Dict[str, Any]] = []

        for node in nodes:
            node_id = node.get("id", "")
            if not node_id:
                # Skip completely anonymous entities for now
                continue

            # Sanitize label
            label = node.get("label", "Entity")
            safe_label = self.sanitize_cypher_identifier(label, "Entity")

            # Ensure properties dict
            props = dict(node.get("properties") or {})

            # Generate stable-ish identity for this ingestion
            canon_id = props.get("canon_id") or f"ai-{uuid.uuid4().hex[:12]}"
            props["canon_id"] = canon_id
            name_to_canon[node_id] = canon_id

            # === Inject default values if missing ===
            if "confidence_level" not in props:
                props["confidence_level"] = DEFAULT_CONFIDENCE_LEVEL

            if "party_knowledge" not in props:
                props["party_knowledge"] = DEFAULT_PARTY_KNOWLEDGE

            if "source" not in props:
                props["source"] = safe_filename

            if "created_at" not in props:
                props["created_at"] = ingestion_timestamp

            # Always refresh updated_at on ingestion
            props["updated_at"] = ingestion_timestamp

            node_batch.append({
                "name": node_id,
                "label": safe_label,
                "props": props
            })

        # --------------------------------------------------
        # 3. Prepare relationship batch with sanitized types
        #    (still keyed by name for compatibility)
        # --------------------------------------------------
        rel_batch: List[Dict[str, Any]] = []

        for rel in rels:
            source_name = rel.get("source")
            target_name = rel.get("target")
            if not source_name or not target_name:
                continue

            rel_type = rel.get("type", "RELATED_TO").upper()
            safe_rel_type = self.sanitize_cypher_identifier(rel_type, "RELATED_TO")

            rel_batch.append({
                "source": source_name,
                "target": target_name,
                "type": safe_rel_type
            })

        # --------------------------------------------------
        # 4. Save Nodes (batch, grouped by label)
        # --------------------------------------------------
        if node_batch:
            nodes_by_label: Dict[str, List[Dict[str, Any]]] = {}
            for item in node_batch:
                lbl = item["label"]
                nodes_by_label.setdefault(lbl, []).append(item)

            for label, items in nodes_by_label.items():
                query = f"""
                UNWIND $items AS item
                MERGE (n:`{label}` {{name: item.name}})
                SET n += item.props
                SET n:Entity
                """
                try:
                    print("[INGEST] About to write to Neo4j", flush=True)
                    await self.db.execute(query, {"items": items})
                    print("[INGEST] Neo4j write complete", flush=True)
                    nodes_saved += len(items)
                except Exception as e:
                    await AuditLogger.log(
                        f"Error saving nodes batch for label {label}: {e}",
                        level=logging.ERROR
                    )

        # --------------------------------------------------
        # 5. Save Relationships (batch, grouped by type)
        # --------------------------------------------------
        if rel_batch:
            rels_by_type: Dict[str, List[Dict[str, Any]]] = {}
            for item in rel_batch:
                rtype = item["type"]
                rels_by_type.setdefault(rtype, []).append(item)

            for rtype, items in rels_by_type.items():
                query = f"""
                UNWIND $items AS item
                MATCH (a {{name: item.source}})
                MATCH (b {{name: item.target}})
                MERGE (a)-[r:`{rtype}`]->(b)
                """
                try:
                    print("[INGEST] About to write to Neo4j", flush=True)
                    await self.db.execute(query, {"items": items})
                    print("[INGEST] Neo4j write complete", flush=True)
                    rels_saved += len(items)
                except Exception as e:
                    await AuditLogger.log(
                        f"Error saving rels batch for type {rtype}: {e}",
                        level=logging.ERROR
                    )

        # --------------------------------------------------
        # 6. Link File Source node
        # --------------------------------------------------
        try:
            await self.db.execute(
                "MERGE (f:File {name: $filename})",
                {"filename": filename}
            )
        except Exception as e:
            await AuditLogger.log(
                f"Error creating File node: {e}",
                level=logging.ERROR
            )

        await AuditLogger.log(
            f"Ingested file '{filename}': {nodes_saved} nodes, {rels_saved} relationships.",
            level=logging.INFO
        )

        return {
            "nodes_saved": nodes_saved,
            "relationships_saved": rels_saved
        }