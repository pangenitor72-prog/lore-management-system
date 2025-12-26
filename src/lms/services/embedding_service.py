# src/services/embedding_service.py
from typing import List, Optional
from src.lms.services.embedding_orchestrator import EmbeddingOrchestrator
from src.lms.services.audit_log import AuditLogger


class EmbeddingService:
    """
    Generates text embeddings using Google's Gemini embedding model via EmbeddingOrchestrator.
    
    These embeddings enable semantic similarity search - finding conceptually
    similar entities even when exact keywords don't match.
    """
    
    def __init__(self, api_key: str):
        """Initialize the embedding service with Gemini API key."""
        self.orchestrator = EmbeddingOrchestrator(api_key=api_key)
        AuditLogger.log_sync("EmbeddingService: Initialized with EmbeddingOrchestrator")
    
    def embed_text(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> Optional[List[float]]:
        """
        Generate an embedding vector for a single text string.
        
        Args:
            text: The text to embed (entity description, lore content, etc.)
            task_type: The type of task - affects how embeddings are optimized
                - RETRIEVAL_DOCUMENT: For documents/entities being stored
                - RETRIEVAL_QUERY: For search queries
                - SEMANTIC_SIMILARITY: For comparing two texts
                - CLASSIFICATION: For text classification
        
        Returns:
            List of floats (768-dimensional vector) or None if failed
        """
        return self.orchestrator.generate_embedding(text, task_type)
    
    def embed_query(self, query: str) -> Optional[List[float]]:
        """
        Generate an embedding for a search query.
        Uses RETRIEVAL_QUERY task type for optimal query matching.
        """
        return self.embed_text(query, task_type="RETRIEVAL_QUERY")
    
    def embed_entity(self, entity: dict) -> Optional[List[float]]:
        """
        Generate an embedding for an entity based on its combined text content.
        
        Combines name, description, and other text fields into a single
        representation for embedding.
        
        Args:
            entity: Dict with entity properties (name, description, type, etc.)
        
        Returns:
            768-dimensional embedding vector or None
        """
        # Build a rich text representation of the entity
        parts = []
        
        # Name is critical
        name = entity.get('name') or entity.get('canonical_name')
        if name:
            parts.append(f"Name: {name}")
        
        # Type/label provides context
        entity_type = entity.get('type') or entity.get('label')
        if entity_type:
            parts.append(f"Type: {entity_type}")
        
        # Description is the main content
        description = entity.get('description')
        if description:
            parts.append(f"Description: {description}")
        
        # Additional content if present
        content = entity.get('content')
        if content:
            parts.append(f"Content: {content}")
        
        # Aliases provide alternative names
        aliases = entity.get('aliases')
        if aliases:
            if isinstance(aliases, list):
                parts.append(f"Also known as: {', '.join(aliases)}")
            else:
                parts.append(f"Also known as: {aliases}")
        
        if not parts:
            return None
        
        combined_text = "\n".join(parts)
        return self.embed_text(combined_text, task_type="RETRIEVAL_DOCUMENT")
    
    def embed_batch(self, texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT") -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts.
        
        Note: Currently processes sequentially. Gemini's batch API could be
        used for higher throughput if needed.
        
        Args:
            texts: List of text strings to embed
            task_type: Task type for all embeddings
        
        Returns:
            List of embedding vectors (None for any that failed)
        """
        embeddings = []
        for text in texts:
            embedding = self.embed_text(text, task_type)
            embeddings.append(embedding)
        return embeddings
    
    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Returns value between -1 and 1, where 1 = identical direction.
        For normalized embeddings, this is equivalent to dot product.
        """
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        magnitude_a = sum(a * a for a in vec_a) ** 0.5
        magnitude_b = sum(b * b for b in vec_b) ** 0.5
        
        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0
        
        return dot_product / (magnitude_a * magnitude_b)
