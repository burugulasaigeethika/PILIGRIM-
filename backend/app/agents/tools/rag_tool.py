"""
PilgrimAI - RAGTool Read-Only Facade (Phase B)

Provides a strictly controlled, read-only interface through which future specialist
agents communicate with the existing RAG pipeline, Qdrant on-disk vector store,
BM25 index, and verified temple datasets.

Guarantees:
- READ-ONLY access (zero mutation or re-indexing operations exposed).
- Normalizes internal LangChain documents into clean, strongly-typed RAGChunk models.
- Decouples specialist agents from raw database drivers and filesystem paths.
"""

import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from app.rag.chat import PilgrimRAGService
from app.api.chat import get_rag_service

logger = logging.getLogger(__name__)


class RAGChunk(BaseModel):
    """
    Normalized, read-only representation of a retrieved context chunk.
    Decouples agent consumption from internal LangChain Document structures.
    """
    model_config = ConfigDict(frozen=True, extra="allow")

    text: str = Field(..., description="Text content of the retrieved passage or parent context")
    temple: Optional[str] = Field(default=None, description="Associated canonical temple name if identified")
    category: Optional[str] = Field(default=None, description="Category of the passage (e.g., 'timings', 'sevas')")
    source: Optional[str] = Field(default=None, description="Relative source path (e.g., 'yadadri/timings.json')")
    score: Optional[float] = Field(default=None, description="Cross-encoder rerank relevance score")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional passage metadata")


class RAGTool:
    """
    Read-only facade exposing existing PilgrimRAGService and KnowledgeRegistry capabilities.
    Does NOT implement its own retrieval, embedding, reranking, or database logic.
    Delegates all queries to the frozen RAG foundation.
    """

    def __init__(self, rag_service: Optional[PilgrimRAGService] = None):
        if rag_service is not None:
            self._rag_service = rag_service
        else:
            self._rag_service = get_rag_service()

    @property
    def rag_service(self) -> PilgrimRAGService:
        """Internal reference to underlying RAG service."""
        return self._rag_service

    def retrieve(
        self,
        query: str,
        temple: Optional[str] = None,
        category: Optional[str] = None,
        top_k: int = 3
    ) -> List[RAGChunk]:
        """
        Retrieves candidate context chunks from the frozen hybrid RAG pipeline.
        Delegates to retrieve_with_metadata if temple/category constraints are given,
        or standard retrieve() otherwise.
        
        Returns normalized List[RAGChunk].
        """
        cleaned_query = query.strip()
        if not cleaned_query:
            return []

        try:
            if temple or category:
                raw_docs = self._rag_service.retrieve_with_metadata(
                    query=cleaned_query,
                    temple=temple,
                    category=category,
                    top_k=top_k
                )
            else:
                raw_docs = self._rag_service.retrieve(
                    query=cleaned_query,
                    top_k=top_k
                )

            chunks: List[RAGChunk] = []
            for doc in raw_docs:
                meta = doc.metadata or {}
                source_path = meta.get("path") or meta.get("source_file")
                rerank_score = meta.get("rerank_score")
                if rerank_score is not None:
                    try:
                        rerank_score = float(rerank_score)
                    except (ValueError, TypeError):
                        rerank_score = None

                chunks.append(
                    RAGChunk(
                        text=doc.page_content,
                        temple=meta.get("temple"),
                        category=meta.get("category"),
                        source=source_path,
                        score=rerank_score,
                        metadata=meta
                    )
                )
            return chunks

        except Exception as e:
            logger.error(f"RAGTool.retrieve failed for query '{query}': {e}", exc_info=True)
            raise

    def get_temple_category_data(self, temple: str, category: str) -> Optional[Any]:
        """
        Fetches the complete raw JSON dataset record for a specified temple and category.
        Read-only inspection via KnowledgeRegistry.
        """
        if not temple or not category:
            return None
        return self._rag_service.knowledge_registry.get_temple_raw_data(temple, category)

    def get_complete_parent_text(self, temple: str, category: str) -> Optional[str]:
        """
        Retrieves the unified complete parent text from the parent store if available.
        Used for complete-category and list queries without top-k truncation.
        """
        if not temple or not category:
            return None
        return self._rag_service.knowledge_registry.get_complete_parent(temple, category)

    def get_registered_temples(self) -> List[str]:
        """
        Returns the sorted list of all 20 canonical registered temples.
        """
        return self._rag_service.knowledge_registry.get_temples()

    def get_registered_categories(self) -> List[str]:
        """
        Returns the list of all registered category keys.
        """
        return self._rag_service.knowledge_registry.get_categories()

    def execute_grounded_rag(self, question: str) -> Dict[str, Any]:
        """
        Executes end-to-end grounded query execution through the frozen RAG pipeline.
        Returns the full RAG response dictionary (answer, sources, confidence, scope, plan).
        """
        cleaned_question = question.strip()
        if not cleaned_question:
            raise ValueError("Question cannot be empty.")
        return self._rag_service.answer(cleaned_question)
