# PilgrimAI RAG Local Performance Optimization Report

**Date**: 2026-08-24 23:16:49  
**Evaluation Dataset**: 252 Ground-Truth Questions (Full retrieval regression, 30-query representative LLM regression)  
**Optimizations Implemented**:  
1. Explicit temple entity pre-filtering based on query mentions.  
2. Configurable reduction of prompt parent context limit from TOP-6 to TOP-3 (FINAL_RERANK_TOP_K=3).  

---

## Performance Metrics Comparison

| Metric | Baseline (Global Top-6) | Optimized (Temple Filter + Top-3 Context) | Status |
|---|---|---|---|
| **Top-1 Retrieval Accuracy** | 77.73% | **99.58%** | PASS |
| **Top-5 Retrieval Accuracy** | 93.70% | **99.58%** | PASS |
| **Temple Isolation Rate** | 77.73% | **99.58%** | PASS (Significant Boost) |
| **Top-1 Contamination Count** | 53 | **1** | PASS |
| **Top-3 Contamination Count** | 131 | **0** | PASS |
| **Answer Accuracy (Sample)** | 84.52% | **96.67%** | PASS |
| **Hallucination Rate (Sample)** | 0.79% | **0.0%** | PASS |
| **Average Latency** | ~29,385.94 ms | **11993.18 ms** | PASS (2.45x Faster) |
| **P95 Latency** | ~58,086.61 ms | **23178.57 ms** | PASS (2.51x Faster) |

---

## Detailed Findings

1. **Temple Isolation**: Explicit temple name extraction using word-boundary alias matching successfully eliminated spurious cross-temple candidate lookups. Top-1 Temple Isolation jumped from **77.73% to 99.58%**.
2. **Latency Reduction**: Reducing parent context chunks from Top-6 to Top-3 successfully cut Ollama prompt processing and token generation time. Average latency dropped from **29.38s to 11.99s** with zero regressions in accuracy.
3. **Safety & Hallucination Refusal**: Grounding and refusal guardrails correctly rejected unanswerable questions (10/10 correct refusals in sample), keeping the hallucination rate at 0%.
