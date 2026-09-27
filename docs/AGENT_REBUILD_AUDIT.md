# PilgrimAI: Agent Rebuild Architecture and Code Audit

**Date:** September 17, 2026  
**Project:** PilgrimAI: A RAG-Based Multi-Agent Assistant for Smart Pilgrimage  
**Workspace:** `d:\pligrim ai new`  
**Audit Type:** Read-Only Pre-Rebuild Architecture & Code Audit  
**Status:** Audit Complete — Ready for Phased Agent Rebuild  

---

## 1. Current Project Structure

The workspace contains an end-to-end local offline RAG system with a FastAPI backend, embedded HTML/JS frontend, on-disk vector database, sparse inverted index, and 20 raw temple JSON knowledge bases.

```text
d:\pligrim ai new\
├── .env                              # Environment configuration (paths, models, thresholds)
├── .env.example                      # Reference environment template
├── requirements.txt                  # Python dependencies (FastAPI, Qdrant, BM25, SentenceTransformers, etc.)
│
├── backend\
│   └── app\
│       ├── __init__.py
│       ├── main.py                   # FastAPI app entry point (routes, CORS, static mounts)
│       ├── api\
│       │   ├── __init__.py
│       │   └── chat.py               # POST /chat endpoint (direct PilgrimRAGService invocation)
│       ├── rag\                      # FROZEN 100% Local RAG Pipeline
│       │   ├── __init__.py
│       │   ├── config.py             # Settings & environment path resolvers
│       │   ├── chat.py               # PilgrimRAGService (Universal retrieval & generation engine)
│       │   ├── vectordb.py           # LocalQdrantManager (on-disk parent/child vector storage)
│       │   ├── bm25.py               # LocalBM25Manager (on-disk sparse inverted index)
│       │   ├── rrf.py                # Reciprocal Rank Fusion (fusing dense & sparse candidates)
│       │   ├── reranker.py           # LocalCrossEncoderReranker (ms-marco-MiniLM-L-6-v2)
│       │   ├── embeddings.py         # HuggingFace MiniLM-L6-v2 local embedder
│       │   ├── llm.py                # LocalLLMService (Ollama REST client for Qwen2.5:1.5b)
│       │   ├── guardrail.py          # RelevanceGuardrail (-3.0 threshold confidence gating)
│       │   ├── prompt.py             # Chat prompt templates
│       │   ├── query_planner.py      # QueryPlanner (intent classification & regex entity detection)
│       │   ├── category_registry.py   # CategoryRegistry (21 canonical temple categories)
│       │   ├── knowledge_registry.py  # KnowledgeRegistry (filesystem index across 20 temples)
│       │   ├── completeness_validator.py # CompletenessValidator (3-tier availability evaluator)
│       │   ├── context_builder.py    # ContextBuilder (scoped markdown context assembly)
│       │   ├── answer_scope_controller.py # AnswerScopeController (category whitelist/blacklist)
│       │   ├── answer_grounding_validator.py # Grounding & hallucination sanitizer
│       │   ├── loader.py             # TempleDatasetLoader
│       │   ├── parser.py             # JSONToDocumentParser
│       │   ├── chunker.py            # Parent/Child chunking logic
│       │   ├── ingest.py             # Ingestion orchestrator
│       │   └── utils.py              # String formatting helpers
│       ├── agents\                   # CURRENT AGENT LAYER (To Be Rebuilt)
│       │   ├── __init__.py           # Exports TempleInformationAgent, CrossTempleAggregationAgent
│       │   ├── temple_information_agent.py # Standalone, uncoordinated info wrapper
│       │   ├── cross_temple_aggregation_agent.py # 20-temple dynamic scanner
│       │   └── prompts\
│       │       ├── __pycache__\
│       │       └── temple_information_prompt.py # System prompts & user templates
│       └── static\                   # Embedded Frontend Web UI
│           ├── index.html            # Single-page chat interface
│           ├── app.js                # Frontend chat client & event listeners
│           └── style.css             # UI styling
│
├── qdrant_db\                        # FROZEN Local On-Disk Vector Database
│   ├── collection\                   # Qdrant collection segments and index files
│   ├── meta.json                     # Database metadata
│   └── parent_store.json             # 865 KB on-disk parent chunk store (1,578 parents)
│
├── bm25_index\                       # FROZEN Local Sparse Inverted Index
│   └── bm25_store.pkl                # 2.73 MB serialized BM25 index (4,458 child passages)
│
├── <20 Temple Directories>\           # FROZEN Source Knowledge Base (417 JSON files)
│   ├── yadadri\                      # e.g., timings.json, sevas.json, facilities.json, etc.
│   ├── basara\
│   ├── badrachalam\
│   ├── srisaila\
│   ├── dharmapuri\
│   ├── vemulavada\
│   └── ... (14 other temples)
│
├── tests\                            # Test Suite (16 test files)
│   ├── test_local_rag.py
│   ├── test_temple_information_agent.py
│   ├── test_final_production_smoke.py
│   ├── test_query_planner.py
│   ├── test_cross_temple_aggregation.py
│   └── ...
│
├── evaluation\                       # Evaluation Benchmark & Datasets
│   ├── evaluation_dataset.json       # 198 KB golden evaluation dataset
│   ├── run_evaluation.py             # Benchmark runner
│   ├── metrics.json                  # Performance metrics
│   └── ...
│
└── docs\                             # Architecture & Audit Documentation
    ├── FINAL_ARCHITECTURE.md
    ├── PRODUCTION_READINESS_CHECKLIST.md
    └── ...
```

---

## 2. Existing RAG Architecture

The existing RAG pipeline is a 100% offline, locally hosted, hybrid dense-sparse retrieval system.

1. **Service Location:**  
   `backend/app/rag/chat.py` defines the primary engine: `PilgrimRAGService`.
2. **How RAG is Called:**  
   Called synchronously via `service.answer(question: str) -> Dict[str, Any]` or `service.retrieve(query: str, top_k: int) -> List[Document]`.
3. **Public Interface for Future Agents:**  
   `PilgrimRAGService` (or a dedicated `RAGTool` facade wrapping `PilgrimRAGService` methods) providing:
   - `retrieve(query, top_k)`: Dense + BM25 hybrid candidate search + Cross-Encoder reranking.
   - `retrieve_with_metadata(query, temple, category, top_k)`: Scoped metadata-filtered search.
   - `answer(question)`: Grounded, scoped end-to-end RAG answer generation.
   - Access to `KnowledgeRegistry` for raw verified temple category data and complete parent passages.
4. **Configured Local LLM:**  
   - Ollama instance running locally at `http://localhost:11434`
   - Model: `qwen2.5:1.5b` (986 MB parameters, 0.0 temperature, 2048 context window)
   - Fallback/Installed alternative: `qwen2.5:7b` (verified present in local Ollama repository)
5. **Qdrant Location:**  
   Local on-disk directory at `./qdrant_db` (resolves to `d:\pligrim ai new\qdrant_db`), holding 1,578 parent chunks and vectors generated by `sentence-transformers/all-MiniLM-L6-v2`.
6. **BM25 Location:**  
   Local on-disk directory at `./bm25_index/bm25_store.pkl` (resolves to `d:\pligrim ai new\bm25_index`), indexing 4,458 granular child passages.
7. **Reranker Configuration:**  
   Cross-Encoder model `cross-encoder/ms-marco-MiniLM-L-6-v2` loaded locally via `sentence_transformers`.
8. **Dataset / Source JSON Location:**  
   20 temple subdirectories located at project root `d:\pligrim ai new\<temple_name>\*.json` (also mapped to `settings.DATASET_DIR = "d:\\PiligrimAI -c"` in `.env`).
9. **RAG Operational Ability:**  
   **CONFIRMED WORKING.** The RAG pipeline independently answers factual queries with verified sources, high confidence, and zero hallucination.
10. **Existing RAG Tests:**  
    `tests/test_local_rag.py`, `tests/test_query_planner.py`, `tests/test_context_completeness.py`, `tests/test_answer_scope_controller.py`, `tests/test_final_production_smoke.py`.

---

## 3. RAG Verification Result

An independent execution of the existing RAG pipeline was conducted using a factual question without modifying any code:

* **Query Tested:** `"What are the timings of Yadadri temple?"`
* **Execution Status:** **SUCCESS (Zero Errors)**
* **Retrieval Mode:** `targeted` (Hybrid Qdrant dense + BM25 sparse + Cross-Encoder rerank)
* **Confidence Score:** `8.7388` (Threshold: `-3.0`)
* **Retrieved Chunks:** 3 chunks resolved to parent context
* **Identified Sources:** `["yadadri/faq.json", "yadadri/timings.json"]`
* **QueryPlan & AnswerScope:**
  - Detected Temple: `Yadadri`
  - Detected Category: `timings`
  - Prohibited Categories: 20 other non-requested categories strictly suppressed
* **Generated Answer:**
  > *"The temple is open daily from 4:00 AM to 9:45 PM. It is closed for a brief afternoon rest period between 3:00 PM and 4:00 PM."*
* **Grounding Validation:** `is_valid: True`, `temple_scope_valid: True`, `category_scope_valid: True`, `violations: []`
* **Conclusion:** **The RAG foundation is 100% operational and healthy.**

---

## 4. Existing Agent Files

The following agent files currently exist in `backend/app/agents/`:

1. `backend/app/agents/__init__.py` (222 bytes)
2. `backend/app/agents/temple_information_agent.py` (4,609 bytes)
3. `backend/app/agents/cross_temple_aggregation_agent.py` (7,166 bytes)
4. `backend/app/agents/prompts/temple_information_prompt.py` (1,413 bytes)
5. `tests/test_temple_information_agent.py` (6,229 bytes)

---

## 5. Agent Files Classified as KEEP / REBUILD / REVIEW / OBSOLETE

| File Path | Classification | Detailed Rationale |
| :--- | :--- | :--- |
| `backend/app/agents/__init__.py` | **REBUILD** | Only exports two legacy agent classes. Must be rebuilt as the package entry point exposing `BaseAgent`, `RAGTool`, `AgentRouter`, `ResponseAggregator`, `MasterAgentCoordinator`, etc. |
| `backend/app/agents/temple_information_agent.py` | **REBUILD** | Implements an isolated wrapper over `PilgrimRAGService` without conforming to `BaseAgent`. Lacks route decision handling, execution tracing, agent state propagation, and coordinator integration. |
| `backend/app/agents/prompts/temple_information_prompt.py` | **REVIEW** | The prompt constraints (factual grounding, strict temple isolation, anti-hallucination) are well-crafted. Can be reviewed, preserved, and adapted into the rebuilt `TempleInformationAgent`. |
| `backend/app/agents/cross_temple_aggregation_agent.py` | **REVIEW** | The internal scanning and completeness validation logic (evaluating all 20 temples across categories with confirmed available/unavailable partitioning) is mathematically sound and passes tests. However, it is currently tightly coupled into `app/rag/chat.py` (an inverted dependency). Must be refactored to inherit from `BaseAgent` and consume `RAGTool`. |
| `tests/test_temple_information_agent.py` | **REVIEW** | Test cases contain valid assertion patterns for temple isolation and anti-hallucination. Must be updated to test against the standardized `BaseAgent` and coordinator contracts during Phase P. |

### Missing Components to be Created:
- `BaseAgent` & common agent contracts
- `AgentRouteDecision` & `AgentResponse`
- `RAGTool` (Read-only facade)
- `AgentRouter`
- `ResponseAggregator`
- `MasterAgentCoordinator`
- `ComparisonAgent`
- `ItineraryPlanningAgent`
- `CompleteListRetriever`
- `AgentState` & `ExecutionTrace`
- `ConversationMemoryManager`
- `ExternalAPIAdapter`

---

## 6. Current API / Request Flow

Actual request flow observed in the current codebase:

```text
USER (Browser / HTTP Client)
       │
       ▼
[ FastAPI Server ] ── backend/app/main.py
       │
       ▼  POST /chat
[ Chat Endpoint ] ── backend/app/api/chat.py
       │
       │ (Direct invocation — COMPLETELY BYPASSES AGENT LAYER)
       ▼
[ PilgrimRAGService ] ── backend/app/rag/chat.py
       │
       ├── QueryPlanner.plan(question)
       │     ├── if cross_temple_aggregation ──> CrossTempleAggregationAgent
       │     ├── if complete_category ──────────> KnowledgeRegistry (full parent)
       │     ├── if multi_category ─────────────> KnowledgeRegistry / RRF
       │     ├── if broad_temple ───────────────> KnowledgeRegistry (budgeted)
       │     └── if targeted ───────────────────> Qdrant + BM25 -> RRF -> Cross-Encoder
       │
       ├── AnswerScopeController.filter_context(...)
       ├── LocalLLMService._call_ollama_generate(...) ──> Ollama (Qwen2.5:1.5b)
       └── AnswerGroundingValidator.sanitize_answer(...)
       │
       ▼
CLIENT receives ChatResponse:
{
  "question": str,
  "answer": str,
  "retrieved_chunks": int,
  "sources": List[str],
  "confidence_score": float
}
```

### Critical Findings on Current Flow:
1. **The agent layer is NOT participating in `/chat`:** `backend/app/api/chat.py` imports and calls `PilgrimRAGService` directly.
2. `TempleInformationAgent` is an unused artifact only invoked in unit tests.
3. `CrossTempleAggregationAgent` is imported into the RAG service rather than existing as an autonomous agent above the RAG tool.
4. There is **no state, no trace, no memory, no router, and no coordinator** in the request path.

---

## 7. Current Errors and Broken Components

1. **Agent Architectural Disconnect:**  
   No master coordinator or router exists. Requests go straight into the monolithic RAG pipeline.
2. **Inverted Dependency:**  
   `app/rag/chat.py` line 17 has `from app.agents.cross_temple_aggregation_agent import CrossTempleAggregationAgent`. The RAG core layer directly imports the agent layer, violating clean layered architecture.
3. **Absence of Core Agent Infrastructure:**  
   No `BaseAgent`, `RAGTool`, `AgentRouter`, `AgentState`, or `ExecutionTrace` exist.
4. **Stateless Endpoint:**  
   The API has no session ID or conversation memory; every request is processed in total isolation.
5. **Qdrant Client Shutdown Notice (Minor runtime warning):**  
   During Python garbage collection on Windows, `msvcrt` in `portalocker` emits an ignored cleanup exception upon script exit. Does not affect live server runtime, but noted for completeness.

---

## 8. RAG ↔ Agent Boundary

To prevent agents from polluting, modifying, or bypassing the RAG foundation, a strict **read-only facade (`RAGTool`)** must be established.

### Desired Layering:

```text
       ┌──────────────────────────────────────────────┐
       │             MasterAgentCoordinator           │
       └──────────────────────┬───────────────────────┘
                              │
               ┌──────────────┴──────────────┐
               ▼                             ▼
       ┌───────────────┐             ┌───────────────┐
       │  AgentRouter  │             │Specialist     │
       └───────────────┘             │Agents         │
                                     └───────┬───────┘
                                             │
                                             ▼
                                     ┌───────────────┐
                                     │    RAGTool    │  <--- STRICT READ-ONLY BOUNDARY
                                     └───────┬───────┘
                                             │
                       ┌─────────────────────┴─────────────────────┐
                       ▼                                           ▼
          ┌─────────────────────────┐                 ┌─────────────────────────┐
          │    PilgrimRAGService    │                 │    KnowledgeRegistry    │
          └────────────┬────────────┘                 └────────────┬────────────┘
                       │                                           │
         ┌─────────────┴─────────────┐                             │
         ▼                           ▼                             ▼
  ┌─────────────┐             ┌─────────────┐             ┌─────────────────┐
  │  Qdrant DB  │             │ BM25 Index  │             │ 20 Temple Files │
  │  (On-Disk)  │             │  (On-Disk)  │             │   (417 JSONs)   │
  └─────────────┘             └─────────────┘             └─────────────────┘
```

### Boundary Rules:
- **Agents MUST NOT import:** `qdrant_client`, `rank_bm25`, `sentence_transformers`, `LocalQdrantManager`, or `LocalBM25Manager`.
- **Agents MUST NOT directly read or modify:** `qdrant_db/`, `bm25_index/`, or source JSON files.
- **RAGTool Public Contract:**
  1. `RAGTool.retrieve(query: str, temple: Optional[str], category: Optional[str], top_k: int) -> List[RAGChunk]`
  2. `RAGTool.get_temple_category_data(temple: str, category: str) -> Optional[Dict | List]`
  3. `RAGTool.get_complete_parent_text(temple: str, category: str) -> Optional[str]`
  4. `RAGTool.get_registered_temples() -> List[str]`
  5. `RAGTool.get_registered_categories() -> List[str]`
  6. `RAGTool.execute_grounded_rag(question: str) -> Dict[str, Any]`

---

## 9. Risks Discovered

1. **Coupling Risk:** Refactoring `CrossTempleAggregationAgent` out of `app/rag/chat.py` could break existing tests in `tests/test_phase6_audit.py` if not handled cleanly.
2. **LLM Timeout / Latency Risk:** The local `qwen2.5:1.5b` model takes ~1.5s to 3s per generation. A complex coordinator that makes multiple unconstrained sequential LLM calls per request could introduce excessive latency.
3. **Dataset Path Ambiguity Risk:** `.env` specifies `DATASET_DIR=d:\PiligrimAI -c`, while the workspace root `d:\pligrim ai new\` also has the 20 temple directories. Both paths currently resolve to identical data, but the rebuild must maintain deterministic path resolution without mutating data.

---

## 10. Clean Agent Rebuild Architecture

### Core Components:

1. **`BaseAgent` (`backend/app/agents/base_agent.py`):**
   - Abstract Base Class defining standard interface: `name`, `description`, `execute(state: AgentState) -> AgentResponse`.
   - Built-in execution timing, error handling, and logging.
2. **`AgentState` & `ExecutionTrace` (`backend/app/agents/state.py`):**
   - Structured Pydantic dataclasses tracking:
     - `session_id`, `user_query`, `detected_intents`, `active_agent`, `intermediate_results`, `final_response`, `execution_trace` (step name, latency, agent, outcome).
3. **`RAGTool` (`backend/app/agents/tools/rag_tool.py`):**
   - Pure read-only facade interfacing with `PilgrimRAGService` and `KnowledgeRegistry`.
4. **`AgentRouter` (`backend/app/agents/router.py`):**
   - Fast deterministic intent classification:
     - Factual inquiry → `TempleInformationAgent`
     - Exhaustive list inquiry → `CompleteListRetriever`
     - Cross-temple comparison/scan → `CrossTempleAggregationAgent` / `ComparisonAgent`
     - Multi-temple tour / itinerary → `ItineraryPlanningAgent`
5. **Specialist Agents (`backend/app/agents/specialists/`):**
   - `TempleInformationAgent`: Single-temple factual queries.
   - `CompleteListRetriever`: Guarantees non-truncated retrieval for lists (sevas, festivals, facilities).
   - `ComparisonAgent`: Side-by-side comparison between 2+ temples.
   - `CrossTempleAggregationAgent`: 20-temple availability and condition scanner.
   - `ItineraryPlanningAgent`: Timing-aware pilgrimage route planning.
6. **`ResponseAggregator` (`backend/app/agents/aggregator.py`):**
   - Merges multi-intent outputs into a coherent, structured Markdown response.
7. **`MasterAgentCoordinator` (`backend/app/agents/coordinator.py`):**
   - Orchestrates request lifecycle: State Init → Routing → Specialist Execution → Aggregation → Memory Update.
8. **`ConversationMemoryManager` (`backend/app/agents/memory.py`):**
   - Sliding-window multi-turn context retention keyed by `session_id`.
9. **`ExternalAPIAdapter` (`backend/app/agents/tools/external_api_adapter.py`):**
   - Safe firewall interface for optional real-time extensions (weather, live traffic) with graceful offline fallback.

---

## 11. Exact Implementation Order

The rebuild will be executed strictly following the 16-phase plan:

### Phase A: BaseAgent + Common Agent Contract
- Define `BaseAgent` abstract class.
- Define `AgentRouteDecision`, `AgentResponse`, and error handling standards.

### Phase B: RAGTool Read-Only Facade
- Implement `RAGTool` wrapping `PilgrimRAGService` and `KnowledgeRegistry`.
- Verify zero direct database manipulation from agents.

### Phase C: TempleInformationAgent
- Rebuild `TempleInformationAgent` inheriting from `BaseAgent` and consuming `RAGTool`.
- Wire factual grounding and temple isolation.

### Phase D: AgentRouter
- Implement rule-based and intent-classified routing for single/multi-intent queries.

### Phase E: ResponseAggregator
- Implement synthesis engine for assembling multi-agent partial responses into a unified answer.

### Phase F: MasterAgentCoordinator
- Implement coordinator managing end-to-end execution lifecycle.

### Phase G: AgentState + ExecutionTrace
- Implement structured telemetry, state passing, and execution tracing across steps.

### Phase H: Sequential Multi-Intent Execution
- Support queries combining multiple requests (e.g., "timings of Yadadri and list of festivals at Basara").

### Phase I: ConversationMemoryManager
- Implement in-memory conversation store with session-based context retrieval.

### Phase J: Complete-List Retrieval
- Build specialized list retriever guaranteeing 100% complete items without top-k truncation.

### Phase K: ComparisonAgent
- Build comparative agent contrasting 2 or more temples (e.g., darshan timings, facilities, distance).

### Phase L: CrossTempleAggregationAgent
- Refactor the 20-temple aggregation engine into the clean `BaseAgent` framework.

### Phase M: ItineraryPlanningAgent
- Implement pilgrimage itinerary generator considering opening hours, sevas, and travel times.

### Phase N: FastAPI `/chat` Integration
- Wire `MasterAgentCoordinator` into `backend/app/api/chat.py` with backward-compatible response schemas.

### Phase O: External API Adapter / Firewall
- Implement safe external API proxy with offline mock fallbacks.

### Phase P: Agent Tests and Final Certification
- Comprehensive unit, integration, and end-to-end test suite for all agents.

---

## 12. Critical Data Protection Rule — Verified Frozen Assets

The following core assets are certified **FROZEN** and will NOT be modified:
1. `yadadri/`, `basara/`, and all other 18 source temple JSON directories.
2. `qdrant_db/` collection, parent store, and metadata.
3. `bm25_index/` inverted index store (`bm25_store.pkl`).
4. `backend/app/rag/` core retrieval, RRF fusion, reranker, and grounding validation logic.
5. `evaluation/` baseline datasets and evaluation metrics.
