"""
PilgrimAI - Latency Diagnostic Profiler for Factual Temple Queries (Phase P)
Target Query: "What are Yadadri temple timings?"
"""

import sys
import time
from pathlib import Path

root_dir = Path(__file__).resolve().parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.router import AgentRouter
from app.agents.state import AgentState
from app.rag.chat import PilgrimRAGService

def profile():
    query = "What are Yadadri temple timings?"
    print(f"\n--- Profiling Query: '{query}' ---")
    
    # 1. Router Latency
    router = AgentRouter()
    t0 = time.perf_counter()
    decision = router.route(query)
    t_router = (time.perf_counter() - t0) * 1000.0
    print(f"1. AgentRouter: {t_router:.2f} ms (Selected Agent: {decision.selected_agent})")
    
    # 2. RAG Service Initialization
    t0 = time.perf_counter()
    rag_service = PilgrimRAGService()
    t_init = (time.perf_counter() - t0) * 1000.0
    print(f"2. RAG Service Init/Load: {t_init:.2f} ms")
    
    # 3. Component level measurement inside RAG
    # 3a. Query Planner / Intent
    t0 = time.perf_counter()
    plan = rag_service.query_planner.plan(query)
    t_plan = (time.perf_counter() - t0) * 1000.0
    print(f"3. Query Planner: {t_plan:.2f} ms")
    
    # 3b. Embedding Generation
    t0 = time.perf_counter()
    query_vector = rag_service.embeddings.embed_query(query)
    t_embed = (time.perf_counter() - t0) * 1000.0
    print(f"4. Dense Embedding (PyTorch/MiniLM): {t_embed:.2f} ms")
    
    # 3c. Qdrant Dense Search
    t0 = time.perf_counter()
    dense_results = rag_service.qdrant_manager.search_candidates(query, rag_service.embeddings, top_k=20)
    t_qdrant = (time.perf_counter() - t0) * 1000.0
    print(f"5. Qdrant Dense Retrieval: {t_qdrant:.2f} ms (Found {len(dense_results)} hits)")
    
    # 3d. BM25 Sparse Search
    t0 = time.perf_counter()
    bm25_results = rag_service.bm25_manager.search_candidates(query=query, top_k=20)
    t_bm25 = (time.perf_counter() - t0) * 1000.0
    print(f"6. BM25 Sparse Search: {t_bm25:.2f} ms (Found {len(bm25_results)} hits)")
    
    # 3e. RRF Fusion
    t0 = time.perf_counter()
    from app.rag.rrf import reciprocal_rank_fusion
    fused_results = reciprocal_rank_fusion(dense_results, bm25_results, top_k=20)
    t_rrf = (time.perf_counter() - t0) * 1000.0
    print(f"7. RRF Rank Fusion: {t_rrf:.2f} ms (Fused {len(fused_results)} hits)")
    
    # 3f. Cross-Encoder Reranking
    t0 = time.perf_counter()
    reranked_results = rag_service.reranker.rerank(query, fused_results, top_k=3)
    t_rerank = (time.perf_counter() - t0) * 1000.0
    print(f"8. Cross-Encoder Reranker (CPU): {t_rerank:.2f} ms")
    
    # 3g. Context Construction & Overall answer_query Execution
    t0 = time.perf_counter()
    ans, chunks, srcs, score = rag_service.answer_query(query)
    t_full_rag = (time.perf_counter() - t0) * 1000.0
    print(f"9. Full RAG answer_query (Context + Ollama LLM generation): {t_full_rag:.2f} ms ({t_full_rag/1000:.2f}s)")
    
    print(f"\n--- Total End-to-End Query Latency: {t_router + t_full_rag:.2f} ms ({(t_router + t_full_rag)/1000:.2f}s) ---")
    print(f"Answer snippet: {str(ans)[:120]}...\n")

if __name__ == "__main__":
    profile()
