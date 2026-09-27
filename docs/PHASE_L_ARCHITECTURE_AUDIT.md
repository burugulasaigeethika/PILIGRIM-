# PilgrimAI — Phase L: Architecture Audit & Implementation Plan

**Date:** September 20, 2026  
**Project:** PilgrimAI: A RAG-Based Multi-Agent Assistant for Smart Pilgrimage  
**Workspace:** `D:\pligrim ai new`  
**Audit Type:** Architecture Audit & Implementation Plan (No Production Code Modified)  
**Status:** Audit Complete — Implementation NOT Started  

---

## 1. Current Certified Baseline

The project has completed Phases A through K with an unbroken green certification baseline across all 12 certified test suites:

| Phase | Component | Tests | Status |
|---|---|---|---|
| Phase A | Agent Contracts (`BaseAgent`, `AgentResponse`, `AgentRouteDecision`) | 10/10 | PASSED |
| Phase B | RAGTool Read-Only Facade | 10/10 | PASSED |
| Phase C | TempleInformationAgent (Specialist) | 10/10 | PASSED |
| Phase D | AgentRouter (Intent Routing & Priority Hierarchy) | 13/13 | PASSED |
| Phase E | ResponseAggregator (Multi-Agent Synthesis) | 13/13 | PASSED |
| Phase F | MasterAgentCoordinator (Lifecycle Orchestration) | 13/13 | PASSED |
| Phase G | AgentState & ExecutionTrace (Telemetry & Auditing) | 17/17 | PASSED |
| Phase H | SequentialMultiIntentPipeline (Multi-Intent Decomposition) | 18/18 | PASSED |
| Phase I | ConversationMemoryManager (Session Context & Resolution) | 24/24 | PASSED |
| RAG Baseline | QueryPlanner & Knowledge Foundations | 40/40 | PASSED |
| Phase J | Complete-List Retrieval Guarantee (Parent Store Integration) | 22/22 | PASSED |
| Phase K | ComparisonAgent (Specialist Side-by-Side Comparison) | 30/30 | PASSED |
| **TOTAL** | **Certified Regression Baseline** | **220/220** | **100% GREEN** |

All protected assets remain untouched:
- 20 temple directories
- 417 source JSON files
- `qdrant_db/` (1,578 parent chunks)
- `bm25_index/` (4,458 child chunks)
- Verified item counts: Dharmapuri sevas = 10, Yadadri facilities = 26, Edupayala prasadam = 2

---

## 2. Current Agent Inventory

Inspection of `backend/app/agents/` reveals the following inventory:

| Agent Name | Source File | Router Intent | Registration Status | Coordinator Integration | Test Suite & Coverage |
|---|---|---|---|---|---|
| `TempleInformationAgent` | `backend/app/agents/temple_information_agent.py` | `temple_information` | Registered by default (`active_agents`) | Fully integrated as default factual specialist | `tests/test_temple_information_agent.py` (10 tests) |
| `ComparisonAgent` | `backend/app/agents/comparison_agent.py` | `comparison` | Registered via `router.register_agent("comparison")` | Injected conditionally via `comparison_agent` param | `tests/test_comparison_agent.py` (30 tests) |
| `CrossTempleAggregationAgent` *(Legacy)* | `backend/app/agents/cross_temple_aggregation_agent.py` | `cross_temple_aggregation` | **NOT REGISTERED** (`selected_agent="none"`, `available=False`) | **NOT INTEGRATED** | Legacy RAG tests only (`test_cross_temple_aggregation.py`, 13 tests) |
| `ItineraryPlanningAgent` | *(Non-existent)* | `itinerary_planning` | **NOT REGISTERED** (`selected_agent="none"`, `available=False`) | **NOT INTEGRATED** | Router intent recognition test only (`test_agent_router.py`) |

---

## 3. Router Architecture

`AgentRouter` (`backend/app/agents/router.py`) uses a priority rule-based evaluation hierarchy:

1. **Priority 1: Empty / Whitespace Query** $\to$ `intent="unsupported"`, `selected_agent="none"`, `confidence=1.0`
2. **Priority 2: Explicit Unsupported Temple** $\to$ Anti-hallucination rejection for non-registered temples (`selected_agent="none"`, `intent="unsupported"`)
3. **Priority 3: Comparison Intent** $\to$ Evaluates comparison syntax / $\ge 2$ temples:
   - If $\ge 2$ non-comparison factual sub-intents are present $\to$ `intent="multi_intent"`, `selected_agent="none"`
   - Otherwise, if `"comparison"` is registered $\to$ `selected_agent="comparison"`, `available=True`
   - If not registered $\to$ `selected_agent="none"`, `available=False`
4. **Priority 4: Itinerary Planning Intent** $\to$ Matches trip/tour/visit patterns $\to$ `selected_agent="none"`, `intent="itinerary_planning"`, `available=False`
5. **Priority 5: Cross-Temple Aggregation Intent** $\to$ Matches aggregation triggers (`which temples`, `list all temples`, etc.) $\to$ `selected_agent="none"`, `intent="cross_temple_aggregation"`, `available=False`
6. **Priority 6: Temple Information Intent** $\to$ Detects canonical temple or factual category $\to$ `selected_agent="temple_information"`, `intent="temple_information"`
7. **Priority 7: General Pilgrimage Guidance** $\to$ General pilgrimage inquiries $\to$ `selected_agent="temple_information"`, `intent="general_guidance"`

`AgentRouter` maintains an `active_agents: Set[str]` set and exposes `register_agent(agent_name: str)`, allowing dynamic activation of newly implemented specialist agents while preserving strict backward compatibility when unregistered.

---

## 4. Coordinator Architecture

`MasterAgentCoordinator` (`backend/app/agents/coordinator.py`) orchestrates the request lifecycle:
- Accepts dependency injections: `router`, `aggregator`, `temple_info_agent`, `comparison_agent`, `agents`, `pipeline`, `memory_manager`.
- Initializes `self.agents: Dict[str, BaseAgent]`.
- Synchronizes with `router.register_agent()` for every active agent.
- Manages the processing flow:
  1. Input validation & empty query detection
  2. Memory context resolution (Phase I sliding window)
  3. Query routing via `AgentRouter.route(query)`
  4. Multi-intent decomposition via `SequentialMultiIntentPipeline` if `intent == "multi_intent"`
  5. Fallback refusal if `route.selected_agent == "none"` or `target not in self.agents`
  6. Specialist execution via `agent.execute(state)` to preserve standard timing, exception containment, and execution traces
  7. Response aggregation via `ResponseAggregator.aggregate()`
  8. Memory recording via `memory_manager.add_turn()`

---

## 5. AgentState and ExecutionTrace

`AgentState` (`backend/app/agents/state.py`):
- Tracks:
  - `session_id: Optional[str]`
  - `user_query: str`
  - `route_decision: Optional[AgentRouteDecision]`
  - `intermediate_results: Dict[str, Any]`
  - `execution_trace: List[TraceStep]` (singular attribute name)
  - `final_response: Optional[AgentResponse]`
  - `context: Dict[str, Any]`
- `TraceStep`: records `agent_name`, `step_name`, `status` ("completed", "failed", "started"), `latency_ms`, `error`, `metadata`.
- Guarantees end-to-end auditability and containment without uncaught exceptions leaking to callers.

---

## 6. ConversationMemoryManager

`ConversationMemoryManager` (`backend/app/agents/memory.py`):
- In-memory sliding-window store keyed by `session_id`.
- Default: `max_turns=10`, `ttl_seconds=3600`, LRU eviction with `max_sessions=1000`.
- Deterministic query resolution (`resolve_query`):
  - Resolves pronouns (`it`, `this temple`, `its`) to the most recent canonical temple.
  - Detects ambiguity when multiple distinct temples were discussed recently.
  - Preserves explicit new temples in the current turn without guessing.

---

## 7. Multi-Intent Pipeline

`SequentialMultiIntentPipeline` (`backend/app/agents/multi_intent_pipeline.py`):
- Decomposes conjoined queries (split on conjunctions, punctuation, question marks).
- Propagates primary temple context to sub-clauses lacking an explicit temple.
- Routes each sub-query independently through `AgentRouter`.
- Executes tasks sequentially and synthesizes results using `ResponseAggregator`.

---

## 8. CrossTempleAggregationAgent Status

- **Current File**: `backend/app/agents/cross_temple_aggregation_agent.py` (171 lines, legacy implementation).
- **Current Status**: **PARTIALLY IMPLEMENTED / LEGACY CODE**.
- **Architectural Discrepancies**:
  1. Does **NOT** inherit from `BaseAgent`.
  2. Does **NOT** implement `_run(state: AgentState) -> AgentResponse`.
  3. Does **NOT** record `ExecutionTrace` or measure execution latencies.
  4. Directly imports and depends on `KnowledgeRegistry`, `CompletenessValidator`, `ContextBuilder`, and `QueryPlanner`, bypassing the `RAGTool` boundary.
  5. Directly imported by `backend/app/rag/chat.py` line 17 as an inverted dependency.
  6. Router marks it as `available=False` ("not yet implemented").
  7. Coordinator does not support or register it.
  8. Cannot participate in `SequentialMultiIntentPipeline`.

---

## 9. ItineraryPlanningAgent Status

- **Current Status**: **NOT IMPLEMENTED (PLANNED ONLY)**.
- Source code: None.
- Router: Recognizes `intent="itinerary_planning"` with `selected_agent="none"`, `available=False`.
- Coordinator: No registration or parameters.
- Inherently depends on temple information, cross-temple comparison, and cross-temple facility/accessibility availability.

---

## 10. Existing Phase L References

In `docs/AGENT_REBUILD_AUDIT.md` (the blueprint for the multi-agent rebuild), Section 11 explicitly designates:
```text
### Phase L: CrossTempleAggregationAgent
- Refactor the 20-temple aggregation engine into the clean BaseAgent framework.

### Phase M: ItineraryPlanningAgent
- Implement pilgrimage itinerary generator considering opening hours, sevas, and travel times.
```

Moreover, `docs/AGENT_REBUILD_AUDIT.md` Section 9 notes:
```text
1. Coupling Risk: Refactoring CrossTempleAggregationAgent out of app/rag/chat.py could break existing tests in tests/test_phase6_audit.py if not handled cleanly.
```

---

## 11. RAG Boundary

`RAGTool` (`backend/app/agents/tools/rag_tool.py`) provides the strict, read-only boundary:
- `get_registered_temples() -> List[str]`: Returns the 20 canonical temples.
- `get_registered_categories() -> List[str]`: Returns canonical categories.
- `get_temple_category_data(temple, category) -> Optional[Any]`: Fetches parsed category data without direct filesystem paths.
- `get_complete_parent_text(temple, category) -> Optional[str]`: Fetches un-truncated parent text.
- `retrieve(query, temple, category, top_k) -> List[RAGChunk]`: Hybrid dense/sparse candidate retrieval.

Phase L must access knowledge strictly via `RAGTool`. Direct imports of `qdrant_client`, `rank_bm25`, `sentence_transformers`, `CrossEncoder`, `LocalQdrantManager`, or raw JSON files inside `CrossTempleAggregationAgent` are strictly prohibited.

---

## 12. Current Test Architecture

- **Total Baseline Tests**: **220 passed, 0 failed** across 12 test suites.
- Legacy cross-temple aggregation tests: `tests/test_cross_temple_aggregation.py` (13 passed).
- All 220 baseline tests must remain green.
- Existing legacy tests verifying the mathematical correctness of 20-temple evaluation (e.g. 11 river-bank temples) must continue to pass.

---

## 13. Identified Architectural Gaps

1. `CrossTempleAggregationAgent` is isolated from the `BaseAgent` contract.
2. Inverted dependency: `chat.py` imports `CrossTempleAggregationAgent`, while `CrossTempleAggregationAgent` imports low-level RAG internals.
3. Router marks aggregation as unavailable despite the existence of core scanning logic.
4. Coordinator cannot dispatch cross-temple queries.
5. Aggregation cannot be executed within a multi-intent pipeline request (e.g. "What are Yadadri timings and list all temples with river bank?").

---

## 14. Recommended Phase L Scope

### Confirmed Target: `CrossTempleAggregationAgent`

The audit confirms that **Phase L must implement `CrossTempleAggregationAgent`** within the clean `BaseAgent` multi-agent framework:
1. Aligns with the sequential order in `AGENT_REBUILD_AUDIT.md` (Phase L: CrossTempleAggregationAgent $\to$ Phase M: ItineraryPlanningAgent).
2. Closes the architectural gap of the legacy agent.
3. Provides necessary aggregation capabilities (e.g., finding which temples have accommodation or wheelchair access) that `ItineraryPlanningAgent` will later depend upon.
4. Keeps Phase L scoped, coherent, and deterministic.

---

## 15. Proposed Phase L Architecture

```text
User Query ("Which temples have wheelchair facilities?")
    ↓
AgentState
    ↓
MasterAgentCoordinator
    ↓
AgentRouter (Intent: "cross_temple_aggregation" -> selected_agent: "cross_temple_aggregation")
    ↓
CrossTempleAggregationAgent.execute(state)
    ↓
[Category & Condition Extraction via CategoryRegistry / QueryPlanner]
    ↓
RAGTool (Iterates across 20 registered temples)
    ↓
Completeness Validation (CONFIRMED_AVAILABLE vs CONFIRMED_UNAVAILABLE vs INFORMATION_NOT_AVAILABLE)
    ↓
Deduplication & Verified Source Attribution
    ↓
Structured Grounded Summary Response
    ↓
AgentResponse (sources, metadata: matching_count, confirmed_available, etc.)
```

### Key Behavioral Safeguards:
- **Universal 20-Temple Coverage**: Every registered temple is inspected.
- **Three-Tier Categorization**:
  - `CONFIRMED_AVAILABLE`: Explicit affirmative evidence.
  - `CONFIRMED_UNAVAILABLE`: Explicit negative evidence.
  - `INFORMATION_NOT_AVAILABLE`: Unrecorded in knowledge base (never infer false absence).
- **Condition Sensitivity**: Supports both positive queries (`"Which temples have river bank?"`) and negative queries (`"Which temples do not have parking?"`).
- **Backward Compatibility**: Preserves legacy methods (`aggregate_temples`, `format_response`, `detect_aggregation_intent`, `validate_match`) so that `backend/app/rag/chat.py` and existing legacy tests do not break.

---

## 16. Proposed Files

### Files to Modify (Minimal):
- `backend/app/agents/cross_temple_aggregation_agent.py`: Refactor to inherit from `BaseAgent`, implement `_run(state: AgentState) -> AgentResponse`, and consume `RAGTool` while retaining backward-compatible methods.
- `backend/app/agents/router.py`: Enable dynamic routing to `cross_temple_aggregation` when registered; preserve fallback when unregistered.
- `backend/app/agents/coordinator.py`: Accept optional `cross_temple_agent: Optional[Any] = None` and synchronize with router.

### New Files:
- `tests/test_cross_temple_aggregation_agent.py`: Dedicated 25+ test suite for Phase L compliance.
- `docs/PHASE_L_CROSS_TEMPLE_AGGREGATION.md`: Comprehensive Phase L documentation.

### Protected Files (DO NOT MODIFY):
- `417 source JSON files`
- `qdrant_db/`
- `bm25_index/`
- `evaluation/`
- `.env`
- `frontend/`
- `backend/app/api/chat.py`
- `backend/app/main.py`
- `backend/app/rag/chat.py`
- `backend/app/rag/query_planner.py`
- `backend/app/rag/knowledge_registry.py`

---

## 17. Proposed Router Changes

In `backend/app/agents/router.py`:
- Priority 5 currently returns `selected_agent="none"`, `available=False`.
- Update to:
  ```python
  is_active = "cross_temple_aggregation" in self.active_agents
  return AgentRouteDecision(
      selected_agent="cross_temple_aggregation" if is_active else "none",
      intent="cross_temple_aggregation",
      confidence=0.90,
      reason="Query matches cross-temple aggregation intent and is routed to CrossTempleAggregationAgent." if is_active else "Query matches cross-temple aggregation intent, but CrossTempleAggregationAgent is not yet implemented.",
      metadata={
          "available": is_active,
          "target_agent": "CrossTempleAggregationAgent"
      }
  )
  ```
- Unregistered state preserves exact previous behavior.

---

## 18. Proposed Coordinator Changes

In `backend/app/agents/coordinator.py`:
- Add `cross_temple_agent: Optional[Any] = None` to `__init__`.
- If provided:
  ```python
  if cross_temple_agent is not None:
      self.agents[cross_temple_agent.name] = cross_temple_agent
  ```
- Sync with router via `self.router.register_agent(agent_name)`.
- When absent, maintains exact fallback behavior.

---

## 19. Phase H Compatibility

Ensure `SequentialMultiIntentPipeline` can execute decomposed queries combining factual, comparison, and cross-temple aggregation requests:
- Example: `"What are the timings of Yadadri? Which temples have river bank?"`
  - Sub-task 1: `temple_information` $\to$ `TempleInformationAgent`
  - Sub-task 2: `cross_temple_aggregation` $\to$ `CrossTempleAggregationAgent`
  - Pipeline executes sequentially and aggregates results.

---

## 20. Phase I Compatibility

Ensure multi-turn queries interact cleanly with `ConversationMemoryManager`:
- A cross-temple aggregation query resets single-temple scope (does not attach prior single-temple focus to global queries like `"Which temples have river bank?"`).
- If an ambiguous pronoun query follows an aggregation, memory resolves or prompts clarification appropriately.

---

## 21. Phase J Compatibility

Cross-temple aggregation operates across 20 temples for a single category/property, whereas Phase J complete-list retrieval operates within a single temple across complete records. Both leverage `KnowledgeRegistry` / parent text mechanisms without conflict.

---

## 22. Test Plan

Create `tests/test_cross_temple_aggregation_agent.py` with **25+ tests**:
1. BaseAgent inheritance contract
2. Agent initialization and name/description
3. Agent lifecycle execution (`_run` returns `AgentResponse`)
4. Execution trace recording in `state.execution_trace`
5. Latency measurement ($> 0$ ms)
6. Router registration and activation
7. Coordinator registration and dispatch
8. Positive aggregation: River bank (11 temples match)
9. Positive aggregation: Wheelchair accessibility
10. Positive aggregation: Accommodation
11. Positive aggregation: Annadanam / Prasadam
12. Negative aggregation: Temples without specific facility
13. Three-tier categorization (`CONFIRMED_AVAILABLE`, `CONFIRMED_UNAVAILABLE`, `INFORMATION_NOT_AVAILABLE`)
14. Completeness validation across all 20 temples
15. Strict RAGTool dependency boundary (zero raw DB imports)
16. Source attribution preservation (JSON files per temple)
17. Deduplication of matched temples
18. Empty query handling
19. Whitespace query handling
20. Unrecognized category / property handling
21. Multi-intent pipeline compatibility (Phase H)
22. Conversation memory compatibility (Phase I)
23. Backward-compatible `aggregate_temples` method
24. Backward-compatible `format_response` method
25. Backward-compatible `detect_aggregation_intent` method
26. Coordinator fallback when unregistered
27. Deterministic repeated execution

---

## 23. Data Integrity Plan

After implementation, verify:
- All 20 temple directories intact
- All 417 JSON files intact
- Specific counts:
  - Dharmapuri sevas = 10
  - Yadadri facilities = 26
  - Edupayala prasadam = 2
  - River bank temples = 11
- Zero index rebuilds

---

## 24. Risk Analysis

| Risk | Impact | Concrete Mitigation |
|---|---|---|
| **Breaking `chat.py` Inverted Import** | High | `CrossTempleAggregationAgent` must retain its public methods (`aggregate_temples`, `format_response`, `detect_aggregation_intent`) as backward-compatible wrappers while implementing `_run(state)`. |
| **Breaking Legacy Tests** | Medium | Keep `tests/test_cross_temple_aggregation.py` running green against the backward-compatible methods. |
| **RAG Boundary Leakage** | Medium | Inject `RAGTool` and use `rag_tool.get_temple_category_data()` and `rag_tool.get_registered_temples()`. Add static AST boundary test. |
| **False Absence Inference** | High | Strictly distinguish `CONFIRMED_UNAVAILABLE` from `INFORMATION_NOT_AVAILABLE` using `CompletenessValidator`. |
| **Router Regressions** | High | Router only activates `cross_temple_aggregation` when registered in `active_agents`. Phase D tests remain green. |

---

## 25. Implementation Order

- **Step L1**: Audit & Plan Approval (Current Step).
- **Step L2**: Refactor `CrossTempleAggregationAgent(BaseAgent)` with `RAGTool` integration and backward-compatible wrappers.
- **Step L3**: Update `AgentRouter` for `cross_temple_aggregation` registration.
- **Step L4**: Update `MasterAgentCoordinator` for `cross_temple_agent` dependency injection.
- **Step L5**: Verify multi-intent pipeline and conversation memory compatibility.
- **Step L6**: Implement `tests/test_cross_temple_aggregation_agent.py` (25+ tests).
- **Step L7**: Run full regression suite (220 baseline + 25+ Phase L tests = 245+ passed).
- **Step L8**: Verify dataset integrity (417 JSONs, 20 temples, ground truth counts).
- **Step L9**: Create `docs/PHASE_L_CROSS_TEMPLE_AGGREGATION.md`.
- **Step L10**: Final Certification and STOP.

---

## 26. Acceptance Criteria

- `CrossTempleAggregationAgent` is a verified subclass of `BaseAgent`.
- Lifecycle methods `execute(state)` and `_run(state)` function cleanly.
- `RAGTool` is the exclusive knowledge access facade.
- Router routes aggregation queries when registered.
- Coordinator dispatches aggregation queries end-to-end.
- Existing 220 tests remain 100% green.
- Legacy `test_cross_temple_aggregation.py` remains green.
- All 25+ new Phase L tests pass.
- Dataset remains 100% frozen.

---

## 27. Phase M: NOT STARTED

`ItineraryPlanningAgent` is reserved for **Phase M**. No Phase M code or planning will begin until Phase L is certified.
