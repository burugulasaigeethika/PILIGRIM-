# PilgrimAI Optimized RAG System Baseline

This document serves as the verified baseline of the PilgrimAI Telangana Temples RAG system. It freezes the state of the optimized system configuration, architecture, and metrics prior to implementing any agent integrations.

---

## 1. System Architecture

The PilgrimAI RAG system operates offline on local hardware, using the following pipeline:
```
User Query 
   │
   ├── [Temple Entity Extractor] ──► Extracts explicit temple mention (canonical mapping)
   │
   ├── [Hybrid Retriever]
   │     ├── Dense Vector Search (Qdrant) ──► Restricted to detected temple if matched
   │     └── Sparse Keyword Search (BM25)  ──► Restricted to detected temple if matched
   │
   ├── [Reciprocal Rank Fusion (RRF)] ──► Merges candidates: score = 1 / (60 + rank)
   │
   ├── [Cross-Encoder Reranker] ──► Reranks candidates using ms-marco-MiniLM-L-6-v2
   │
   ├── [Relevance Guardrail] ──► Refuses queries with low relevance scores
   │
   ├── [Parent Context Resolver] ──► Resolves chunk IDs to parent document segments (Max 3)
   │
   └── [Local LLM (Ollama)] ──► qwen2.5:1.5b generates deterministic, grounded answer
```

---

## 2. Configuration & Parameter Settings

Configured in [config.py](file:///D:/PiligrimAI%20-c/backend/app/rag/config.py):
- **Candidate Pool Size (`CANDIDATE_POOL_TOP_K`)**: `30`
- **Reranker Context Limit (`FINAL_RERANK_TOP_K`)**: `3` (Optimized from 6 to reduce Ollama prompt size and generation latency)
- **RRF K Constant (`RRF_K`)**: `60.0`
- **Relevance Threshold (`RELEVANCE_THRESHOLD`)**: `-3.0`
- **Ollama Context Window (`num_ctx`)**: `2048`
- **Ollama Temperature (`temperature`)**: `0.0` (Deterministic)

---

## 3. Temple Filtering Implementation

Implemented inside [chat.py](file:///D:/PiligrimAI%20-c/backend/app/rag/chat.py#L38-L74):
- Detects explicit temple mentions using word-boundary alias matching (20 known temples).
- When a temple name is explicitly matched in the query, candidate searches in Qdrant and BM25 are constrained to metadata matching that temple.
- If no temple name is matched, global query matching across all temples is preserved.

---

## 4. Current Evaluation & Performance Metrics

Verified metrics from the optimization regression runs:

| Metric | Verified Baseline |
|---|---|
| **Top-1 Retrieval Accuracy** | `99.58%` |
| **Top-5 Retrieval Accuracy** | `99.58%` |
| **Temple Isolation Rate** | `99.58%` |
| **Top-1 Contamination Count** | `1 / 238` |
| **Top-3 Contamination Count** | `0` |
| **Answer Accuracy (30-Query Sample)** | `96.67%` |
| **Sample Hallucination Rate** | `0.00%` |
| **Average End-to-End Latency** | `11,993 ms` |
| **P95 Latency** | `23,179 ms` |
| **Unit Tests Status** | `7 / 7 PASSED` |

---

## 5. Storage & Model Environments

- **Qdrant Vector DB Location**: `D:\PiligrimAI -c\qdrant_db\`
- **BM25 okapi Index Location**: `D:\PiligrimAI -c\bm25_index\`
- **Ollama Model Directory**: `D:\Ollama\models\`
- **Ollama Models**:
  - `qwen2.5:1.5b` (Primary LLM)
  - `qwen2.5:7b` (Secondary LLM)
- **HuggingFace Local Cache Directory**: Defaults in Virtual Environment `D:\temple rag 1\.venv\`

---

## 6. Key Files Involved

1. [chat.py](file:///D:/PiligrimAI%20-c/backend/app/rag/chat.py) — Core local RAG service logic (`retrieve` and `answer` endpoints).
2. [config.py](file:///D:/PiligrimAI%20-c/backend/app/rag/config.py) — Configuration setting and parameters.
3. [test_local_rag.py](file:///D:/PiligrimAI%20-c/tests/test_local_rag.py) — Regression unit tests.
4. [run_regression.py](file:///D:/PiligrimAI%20-c/evaluation/optimization_results/run_regression.py) — Auto-regression benchmark script.

---

## 7. Baseline Verification Statement

> [!IMPORTANT]
> This freezes the verified baseline state of the optimized PilgrimAI RAG system. This configuration (`FINAL_RERANK_TOP_K=3` and word-boundary temple extraction) must not be modified during the upcoming agent implementation. Any future modifications to the retrieval behavior must be benchmarked against this report.
