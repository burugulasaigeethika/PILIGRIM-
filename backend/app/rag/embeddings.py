import logging
from typing import List, Any
from app.rag.config import settings

logger = logging.getLogger(__name__)

class LocalEmbeddings:
    """Wrapper around SentenceTransformer running 100% locally on CPU/GPU without API dependencies."""

    def __init__(self, model_name: str = settings.EMBEDDING_MODEL):
        self.model_name = model_name
        logger.info(f"Initializing Local SentenceTransformers Model ('{model_name}')...")
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Compute vector embeddings for a list of document strings."""
        if not texts:
            return []
        embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return embeddings.tolist()

    def embed_query(self, text: str) -> List[float]:
        """Compute vector embedding for a single user query."""
        if not text:
            return []
        embedding = self.model.encode(text, convert_to_numpy=True, show_progress_bar=False)
        return embedding.tolist()

def get_embeddings_model() -> LocalEmbeddings:
    """Initialize and return local embeddings instance."""
    return LocalEmbeddings()
