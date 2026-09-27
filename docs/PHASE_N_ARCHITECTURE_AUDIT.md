# PilgrimAI — Phase N Architecture Audit & Implementation Plan

**Date:** September 21, 2026  
**Project:** PilgrimAI: A RAG-Based Multi-Agent Assistant for Smart Pilgrimage  
**Workspace:** `D:\pligrim ai new`  
**Audit Type:** Architecture Audit & Implementation Plan (No Production Code Modified)  
**Status:** Audit Complete — Implementation NOT Started  

---

## 1. Audit Date
September 21, 2026

---

## 2. Workspace
`D:\pligrim ai new`

---

## 3. Current Certified Baseline
The repository currently maintains a 100% green certified baseline across all 15 test suites:

| Suite | Component / Phase | Tests | Status |
|---|---|---|---|
| 1 | `test_agent_contracts.py` (Phase A: Agent Contracts) | 10/10 | PASSED |
| 2 | `test_rag_tool.py` (Phase B: RAGTool Read-Only Facade) | 10/10 | PASSED |
| 3 | `test_temple_information_agent.py` (Phase C: Temple Information Specialist) | 10/10 | PASSED |
| 4 | `test_agent_router.py` (Phase D: AgentRouter Priorities) | 13/13 | PASSED |
| 5 | `test_response_aggregator.py` (Phase E: ResponseAggregator Synthesis) | 13/13 | PASSED |
| 6 | `test_master_agent_coordinator.py` (Phase F: Coordinator Orchestration) | 13/13 | PASSED |
| 7 | `test_agent_state.py` (Phase G: AgentState & ExecutionTrace) | 17/17 | PASSED |
| 8 | `test_multi_intent_pipeline.py` (Phase H: Sequential Multi-Intent Pipeline) | 18/18 | PASSED |
| 9 | `test_conversation_memory.py` (Phase I: ConversationMemoryManager) | 24/24 | PASSED |
| 10 | `test_query_planner.py` (RAG Baseline: Intent & Entity Classification) | 40/40 | PASSED |
| 11 | `test_complete_list_retrieval.py` (Phase J: Complete-List Retrieval) | 22/22 | PASSED |
| 12 | `test_comparison_agent.py` (Phase K: ComparisonAgent Specialist) | 30/30 | PASSED |
| 13 | `test_cross_temple_aggregation_agent.py` (Phase L: CrossTempleAggregationAgent) | 28/28 | PASSED |
| 14 | `test_itinerary_planning_agent.py` (Phase M: ItineraryPlanningAgent Specialist) | 27/27 | PASSED |
| **—** | **Subtotal Modern Test Baseline** | **275/275** | **100% GREEN** |
| 15 | `test_cross_temple_aggregation.py` (Legacy RAG Compatibility) | 13/13 | PASSED |
| **TOTAL** | **Certified Regression Baseline (Modern + Legacy)** | **288/288** | **100% GREEN** |

---

## 4. Current Repository State
- **Temples:** 20 canonical temple directories verified present in project root.
- **Source JSON Files:** Exactly 417 verified source files.
- **Categories:** 21 verified canonical categories registered in `CategoryRegistry`.
- **Vector Index:** Qdrant on-disk storage (`qdrant_db/`) containing 1,578 parent chunks.
- **Sparse Index:** BM25 inverted index (`bm25_index/`) containing 4,458 child chunks.
- **Local Models:** Embeddings via `sentence-transformers/all-MiniLM-L6-v2`, reranking via `cross-encoder/ms-marco-MiniLM-L-6-v2`, local LLM via Ollama `qwen2.5:1.5b`.

---

## 5. Current Architecture

```text
User Query
    ↓
AgentState
    ↓
MasterAgentCoordinator (Orchestrator)
    ↓
ConversationMemoryManager (Sliding-window context & pronoun resolution)
    ↓
AgentRouter (Priority-driven deterministic intent classification)
    ↓
Specialist Agent (TempleInformation, Comparison, CrossTempleAggregation, ItineraryPlanning)
    ↓
RAGTool (Read-Only Knowledge Access Facade)
    ↓
Verified Knowledge Base (Local Qdrant, BM25, KnowledgeRegistry)
    ↓
AgentResponse (Structured metadata, sources, execution timing)
    ↓
ResponseAggregator (Unified Markdown synthesis, conflict detection, source deduplication)
    ↓
Final Response
```

---

## 6. Current Agent Inventory

| Agent Name | Source File | BaseAgent Inherited? | RAG Boundary | Router Intent | Registration Status |
|---|---|---|---|---|---|
| `TempleInformationAgent` | `backend/app/agents/temple_information_agent.py` | Yes | RAGTool only | `temple_information` | Default active agent |
| `ComparisonAgent` | `backend/app/agents/comparison_agent.py` | Yes | RAGTool only | `comparison` | Registered dynamically |
| `CrossTempleAggregationAgent` | `backend/app/agents/cross_temple_aggregation_agent.py` | Yes | RAGTool only | `cross_temple_aggregation` | Registered dynamically |
| `ItineraryPlanningAgent` | `backend/app/agents/itinerary_planning_agent.py` | Yes | RAGTool only | `itinerary_planning` | Registered dynamically |

All 4 agents strictly inherit from `BaseAgent`, execute via `execute(state: AgentState) -> AgentResponse`, record `ExecutionTrace`, maintain strict Fact vs. Suggestion / Comparison / Aggregation boundaries, and interface exclusively through `RAGTool`.

---

## 7. BaseAgent Contract Audit
- Defined in `backend/app/agents/base_agent.py`.
- Enforces abstract `_run(state: AgentState) -> AgentResponse` hook.
- Implements standard `execute(state: AgentState) -> AgentResponse` measuring `latency_ms`, appending `ExecutionTrace` to `state.execution_trace`, and containing unhandled exceptions into controlled error responses.
- Verified compliant across all 4 specialist agents.

---

## 8. AgentState / ExecutionTrace Audit
- Defined in `backend/app/agents/state.py`.
- Fields: `session_id`, `user_query`, `detected_intents`, `active_agent`, `intermediate_results`, `final_response`, `execution_trace`, `context`.
- `ExecutionTrace`: captures `step_name`, `agent_name`, `status`, `latency_ms`, `metadata`, `error`, `timestamp`.
- Audited: Fully compatible and rich. No additional state fields are required for Phase N, though `session_id` must now be plumbed from API requests into `AgentState`.

---

## 9. AgentRouter Audit
- Defined in `backend/app/agents/router.py`.
- Routing order & priorities:
  1. Priority 1: Empty / whitespace query $\to$ `intent="unsupported"`
  2. Priority 2: Explicit unsupported temple $\to$ `intent="unsupported"`
  3. Priority 3: Comparison intent $\to$ `intent="comparison"` (or `multi_intent` if conjoined)
  4. Priority 4: Itinerary planning intent $\to$ `intent="itinerary_planning"` (or `multi_intent` if conjoined)
  5. Priority 5: Cross-temple aggregation intent $\to$ `intent="cross_temple_aggregation"`
  6. Priority 6: Multi-intent conjoined query $\to$ `intent="multi_intent"`
  7. Priority 7: Single known-temple factual query $\to$ `intent="temple_information"`
  8. Priority 8: Zero-temple generic inquiry $\to$ `intent="clarification"`
  9. Priority 9: Non-temple / out-of-scope query $\to$ `intent="unsupported"`
- Inactive-agent fallbacks preserved across comparison, itinerary, and aggregation.
- Dynamic registration via `register_agent()` and `unregister_agent()` verified operational.

---

## 10. MasterAgentCoordinator Audit
- Defined in `backend/app/agents/coordinator.py`.
- Orchestration workflow:
  1. State validation
  2. Multi-turn pronoun resolution via `ConversationMemoryManager`
  3. Intent classification via `AgentRouter`
  4. Clarification / Unsupported containment
  5. Multi-intent decomposition & sequential execution via `SequentialMultiIntentPipeline`
  6. Unimplemented capability fallback check (`is_unimplemented`)
  7. Specialist agent execution via `selected_agent.execute(state)`
  8. Synthesis via `ResponseAggregator`
  9. Memory recording via `memory_manager.add_turn()`
- Supports constructor dependency injection:
  `MasterAgentCoordinator(router, aggregator, temple_info_agent, comparison_agent, cross_temple_agent, itinerary_agent, agents, pipeline, memory_manager)`

---

## 11. ConversationMemory Audit
- Defined in `backend/app/agents/memory.py` (`ConversationMemoryManager`).
- Features:
  - Session-isolated history storing up to 10 turns per session.
  - LRU session eviction (up to 1,000 concurrent sessions).
  - TTL expiry (default 3,600s / 1 hour).
  - Pronoun / anaphora resolution for single and multiple temples ("it", "there", "them", "both").
  - Secret sanitization (masks API keys, passwords, bearer tokens).
- Audited: Ready to be utilized in `/chat` once `session_id` is passed from API requests.

---

## 12. Multi-Intent Pipeline Audit
- Defined in `backend/app/agents/multi_intent_pipeline.py` (`SequentialMultiIntentPipeline`).
- Decomposes conjoined queries into ordered sub-queries preserving temple context.
- Dispatches sub-queries to appropriate registered specialist agents sequentially.
- Synthesizes outputs through `ResponseAggregator`.
- Tested and verified operational with factual, comparison, aggregation, and itinerary intents.

---

## 13. ResponseAggregator Audit
- Defined in `backend/app/agents/response_aggregator.py` (`ResponseAggregator`).
- Composes single or multiple `AgentResponse` objects into a unified `AgentResponse`.
- Features: deduplication, source merging without duplication, conflict detection, failure preservation.

---

## 14. RAGTool Boundary Audit
- Defined in `backend/app/agents/tools/rag_tool.py` (`RAGTool`).
- Public methods:
  - `retrieve(query, temple, category, top_k)`
  - `get_temple_category_data(temple, category)`
  - `get_complete_parent_text(temple, category)`
  - `get_registered_temples()`
  - `get_registered_categories()`
  - `execute_grounded_rag(question)`
- Zero forbidden DB imports or raw filesystem reads across all specialist agents.

---

## 15. Legacy Agent Audit
- The only previous legacy agent was `CrossTempleAggregationAgent`, which was refactored in Phase L to cleanly inherit from `BaseAgent` while preserving its legacy methods (`aggregate_temples`, `format_response`, `detect_aggregation_intent`).
- Legacy test suite `tests/test_cross_temple_aggregation.py` passes 13/13.
- No other legacy agent classes exist in the repository.

---

## 16. External API Boundary Audit
- Live navigation, live traffic, live weather, and room booking agents do **NOT** exist in the repository.
- Phase M established strict deterministic live-data limitation disclaimers.
- External API adapters are scheduled for **Phase O** (`docs/AGENT_REBUILD_AUDIT.md` Section 11 line 399).
- External APIs must remain strictly **OUT OF SCOPE** for Phase N.

---

## 17. `/chat` Integration Audit (The Critical Gap)
- Inspection of `backend/app/api/chat.py` reveals:
  ```python
  @router.post("/chat", response_model=ChatResponse)
  async def chat_endpoint(request: ChatRequest):
      ...
      service = get_rag_service()
      result = service.answer(cleaned_question)
      return ChatResponse(...)
  ```
- **Architectural Disconnect:**
  - `/chat` currently connects directly to `PilgrimRAGService.answer()`.
  - It **completely bypasses** `MasterAgentCoordinator`, `AgentRouter`, `TempleInformationAgent`, `ComparisonAgent`, `CrossTempleAggregationAgent`, `ItineraryPlanningAgent`, `SequentialMultiIntentPipeline`, and `ConversationMemoryManager`.
  - A user sending queries to `/chat` cannot access comparison, itinerary planning, multi-intent, or conversation memory!
  - `ChatRequest` does not support `session_id`, precluding multi-turn memory from the API.
- This is the exact gap Phase N was scheduled to solve.

---

## 18. Dataset Integrity Audit
Verified read-only from actual repository data:
- **Temple Directories:** 20 verified present (`ahobilam`, `badrachalam`, `balkampet`, `basara`, `birla mandir`, `chilkur`, `dharmapuri`, `edupayal`, `jogulamba(new)`, `kaleshvaram`, `karmanghat`, `medaram`, `ramappa`, `srisaila`, `thousand pillar`, `ttd`, `ujjaini`, `veera satyanarayana`, `vemulavada`, `yadadri`).
- **Source JSON Files:** Exactly 417 verified.
- **Ground Truth Item Counts:**
  - Dharmapuri sevas = 10 (`dharmapuri/sevas.json`).
  - Yadadri facilities = 26 (`yadadri/facilities.json`).
  - Edupayala prasadam = 2 (`edupayal/prasadam.json`).
  - River-bank temples = 11 (verified via `CrossTempleAggregationAgent`).
- **Protected Storage:** `qdrant_db/` (1,578 parent chunks) and `bm25_index/` (4,458 child chunks) verified unchanged.

---

## 19. Test Baseline
- **Modern Regression (14 suites):** **275/275 PASSED**
- **Legacy Regression (1 suite):** **13/13 PASSED**
- **Total Repository Baseline:** **288/288 PASSED** (100% green)

---

## 20. Identified Architectural Gaps

1. **API / Agent Layer Disconnection:**
   The entire Phase A–M multi-agent system (`MasterAgentCoordinator`, `AgentRouter`, `TempleInformationAgent`, `ComparisonAgent`, `CrossTempleAggregationAgent`, `ItineraryPlanningAgent`) is fully functional and certified in `tests/`, but is **completely disconnected** from the FastAPI endpoint in `backend/app/api/chat.py`.
2. **Missing Session Context in API:**
   `ChatRequest` only accepts `question: str`. It does not support `session_id: Optional[str]`, preventing API users or web clients from engaging in multi-turn pronoun-resolved conversations.
3. **Missing Coordinator Agent Responses in API:**
   `ChatResponse` only returns `question`, `answer`, `retrieved_chunks`, `sources`, `confidence_score`. It lacks agent-layer metadata such as `agent_name`, `session_id`, `latency_ms`, and `metadata` (while needing to preserve backward compatibility for existing callers).
4. **No Comprehensive `/chat` Integration Test Suite:**
   There is currently no dedicated test suite verifying that `/chat` dispatches across all specialist agents, multi-intent pipeline, conversation memory, and error fallbacks.

---

## 21. Phase N Candidate

**Candidate:** **FastAPI `/chat` Multi-Agent Coordinator Integration**

### Why It Belongs After Phase M
- In `docs/AGENT_REBUILD_AUDIT.md` Section 11, line 396:
  ```text
  ### Phase N: FastAPI `/chat` Integration
  - Wire `MasterAgentCoordinator` into `backend/app/api/chat.py` with backward-compatible response schemas.
  ```
- All specialist agents (Phase C: Temple Information, Phase K: Comparison, Phase L: Cross-Temple Aggregation, Phase M: Itinerary Planning) are now complete and certified.
- The multi-agent assistant cannot be used via HTTP or the web interface until `/chat` is wired to `MasterAgentCoordinator`.

---

## 22. Phase N Scope

1. **Wire Coordinator into `backend/app/api/chat.py`:**
   - Initialize/inject `MasterAgentCoordinator` (with all 4 specialist agents: `temple_information`, `comparison`, `cross_temple_aggregation`, `itinerary_planning`, plus `ConversationMemoryManager`).
   - Route incoming POST `/chat` requests through `coordinator.process(state)`.
2. **Schema Upgrades with Strict Backward Compatibility:**
   - `ChatRequest`:
     - `question: str` (required, preserved).
     - `session_id: Optional[str] = None` (new optional field; generates a UUID if not provided).
   - `ChatResponse`:
     - `question: str` (preserved).
     - `answer: str` (preserved).
     - `retrieved_chunks: int` (preserved, mapped from response metadata or chunk count).
     - `sources: List[str]` (preserved).
     - `confidence_score: float` (preserved, mapped from response metadata or default 1.0 for specialist answers).
     - `agent_name: Optional[str] = None` (new optional telemetry field).
     - `session_id: Optional[str] = None` (new optional field returned to caller).
     - `latency_ms: Optional[float] = None` (new optional field).
     - `metadata: Optional[Dict[str, Any]] = None` (new optional field).
3. **Graceful Fallback & Error Containment:**
   - Empty/whitespace queries return HTTP 400 or structured refusal without crashing.
   - Internal coordinator exceptions return clean HTTP 500 or fallback `ChatResponse`.
4. **Lifecycle & Startup Integration in `backend/app/main.py`:**
   - Update `startup_event` in `backend/app/main.py` to pre-warm `MasterAgentCoordinator` (or lazily initialize safely).
5. **Static UI Compatibility:**
   - Confirm `backend/app/static/index.html` functions cleanly with the updated response without breaking.

---

## 23. Out of Scope for Phase N

The following must **NOT** be included in Phase N:
- `ExternalAPIAdapter` (scheduled for **Phase O**).
- Real-time navigation / live traffic APIs (Google Maps, MapMyIndia).
- Real-time weather APIs (OpenWeatherMap, IMD).
- Live booking systems or room reservation APIs.
- Voice / Audio / Multilingual APIs (Whisper, Bhashini).
- Modifying the frozen 417 source JSON files.
- Rebuilding Qdrant or BM25 indexes.
- Modifying core RAG retrieval logic (`backend/app/rag/`).

---

## 24. Proposed File Changes

### Files to Modify:
1. `backend/app/api/chat.py` — Wire `MasterAgentCoordinator`, update `ChatRequest`/`ChatResponse` schemas with backward compatibility.
2. `backend/app/main.py` — Update startup pre-warming to initialize the coordinator safely.

### Files to Create:
1. `tests/test_chat_integration.py` — Comprehensive Phase N test suite verifying `/chat` endpoint with TestClient across all intents, memory, and fallbacks (at least 20 tests).
2. `docs/PHASE_N_CHAT_INTEGRATION.md` — Post-implementation certification report.

### Files that Must Remain Protected:
- All 417 source JSON files across 20 temple directories.
- `qdrant_db/`
- `bm25_index/`
- `evaluation/`
- `.env`
- `backend/app/rag/*`
- All 15 existing test suites.

---

## 25. Proposed Implementation Plan

```text
N1 — Coordinator Factory & Dependency Injection in chat.py
     - Create get_coordinator() factory in chat.py with singleton caching and lazy instantiation.
     - Inject all 4 specialist agents (TempleInformationAgent, ComparisonAgent, CrossTempleAggregationAgent, ItineraryPlanningAgent).
     - Inject ConversationMemoryManager for multi-turn tracking.

N2 — Schema Evolution with Backward Compatibility
     - Add session_id to ChatRequest (default None).
     - Add agent_name, session_id, latency_ms, metadata to ChatResponse as optional fields.
     - Preserve existing question, answer, retrieved_chunks, sources, confidence_score fields.

N3 — chat_endpoint Execution via Coordinator
     - Construct AgentState(user_query=question, session_id=session_id).
     - Execute coordinator.process(state).
     - Map AgentResponse fields into ChatResponse.

N4 — Application Startup in main.py
     - Update startup_event in main.py to pre-warm get_coordinator().

N5 — Phase N Test Suite Creation
     - Create tests/test_chat_integration.py using FastAPI TestClient.
     - Test single-temple factual queries.
     - Test comparison queries through /chat.
     - Test cross-temple aggregation queries through /chat.
     - Test itinerary planning queries through /chat.
     - Test multi-intent compound queries through /chat.
     - Test multi-turn conversation memory with session_id through /chat.
     - Test empty, whitespace, and unknown temple handling through /chat.
     - Test backward compatibility with legacy ChatRequest ({question}).

N6 — Regression Verification
     - Run 288 pre-Phase-N baseline tests + new Phase N tests.

N7 — Data Integrity Verification
     - Verify 20 temples, 417 JSONs, ground truth counts, frozen indexes.

N8 — Certification & Documentation
     - Generate docs/PHASE_N_CHAT_INTEGRATION.md.
```

---

## 26. Proposed Test Plan

`tests/test_chat_integration.py` will include at least 20 focused tests:
1. Health check endpoint verification (`/health`).
2. Legacy `ChatRequest` schema compatibility (`{"question": "..."}`).
3. Enhanced `ChatRequest` schema with `session_id`.
4. Backward-compatible `ChatResponse` field presence (`question`, `answer`, `retrieved_chunks`, `sources`, `confidence_score`).
5. Enhanced `ChatResponse` field presence (`agent_name`, `session_id`, `latency_ms`).
6. Factual single-temple dispatch via `/chat` (routed to `temple_information`).
7. Comparison query dispatch via `/chat` (routed to `comparison`).
8. Cross-temple aggregation query dispatch via `/chat` (routed to `cross_temple_aggregation`).
9. Itinerary planning query dispatch via `/chat` (routed to `itinerary_planning`).
10. Multi-intent conjoined query dispatch via `/chat` (routed to `multi_intent`).
11. Multi-turn conversation memory turn 1 $\to$ turn 2 pronoun resolution via `/chat` using `session_id`.
12. Multi-turn session isolation (distinct `session_id`s do not cross-contaminate).
13. Auto-generated `session_id` when omitted in `ChatRequest`.
14. Empty question rejection (HTTP 400 Bad Request).
15. Whitespace question rejection (HTTP 400 Bad Request).
16. Unknown temple controlled refusal via `/chat`.
17. Zero-temple clarification response via `/chat`.
18. Source grounding format compliance in `/chat` response.
19. Live-data disclaimer presence in itinerary `/chat` responses.
20. Concurrent request isolation and deterministic behavior.

---

## 27. Acceptance Criteria

1. **Coordinator Integration:** All HTTP requests to `POST /chat` are processed through `MasterAgentCoordinator`.
2. **All 4 Specialists Reachable:** Factual, comparison, cross-temple aggregation, and itinerary queries submitted to `/chat` execute their respective specialist agents.
3. **Memory Operational via API:** Successive requests sharing a `session_id` resolve pronouns correctly.
4. **Strict Schema Backward Compatibility:** Any existing client sending `{"question": "..."}` receives valid responses matching the previous `ChatResponse` contract.
5. **Zero Regression:** All 288 existing tests (275 modern + 13 legacy) continue to pass 100%.
6. **No Protected File Mutation:** 417 temple JSON files, `qdrant_db/`, `bm25_index/`, and core `backend/app/rag/` files remain completely untouched.

---

## 28. Risks & Mitigations

1. **Circular Import Risk:**
   - *Risk:* `chat.py` importing coordinator, which imports agents, which import RAGTool, which imports RAG service.
   - *Mitigation:* Use lazy factory `get_coordinator()` pattern already proven in `chat.py` and `itinerary_planning_agent.py`.
2. **FastAPI Pydantic V2 Deprecation Warnings:**
   - *Risk:* Existing `chat.py` has a minor deprecation warning for `Field(..., example=...)`.
   - *Mitigation:* Cleanly migrate to `json_schema_extra` during Phase N.
3. **Cold Start Latency:**
   - *Risk:* Initializing all agents and embedding/cross-encoder models on first request could cause timeout.
   - *Mitigation:* Pre-warm coordinator and models in `startup_event`.
4. **Breaking Web UI:**
   - *Risk:* Changing `ChatResponse` could break `index.html`.
   - *Mitigation:* Keep all existing fields with exact same types and semantics; only add new optional fields.

---

## 29. Protected Files
- `All 417 source JSON files across 20 temple directories`
- `qdrant_db/`
- `bm25_index/`
- `evaluation/`
- `.env`
- `backend/app/rag/*`
- All 15 existing test suites in `tests/`

---

## 30. Certification Strategy
- Pre-Phase-N Baseline: **288/288 passed** (275 modern + 13 legacy).
- Expected Post-Phase-N Baseline: **288 + 20+ = 308+ passed**.
- Dataset integrity verification: 20 temples, 417 JSONs, Dharmapuri sevas = 10, Yadadri facilities = 26, Edupayala prasadam = 2, River-bank temples = 11.
- Complete regression suite executed and confirmed green before claiming certification.

---

## 31. Audit Conclusion
The Phase N scope is conclusively identified and firmly grounded in repository documentation:
**Phase N: FastAPI `/chat` Multi-Agent Coordinator Integration**
Phase N implementation has **NOT STARTED**. Awaiting explicit user approval before proceeding.
