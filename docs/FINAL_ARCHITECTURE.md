# PilgrimAI — Final System Architecture

## 1. End-to-End Information Flow

```
USER INTERACTION (Web UI / API Client)
   │
   ▼
[ FastAPI Server ] ── /chat (POST)
   │
   ▼
[ PilgrimRAGService ] (backend/app/rag/chat.py)
   │
   ├── Step 1: QUERY PLANNING & ENTITY RESOLUTION
   │     └── QueryPlanner (backend/app/rag/query_planner.py)
   │           - Detects canonical temples via strict word-boundary regex
   │           - Classifies query intent into one of 5 deterministic retrieval routes:
   │               1. Targeted Fact (`targeted`)
   │               2. Complete Category (`complete_category`)
   │               3. Cross-Temple Aggregation (`cross_temple_aggregation`)
   │               4. Multi-Category Inquiry (`multi_category`)
   │               5. Broad Temple Overview (`broad_temple`)
   │
   ├── Step 2: RETRIEVAL ORCHESTRATION
   │     ├── Route 1 (Targeted):
   │     │     Dense (Qdrant) + Sparse (BM25) → Reciprocal Rank Fusion (RRF)
   │     │     → Cross-Encoder Reranking (`ms-marco-MiniLM-L-6-v2`) → Top-3 Parents
   │     ├── Route 2 (Complete Category):
   │     │     Direct KnowledgeRegistry Parent Resolution (Exhaustive, non-truncated)
   │     ├── Route 3 (Cross-Temple Aggregation):
   │     │     CrossTempleAggregationAgent (20 Temples dynamic evaluation)
   │     │     → CompletenessValidator (3-Tier availability partitioning)
   │     ├── Route 4 (Multi-Category):
   │     │     Multi-Category Context Builder (Separate category budgets, zero starvation)
   │     └── Route 5 (Broad Temple Overview):
   │           Priority-Budgeted Context Builder (Top categories, budget k ≤ 6)
   │
   ├── Step 3: CONTEXT ASSEMBLY & ANSWER SCOPING
   │     └── AnswerScopeController (backend/app/rag/answer_scope_controller.py)
   │           - Filters unrequested category chunks before prompt construction
   │           - Injects strict scoped instructions forbidding extraneous details
   │
   ├── Step 4: LOCAL LLM INFERENCE
   │     └── LocalLLMService (backend/app/rag/llm.py)
   │           - Ollama REST Client (`http://localhost:11434/api/generate`)
   │           - Certified Production Model: `qwen2.5:1.5b` (986 MB parameters)
   │
   └── Step 5: ANSWER GROUNDING VALIDATION & SANITIZATION
         └── AnswerGroundingValidator (backend/app/rag/answer_grounding_validator.py)
               - Detects and trims foreign temple mentions (0.0% cross-temple bleed)
               - Sanitizes unrequested category dumps
               - Enforces grounded refusal for fictitious or unsupported entities
   │
   ▼
CLIENT RESPONSE (JSON Payload / HTML Render)
```

---

## 2. Five Deterministic Retrieval Routes

| Retrieval Route | Trigger Condition | Execution Strategy | Context Strategy |
| :--- | :--- | :--- | :--- |
| **`targeted`** | Specific factual queries (timings, pricing, history, rules, single facility) | Hybrid Dense (Qdrant) + Sparse (BM25) + Cross-Encoder Reranker | Top-3 Parent Chunks (`FINAL_RERANK_TOP_K = 3`) with unrequested category filtering |
| **`complete_category`** | Exhaustive queries ("all sevas", "list all festivals", "all facilities") | Direct `KnowledgeRegistry` parent document retrieval | Full complete parent context (no Top-K truncation) |
| **`cross_temple_aggregation`** | Comparative/aggregator queries ("which temples have...", "temples without...") | Dynamic scan across all 20 temple source directories | Structured Markdown table with 3-tier partitioning (`CONFIRMED_AVAILABLE`, `CONFIRMED_UNAVAILABLE`, `INFORMATION_NOT_AVAILABLE`) |
| **`multi_category`** | Queries spanning 2+ categories ("accommodation and restaurants") | Hybrid search per category with section allocation | Multi-section structured context preventing starvation |
| **`broad_temple`** | General overviews ("tell me about X", "overview of X") | Multi-category synthesis | Budgeted priority context ($k \le 6$) |

---

## 3. Data & Index Layer
- **Source JSON Corpus**: 417 files across 20 temple directories.
- **Vector Database**: Qdrant local on-disk collection (`qdrant_db/`) indexing 1,578 parent chunks using `all-MiniLM-L6-v2` embeddings.
- **Sparse Inverted Index**: BM25 local on-disk index (`bm25_index/`) indexing 4,458 granular passage chunks.
- **Parent Store**: In-memory and on-disk parent store mapping chunk hashes to full category records.
