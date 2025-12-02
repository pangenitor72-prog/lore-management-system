# src/agents/embedding_orchestrator.py
from typing import List, Optional
import google.generativeai as genai
from src.services.audit_log import AuditLogger
import logging

class EmbeddingOrchestrator:
    """
    Orchestrates calls to Gemini's embedding API.
    Encapsulates the direct LLM interaction for embedding generation.
    """
    MODEL_NAME = "models/text-embedding-004"
    EMBEDDING_DIMENSION = 768

    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        AuditLogger.log_sync("EmbeddingOrchestrator: Initialized with Gemini text-embedding-004")

    def generate_embedding(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> Optional[List[float]]:
        """
        Generates an embedding vector for a single text string using the Gemini API.
        """
        if not text or not text.strip():
            return None
        
        try:
            result = genai.embed_content(
                model=self.MODEL_NAME,
                content=text,
                task_type=task_type
            )
            return result['embedding']
        except Exception as e:
            AuditLogger.log_sync(f"Embedding generation failed: {e}", level=logging.ERROR)
            return None
