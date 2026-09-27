import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file located at root workspace directory
env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

def _sanitize_path(val: str) -> str:
    """Sanitize environment-provided filesystem path by stripping quotes and normalizing."""
    if not val:
        return val
    cleaned = val.strip().strip("'\"")
    return os.path.normpath(cleaned)


class Settings:
    """Application configuration for local offline PilgrimAI RAG pipeline."""

    # Project root directory (d:\PiligrimAI -c)
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent.parent

    # Dataset directory defaults to project root
    _raw_dataset_dir = _sanitize_path(os.getenv("DATASET_DIR", str(PROJECT_ROOT)))
    DATASET_DIR: str = str((PROJECT_ROOT / _raw_dataset_dir).resolve()) if not os.path.isabs(_raw_dataset_dir) else _raw_dataset_dir

    # Local Qdrant Storage Directory (absolute path)
    _raw_qdrant_dir = _sanitize_path(os.getenv("QDRANT_DIR", "./qdrant_db"))
    QDRANT_DIR: str = str((PROJECT_ROOT / _raw_qdrant_dir).resolve()) if not os.path.isabs(_raw_qdrant_dir) else _raw_qdrant_dir

    # Local BM25 Index Directory (absolute path)
    _raw_bm25_dir = _sanitize_path(os.getenv("BM25_DIR", "./bm25_index"))
    BM25_DIR: str = str((PROJECT_ROOT / _raw_bm25_dir).resolve()) if not os.path.isabs(_raw_bm25_dir) else _raw_bm25_dir

    # Local HuggingFace Embedding model
    EMBEDDING_MODEL: str = os.getenv(
        "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )

    # Local Cross-Encoder Reranker model
    RERANKER_MODEL: str = os.getenv(
        "RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
    )

    # Local Ollama LLM configuration
    LLM_MODEL: str = os.getenv("LLM_MODEL", "qwen2.5:1.5b")
    LOCAL_LLM_MODEL: str = os.getenv("LOCAL_LLM_MODEL", LLM_MODEL)
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_TIMEOUT: int = int(os.getenv("OLLAMA_TIMEOUT", "180"))

    # Chunking settings (Parent / Child)
    CHILD_CHUNK_SIZE: int = int(os.getenv("CHILD_CHUNK_SIZE", "300"))
    CHILD_CHUNK_OVERLAP: int = int(os.getenv("CHILD_CHUNK_OVERLAP", "50"))

    # Configurable List-Based File Types supporting complete-list retrieval
    LIST_BASED_FILES: set = {
        "sevas.json", "festivals.json", "prasadam.json", "prasadams.json",
        "facilities.json", "restaurants.json", "donations.json",
        "nearby_attractions.json", "sub_temples.json"
    }

    # Retrieval settings
    CANDIDATE_POOL_TOP_K: int = int(os.getenv("CANDIDATE_POOL_TOP_K", "30"))
    FINAL_RERANK_TOP_K: int = int(os.getenv("FINAL_RERANK_TOP_K", "3"))
    RRF_K: float = float(os.getenv("RRF_K", "60.0"))

    # Relevance guardrail threshold
    RELEVANCE_THRESHOLD: float = float(os.getenv("RELEVANCE_THRESHOLD", "-3.0"))

settings = Settings()
