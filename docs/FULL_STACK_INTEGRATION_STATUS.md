# PilgrimAI — Full-Stack Integration Architecture & Status

## 1. System Architecture & Components

```
CLIENT (Browser)
    │
    │  HTTP / REST (Port 8000)
    ▼
FastAPI Application (backend/app/main.py)
    ├── Static UI Mount (/ & /static) ── HTML5 / CSS3 / Vanilla JS Interface
    ├── Health Endpoint (/health)
    └── Chat Router (/chat - POST)
            │
            ▼
      PilgrimRAGService (backend/app/rag/chat.py)
            │
            ├── 1. QueryPlanner (Deterministic Regex & Word Boundaries)
            │       ├── Targeted Fact Mode
            │       ├── Complete Category Mode
            │       ├── Cross-Temple Aggregation Mode
            │       ├── Multi-Category Mode
            │       └── Broad Temple Overview Mode
            │
            ├── 2. Retrieval Engines (100% Offline / Local)
            │       ├── Qdrant Vector DB (Local on-disk: qdrant_db/)
            │       ├── BM25 Sparse Index (Local on-disk: bm25_index/)
            │       ├── Cross-Encoder Reranker (ms-marco-MiniLM-L-6-v2)
            │       └── KnowledgeRegistry (Complete Parent Context Store)
            │
            ├── 3. ContextBuilder & CompletenessValidator
            │       └── Strict 3-Tier Availability Partitioning
            │
            ├── 4. AnswerScopeController (Context Filtering & Scoped Prompts)
            │
            ├── 5. Local Ollama LLM Service (qwen2.5:1.5b on localhost:11434)
            │
            └── 6. AnswerGroundingValidator (Cross-Temple Bleed & Hallucination Sanitizer)
```

---

## 2. Configuration & Integration Contracts

| Property | Value / Definition | Status |
| :--- | :--- | :---: |
| **Backend Host & Port** | `127.0.0.1:8000` | Configured |
| **Frontend Host & Port** | Served directly via FastAPI static mount on `http://127.0.0.1:8000/` | Configured |
| **Chat Endpoint** | `POST /chat` | Active |
| **Request Schema** | `{"question": "string"}` | Validated |
| **Response Schema** | `{"question": "string", "answer": "string", "retrieved_chunks": int, "sources": list, "confidence_score": float}` | Validated |
| **CORS Middleware** | `allow_origins=["*"]`, `allow_methods=["*"]`, `allow_headers=["*"]` | Active |
| **Production Model** | `qwen2.5:1.5b` (Local Ollama) | Verified |
| **Ollama Endpoint** | `http://localhost:11434` | Active |
| **Vector DB** | `qdrant_db/` (Local on-disk collection) | Active |
| **Sparse Index** | `bm25_index/` (Local on-disk index) | Active |
