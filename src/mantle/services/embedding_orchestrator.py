# src/services/embedding_orchestrator.py
from typing import List, Optional
import logging

import google.generativeai as genai
from src.mantle.services.audit_log import AuditLogger

logger = logging.getLogger(__name__)


class EmbeddingOrchestrator:
    """
    Orchestrates calls to Gemini's embedding API.
    Encapsulates the direct LLM interaction for embedding generation.
    """
    MODEL_NAME = "models/text-embedding-004"
    EMBEDDING_DIMENSION = 768

    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        AuditLogger.log_sync(
            "EmbeddingOrchestrator: Initialized with Gemini text-embedding-004"
        )

    def generate_embedding(
        self,
        text: str,
        task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> Optional[List[float]]:
        """
        Generates an embedding vector for a single text string using the Gemini API.
        Includes strict validation to avoid silently propagating bad vectors.
        """
        if not text or not text.strip():
            return None

        try:
            result = genai.embed_content(
                model=self.MODEL_NAME,
                content=text,
                task_type=task_type,
            )

            # Defensive: handle possible response shape changes
            embedding = None

            if isinstance(result, dict):
                embedding = result.get("embedding")
            elif hasattr(result, "embedding"):
                embedding = getattr(result, "embedding", None)

            if not embedding or not isinstance(embedding, list):
                AuditLogger.log_sync(
                    f"EmbeddingOrchestrator: Invalid embedding format returned "
                    f"for text '{text[:60]}...'",
                    level=logging.ERROR,
                )
                return None

            if len(embedding) != self.EMBEDDING_DIMENSION:
                AuditLogger.log_sync(
                    f"EmbeddingOrchestrator: Incorrect embedding dimension "
                    f"{len(embedding)} (expected {self.EMBEDDING_DIMENSION})",
                    level=logging.ERROR,
                )
                return None

            return embedding

        except Exception as e:
            AuditLogger.log_sync(
                f"Embedding generation failed: {e}",
                level=logging.ERROR,
            )
            return None