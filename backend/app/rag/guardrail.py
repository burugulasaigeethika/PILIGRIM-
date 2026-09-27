import logging
from typing import List, Tuple
from langchain_core.documents import Document

from app.rag.config import settings

logger = logging.getLogger(__name__)

DEFAULT_REFUSAL_MESSAGE = "I could not find this information in the temple knowledge base."

class RelevanceGuardrail:
    """
    Evaluates retrieval confidence score against configured threshold.
    Prevents LLM hallucination when retrieved context is irrelevant or low confidence.
    """

    def __init__(self, threshold: float = settings.RELEVANCE_THRESHOLD):
        self.threshold = threshold

    def evaluate_retrieval(
        self,
        reranked_docs: List[Document]
    ) -> Tuple[bool, float]:
        """
        Evaluates top document rerank score.
        Returns tuple: (is_relevant: bool, max_score: float)
        """
        if not reranked_docs:
            return False, -999.0

        top_doc = reranked_docs[0]
        max_score = top_doc.metadata.get("rerank_score", -999.0)

        if max_score < self.threshold:
            logger.info(
                f"[GUARDRAIL TRIGGERED] Top rerank score {max_score:.3f} < threshold {self.threshold:.3f}. Refusing answer."
            )
            return False, max_score

        return True, max_score
