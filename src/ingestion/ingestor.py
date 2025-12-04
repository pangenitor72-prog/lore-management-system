from src.db.neo4j_adapter import Neo4jDatabase
import asyncio
import os
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
        embedding_service: EmbeddingService
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

    def merge_extractions(self, extractions: List[Dict]) -> Dict[str, Any]:
        """Merge multiple chunk extractions."""
        all_nodes = {}
        all_rels = []
        
        for data in extractions:
            if not data: continue
            
            for node in data.get("nodes", []):
                node_id = node.get("id", "")
                if node_id:
                    if node_id not in all_nodes:
                        all_nodes[node_id] = node
                    else:
                        # Merge properties
                        all_nodes[node_id]["properties"].update(node.get("properties", {}))
            
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
            await AuditLogger.log(f"Embedding generation failed for node {node_id}: {str(e)}", level=logging.ERROR)
            return None

    async def process_file_content(self, filename: str, content: str) -> Dict[str, Any]:
        """
        Process file content: Chunk -> Extract -> Return Data (does not save yet).
        Useful for UI preview.
        """
        chunks = self.chunk_text(content)
        
        # Concurrent extraction using the dedicated service
        tasks = [self.extraction_service.extract_graph_from_chunk(chunk, i) for i, chunk in enumerate(chunks)]
        extractions = await asyncio.gather(*tasks)
        
        # Check for empty results which might indicate errors (already logged in the service)
        errors = []
        
        merged_data = self.merge_extractions(extractions)
        return {
            "filename": filename,
            "data": merged_data,
            "chunks_count": len(chunks),
            "errors": errors 
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
        nodes = data.get("nodes", [])
        rels = data.get("relationships", [])
        nodes_saved = 0
        rels_saved = 0
        
        # Timestamp for this ingestion batch
        ingestion_timestamp = datetime.now(timezone.utc).isoformat()
        
        # Sanitize filename for use as source reference
        safe_filename = re.sub(r'[<>:"/\\|?*]', '_', filename) if filename else "unknown_source"
        
        # 1. Prepare Nodes with Embeddings
        # Generate embeddings concurrently for better performance
        if self.enable_embeddings and self.embedding_service:
            embedding_tasks = []
            nodes_to_embed = []
            
            for node in nodes:
                nodes_to_embed.append(node)
                embedding_tasks.append(self._generate_node_embedding(node))
            
            if embedding_tasks:
                # Correctly gather results from embedding_tasks
                embeddings = await asyncio.gather(*embedding_tasks)
                
                # Assign embeddings back to nodes
                for i, node in enumerate(nodes_to_embed):
                    if embeddings[i]:
                        if "properties" not in node:
                            node["properties"] = {}
                        node["properties"]["embedding"] = embeddings[i]

        # Prepare batch data for nodes with default value injection
        node_batch = []
        for node in nodes:
            node_id = node.get("id", "")
if not node_id:
    continue

# Generate stable unique identity for ingested entities
canon_id = node.get("canon_id") or f"ai-{uuid.uuid4().hex[:12]}"
            
            # Sanitize label using the proper identifier sanitizer
            label = node.get("label", "Entity")
            safe_label = self.sanitize_cypher_identifier(label, "Entity")
            
            # Get existing properties
            # Inject canon_id for identity consistency
            props["canon_id"] = canon_id
            
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
            
            node_batch.append({
                "name": node_id,
                "label": safe_label,
                "props": props
            })

        # Prepare batch data for relationships with sanitization
        rel_batch = []
        for rel in rels:
            source = rel.get("source")
            target = rel.get("target")
            
            # Sanitize relationship type
            rel_type = rel.get("type", "RELATED_TO").upper()
            safe_rel_type = self.sanitize_cypher_identifier(rel_type, "RELATED_TO")
            
            if source and target:
                rel_batch.append({
                    "source": source,
                    "target": target,
                    "type": safe_rel_type
                })

      # 1. Save Nodes (Batch)
        if node_batch:
            # Group by label to optimize MERGE
            nodes_by_label = {}
            for item in node_batch:
                lbl = item["label"]
                if lbl not in nodes_by_label:
                    nodes_by_label[lbl] = []
                nodes_by_label[lbl].append(item)

            for label, items in nodes_by_label.items():
                query = f"""
                UNWIND $items AS item
                MERGE (n:`{label}` {{name: item.name}})
                SET n += item.props
                SET n:Entity
                """
                try:
                    await self.db.execute(query, {"items": items})
                    nodes_saved += len(items)
                except Exception as e:
                    await AuditLogger.log(
                        f"Error saving nodes batch for label {label}: {e}",
                        level=logging.ERROR
                    )

       # 2. Save Relationships (Batch)
        if rel_batch:
            # Group by type
            rels_by_type = {}
            for item in rel_batch:
                rtype = item["type"]
                if rtype not in rels_by_type:
                    rels_by_type[rtype] = []
                rels_by_type[rtype].append(item)

            for rtype, items in rels_by_type.items():
                query = f"""
                UNWIND $items AS item
                MATCH (a {{name: item.source}})
                MATCH (b {{name: item.target}})
                MERGE (a)-[r:`{rtype}`]->(b)
                """
                try:
                    await self.db.execute(query, {"items": items})
                    rels_saved += len(items)
                except Exception as e:
                    await AuditLogger.log(
                        f"Error saving rels batch for type {rtype}: {e}",
                        level=logging.ERROR
                    )
        # 3. Link File Source
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
