import os
import sys
import time
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Setup sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.rag.chat import PilgrimRAGService
from app.rag.guardrail import DEFAULT_REFUSAL_MESSAGE
from app.rag.rrf import reciprocal_rank_fusion
from app.rag.config import settings

def normalize_text(text: str) -> str:
    """Lowercase and clean text for deterministic evaluation."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r'[\r\n\t]+', ' ', text)
    text = re.sub(r'[^\w\s\:\.\,\-₹]', '', text)
    return text.strip()

def extract_key_tokens(text: str) -> List[str]:
    """Extract significant keywords, times, and numbers from ground truth."""
    if not text:
        return []
    words = re.findall(r'\b[a-zA-Z0-9\:\.\-₹]{2,}\b', text.lower())
    stopwords = {
        "the", "and", "for", "with", "this", "that", "from", "are", "temple",
        "located", "village", "district", "state", "includes", "check", "daily"
    }
    return [w for w in words if w not in stopwords]

class ComprehensiveEvaluator:
    """Executes multi-stage evaluation of the real production PilgrimAI RAG system."""

    def __init__(self):
        print("Initializing PilgrimRAGService for evaluation...")
        self.rag = PilgrimRAGService()
        self.embeddings = self.rag.embeddings
        self.qdrant = self.rag.qdrant_manager
        self.bm25 = self.rag.bm25_manager
        self.reranker = self.rag.reranker
        self.parent_store = self.rag.parent_store

    def evaluate_single_query(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Runs single question through all retrieval stages, isolation check, and Ollama generation."""
        q_id = item["id"]
        temple_id = item["temple_id"].lower()
        temple_name = item["temple_name"]
        query = item["question"]
        expected_answer = item.get("expected_answer", "")
        expected_sources = [s.replace("\\", "/").lower() for s in item.get("source_files", [])]
        is_answerable = item.get("answerable", True)

        result_record = {
            "id": q_id,
            "temple_id": temple_id,
            "temple_name": temple_name,
            "question": query,
            "category": item.get("category", "general"),
            "difficulty": item.get("difficulty", "medium"),
            "answerable": is_answerable,
            "expected_answer": expected_answer,
            "expected_sources": expected_sources,
            "stages": {}
        }

        # -------------------------------------------------------------
        # STAGE 1: Qdrant Dense Retrieval
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        qdrant_candidates = self.qdrant.search_candidates(query, self.embeddings, top_k=30)
        t_qdrant = (time.perf_counter() - t0) * 1000.0

        qdrant_temples = [str(d.metadata.get("temple", "")).lower() for d in qdrant_candidates]
        qdrant_sources = [str(d.metadata.get("path", "")).replace("\\", "/").lower() for d in qdrant_candidates]

        qdrant_top1_temple = temple_id in qdrant_temples[0] if qdrant_temples else False
        qdrant_top3_temple = any(temple_id in t for t in qdrant_temples[:3])
        qdrant_top5_temple = any(temple_id in t for t in qdrant_temples[:5])

        qdrant_top1_source = any(src in qdrant_sources[0] for src in expected_sources) if qdrant_sources and expected_sources else False
        qdrant_top3_source = any(any(src in s for src in expected_sources) for s in qdrant_sources[:3]) if expected_sources else False
        qdrant_top5_source = any(any(src in s for src in expected_sources) for s in qdrant_sources[:5]) if expected_sources else False

        result_record["stages"]["qdrant"] = {
            "latency_ms": t_qdrant,
            "top1_temple": qdrant_top1_temple,
            "top3_temple": qdrant_top3_temple,
            "top5_temple": qdrant_top5_temple,
            "top1_source": qdrant_top1_source,
            "top3_source": qdrant_top3_source,
            "top5_source": qdrant_top5_source,
            "top3_sources": qdrant_sources[:3],
            "top3_temples": qdrant_temples[:3]
        }

        # -------------------------------------------------------------
        # STAGE 2: BM25 Sparse Retrieval
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        bm25_candidates = self.bm25.search_candidates(query, top_k=30)
        t_bm25 = (time.perf_counter() - t0) * 1000.0

        bm25_temples = [str(d.metadata.get("temple", "")).lower() for d in bm25_candidates]
        bm25_sources = [str(d.metadata.get("path", "")).replace("\\", "/").lower() for d in bm25_candidates]

        bm25_top1_temple = temple_id in bm25_temples[0] if bm25_temples else False
        bm25_top3_temple = any(temple_id in t for t in bm25_temples[:3])
        bm25_top5_temple = any(temple_id in t for t in bm25_temples[:5])

        bm25_top1_source = any(src in bm25_sources[0] for src in expected_sources) if bm25_sources and expected_sources else False
        bm25_top3_source = any(any(src in s for src in expected_sources) for s in bm25_sources[:3]) if expected_sources else False
        bm25_top5_source = any(any(src in s for src in expected_sources) for s in bm25_sources[:5]) if expected_sources else False

        result_record["stages"]["bm25"] = {
            "latency_ms": t_bm25,
            "top1_temple": bm25_top1_temple,
            "top3_temple": bm25_top3_temple,
            "top5_temple": bm25_top5_temple,
            "top1_source": bm25_top1_source,
            "top3_source": bm25_top3_source,
            "top5_source": bm25_top5_source,
            "top3_sources": bm25_sources[:3],
            "top3_temples": bm25_temples[:3]
        }

        # -------------------------------------------------------------
        # STAGE 3: Hybrid RRF & Reranking
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        fused = reciprocal_rank_fusion(qdrant_candidates, bm25_candidates, top_k=30)
        t_hybrid = (time.perf_counter() - t0) * 1000.0

        fused_sources = [str(d.metadata.get("path", "")).replace("\\", "/").lower() for d in fused]
        fused_temples = [str(d.metadata.get("temple", "")).lower() for d in fused]
        fused_top1_source = any(src in fused_sources[0] for src in expected_sources) if fused_sources and expected_sources else False

        t0 = time.perf_counter()
        reranked = self.reranker.rerank(query, fused, top_k=6)
        t_rerank = (time.perf_counter() - t0) * 1000.0

        reranked_temples = [str(d.metadata.get("temple", "")).lower() for d in reranked]
        reranked_sources = [str(d.metadata.get("path", "")).replace("\\", "/").lower() for d in reranked]

        hybrid_top1_temple = temple_id in reranked_temples[0] if reranked_temples else False
        hybrid_top3_temple = any(temple_id in t for t in reranked_temples[:3])
        hybrid_top5_temple = any(temple_id in t for t in reranked_temples[:5])

        hybrid_top1_source = any(src in reranked_sources[0] for src in expected_sources) if reranked_sources and expected_sources else False
        hybrid_top3_source = any(any(src in s for src in expected_sources) for s in reranked_sources[:3]) if expected_sources else False
        hybrid_top5_source = any(any(src in s for src in expected_sources) for s in reranked_sources[:5]) if expected_sources else False

        rerank_improvement = (1 if hybrid_top1_source else 0) - (1 if fused_top1_source else 0)

        # Parent Context Resolution
        resolved_parents = []
        for d in reranked:
            p_id = d.metadata.get("parent_id")
            p_text = self.parent_store.get(p_id) if p_id else None
            if p_text:
                resolved_parents.append(p_id)

        result_record["stages"]["hybrid_rerank"] = {
            "hybrid_latency_ms": t_hybrid,
            "rerank_latency_ms": t_rerank,
            "top1_temple": hybrid_top1_temple,
            "top3_temple": hybrid_top3_temple,
            "top5_temple": hybrid_top5_temple,
            "top1_source": hybrid_top1_source,
            "top3_source": hybrid_top3_source,
            "top5_source": hybrid_top5_source,
            "rerank_improvement": rerank_improvement,
            "parent_contexts_resolved": len(resolved_parents),
            "top3_sources": reranked_sources[:3],
            "top3_temples": reranked_temples[:3]
        }

        # -------------------------------------------------------------
        # STAGE 4: Temple Isolation & Contamination Check
        # -------------------------------------------------------------
        top1_contam = False
        top3_contam = False
        top5_contam = False

        if is_answerable:
            if reranked_temples:
                top1_contam = not (temple_id in reranked_temples[0])
                top3_contam = any(not (temple_id in t) for t in reranked_temples[:3])
                top5_contam = any(not (temple_id in t) for t in reranked_temples[:5])

        result_record["stages"]["isolation"] = {
            "top1_contamination": top1_contam,
            "top3_contamination": top3_contam,
            "top5_contamination": top5_contam,
            "isolated": not top1_contam
        }

        # -------------------------------------------------------------
        # STAGE 5: End-to-End Ollama Generation & Answer Evaluation
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        rag_res = self.rag.answer(query)
        total_latency = (time.perf_counter() - t0) * 1000.0

        gen_answer = rag_res.get("answer", "")
        confidence = rag_res.get("confidence_score", 0.0)
        retrieved_chunks_count = rag_res.get("retrieved_chunks", 0)
        final_sources = rag_res.get("sources", [])

        # Evaluation of Answer
        norm_gen = normalize_text(gen_answer)
        is_refusal = (DEFAULT_REFUSAL_MESSAGE.lower() in norm_gen or
                      "could not find" in norm_gen or
                      "not available" in norm_gen or
                      "no information" in norm_gen or
                      "cannot answer" in norm_gen or
                      "does not provide" in norm_gen)

        hallucination_detected = False
        answer_grade = "INCORRECT"

        if not is_answerable:
            if is_refusal:
                answer_grade = "CORRECT"
            else:
                answer_grade = "HALLUCINATED"
                hallucination_detected = True
        else:
            if is_refusal:
                answer_grade = "REFUSED_ANSWERABLE"
            else:
                key_tokens = extract_key_tokens(expected_answer)
                if not key_tokens:
                    answer_grade = "CORRECT"
                else:
                    matches = [tok for tok in key_tokens if tok in norm_gen]
                    match_ratio = len(matches) / len(key_tokens)
                    if match_ratio >= 0.40:
                        answer_grade = "CORRECT"
                    elif match_ratio >= 0.20:
                        answer_grade = "PARTIAL"
                    else:
                        answer_grade = "INCORRECT"

        result_record["stages"]["generation"] = {
            "generated_answer": gen_answer,
            "confidence_score": confidence,
            "retrieved_chunks": retrieved_chunks_count,
            "final_sources": final_sources,
            "total_latency_ms": total_latency,
            "answer_grade": answer_grade,
            "hallucination_detected": hallucination_detected,
            "is_refusal": is_refusal
        }

        return result_record
