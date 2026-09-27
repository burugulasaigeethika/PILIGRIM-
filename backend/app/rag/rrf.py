from typing import List, Dict
from langchain_core.documents import Document

from app.rag.config import settings

def reciprocal_rank_fusion(
    dense_candidates: List[Document],
    bm25_candidates: List[Document],
    top_k: int = settings.CANDIDATE_POOL_TOP_K,
    rrf_k: float = settings.RRF_K
) -> List[Document]:
    """
    Merges dense vector search results and BM25 keyword search results using
    Reciprocal Rank Fusion (RRF):
    
    RRF_Score(doc) = sum( 1 / (rrf_k + rank) )
    
    Returns a unified, deduplicated list of top_k candidate Documents.
    """
    doc_map: Dict[str, Document] = {}
    rrf_scores: Dict[str, float] = {}

    def get_chunk_key(doc: Document) -> str:
        return doc.metadata.get("chunk_id") or doc.page_content[:100]

    # Process Dense vector candidate ranks
    for rank, doc in enumerate(dense_candidates, start=1):
        key = get_chunk_key(doc)
        doc_map[key] = doc
        rrf_scores[key] = rrf_scores.get(key, 0.0) + (1.0 / (rrf_k + rank))

    # Process BM25 keyword candidate ranks
    for rank, doc in enumerate(bm25_candidates, start=1):
        key = get_chunk_key(doc)
        if key not in doc_map:
            doc_map[key] = doc
        rrf_scores[key] = rrf_scores.get(key, 0.0) + (1.0 / (rrf_k + rank))

    # Sort documents by RRF score descending
    sorted_keys = sorted(rrf_scores.keys(), key=lambda k: rrf_scores[k], reverse=True)

    fused_candidates = []
    for key in sorted_keys[:top_k]:
        doc = doc_map[key]
        meta = doc.metadata.copy()
        meta["rrf_score"] = float(rrf_scores[key])
        fused_candidates.append(Document(page_content=doc.page_content, metadata=meta))

    return fused_candidates
