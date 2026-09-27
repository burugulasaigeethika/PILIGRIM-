# PilgrimAI — Phase M: ItineraryPlanningAgent Certification Report

**Date:** September 20, 2026  
**Project:** PilgrimAI: A RAG-Based Multi-Agent Assistant for Smart Pilgrimage  
**Workspace:** `D:\pligrim ai new`  
**Certification Status:** CERTIFIED COMPLETE  
**Phase N Status:** NOT STARTED  

---

## 1. Objective

Phase M implemented a dedicated specialist agent, `ItineraryPlanningAgent`, extending `BaseAgent` to provide grounded, timing-aware single-temple and multi-temple pilgrimage itinerary planning across all 20 registered temples in Telangana.

The agent adheres strictly to:
- Grounded scheduling using verified temple timings, sevas, accommodation, travel, prasadam, crowd, and facilities data.
- Strict Fact vs. Suggestion separation (every scheduling recommendation is explicitly partitioned from verified temple facts).
- Zero fabricated travel times, driving durations, or routes between arbitrary temples.
- Strict disclosure of live-data limitations via a mandatory deterministic Live-Data Disclaimer.
- Exclusive factual retrieval through `RAGTool` (zero direct database, raw file, or vector store access).
- Seamless interoperability with `AgentRouter`, `MasterAgentCoordinator`, `SequentialMultiIntentPipeline`, and `ConversationMemoryManager`.

---

## 2. Architecture

```text
User Query
    ↓
AgentState
    ↓
MasterAgentCoordinator (Orchestrator)
    ↓
ConversationMemoryManager (Multi-turn Pronoun Resolution)
    ↓
AgentRouter (Priority 4: Itinerary Planning Intent)
    ↓
ItineraryPlanningAgent (BaseAgent Specialist)
    ↓
RAGTool (Read-Only Knowledge Facade)
    ↓
Verified Knowledge Base (timings, sevas, travel, accommodation, prasadam, crowd, facilities)
    ↓
AgentResponse (Grounded Schedule + Fact/Suggestion Separation + Disclaimer)
    ↓
ResponseAggregator (Composition Layer)
```

---

## 3. Agent Contract

- **Class**: `ItineraryPlanningAgent(BaseAgent)`
- **Module**: `backend/app/agents/itinerary_planning_agent.py`
- **Agent Name**: `itinerary_planning`
- **Public Lifecycle**: Inherits standard `execute(state: AgentState) -> AgentResponse` from `BaseAgent`, measuring latency, tracking execution trace, and catching unhandled exceptions cleanly.
- **Core Internal Entrypoint**: `_run(state: AgentState) -> AgentResponse`
- **Metadata Returned**:
  ```python
  {
      "itinerary": True,
      "temples": detected_temples,
      "duration_days": duration_days,
      "sources_by_temple": sources_by_temple,
      "disclaimer_present": True
  }
  ```

---

## 4. RAGTool Boundary

`ItineraryPlanningAgent` strictly respects the RAG boundary:
- Operates exclusively through `self.rag_tool` dependency injection (`RAGTool`).
- Uses lazy initialization (`@property def rag_tool`) to prevent circular import loops between the agent layer and the RAG foundation.
- Performs category-specific queries through `rag_tool.retrieve(query, temple, category)` for relevant categories only (`timings`, `sevas`, `travel`, `accommodation`, `prasadam`, `crowd`, `facilities`).
- Has **ZERO** direct imports or usage of:
  - `PilgrimRAGService`
  - `qdrant_client`
  - `rank_bm25`
  - `sentence_transformers`
  - `CrossEncoder`
  - `LocalQdrantManager`
  - `open()` / `json.load()` filesystem access

---

## 5. Supported Itinerary Capabilities

1. **Single-Temple Grounded Itinerary**:
   - Synthesizes 1-day or multi-day itineraries for a single registered temple.
   - Grounded in verified morning opening hours, afternoon sanctum breaks, evening darshans, and night closing.
2. **Multi-Temple Pilgrimage Sequencing**:
   - Sequences up to 3 temples across distinct pilgrimage days (e.g., Day 1 — Yadadri, Day 2 — Dharmapuri).
   - Grounded in verified static data for each temple.
3. **Fact vs. Suggestion Demarcation**:
   - Distinct sections: `**Verified Temple Information:**` vs `**Suggested Visit Plan:**` (Morning, Afternoon, Evening windows).
4. **Controlled Refusal & Clarification**:
   - Rejects unregistered / unknown temples (e.g., "Atlantis Temple") with explicit refusal.
   - Prompts for clarification on zero-temple queries (e.g., "Plan a pilgrimage itinerary for me").
   - Safely contains empty or whitespace queries.

---

## 6. Timing-Aware Planning

- Fetches `timings` category via `RAGTool`.
- Incorporates official opening hours, afternoon closing/break periods, and evening darshan slots.
- Does not hardcode schedules; all times are derived dynamically from verified temple records.

---

## 7. Seva-Aware Planning

- Fetches `sevas` category via `RAGTool`.
- When users request a visit centered around morning/special rituals, the agent extracts verified sevas, ritual names, timings, and ticket prices from `sevas.json`.
- Zero hallucination: if no matching seva exists, the agent explicitly states that records do not contain a matching seva.

---

## 8. Travel-Data Limitations & No Fabricated Durations

- The underlying dataset contains static `travel.json` notes (nearest railway station, airport, highway connectivity, distance to Hyderabad).
- **Anti-Hallucination Invariant**: The agent **NEVER** calculates or invents driving durations or route times between temples (e.g., never generates "takes 2 hours 15 minutes to drive from Yadadri to Dharmapuri").
- Mandatory deterministic Live-Data Disclaimer included on all generated itineraries:
  ```text
  *(Live-Data Limitation: This itinerary is constructed strictly from verified static records. It does not include real-time traffic, live road conditions, real-time travel durations, live weather forecasts, or dynamic room booking availability. Please verify current local transit schedules and devasthanam announcements before departure).*
  ```

---

## 9. Accommodation & Prasadam Handling

- **Accommodation**:
  - Retrieved from `accommodation.json`.
  - Presented strictly as static options (on-site devasthanam guest houses, choultries, room types, booking rules).
  - Never claims live room availability or confirmed reservations.
- **Prasadam / Annadanam**:
  - Retrieved from `prasadam.json`.
  - Integrates free Annadanam lunch hours and prasadam counter availability into afternoon windows.

---

## 10. Router Integration

Updated `backend/app/agents/router.py`:
- Refined `_itinerary_patterns` to recognize duration prefixes (e.g., `plan a one-day visit`, `plan a 2-day tour`, `plan my visit`).
- Priority 4 dynamically checks active agents:
  - If `"itinerary_planning" in self.active_agents`: routes to `selected_agent="itinerary_planning"`, `available=True`.
  - If not active: preserves fallback to `selected_agent="none"`, `available=False`.
- Checked conjoined sub-intents: if an itinerary query contains conjoined sub-intents (e.g. timings + itinerary), it routes to `multi_intent` for ordered sequential dispatch.

---

## 11. Coordinator Integration

Updated `backend/app/agents/coordinator.py`:
- Added `itinerary_agent: Optional[Any] = None` to `MasterAgentCoordinator.__init__`.
- Registered `itinerary_agent` in `self.agents` and dynamically registered with `self.router`.
- Integrated with `is_unimplemented` fallback check.

---

## 12. Multi-Intent Compatibility (Phase H)

- Compound queries like `"What are the timings of Yadadri and plan a one-day visit there"` are recognized as `multi_intent`.
- `SequentialMultiIntentPipeline` decomposes the query into:
  - Task 1: `"What are the timings of Yadadri"` $\to$ `TempleInformationAgent`
  - Task 2: `"plan a one-day visit there at Yadadri temple"` $\to$ `ItineraryPlanningAgent`
- Both responses are aggregated seamlessly into a unified output.

---

## 13. Conversation Memory Compatibility (Phase I)

- Multi-turn queries using pronouns (e.g., Turn 1: `"Tell me about Yadadri"`, Turn 2: `"Plan a one-day visit there"`) are resolved by `ConversationMemoryManager` to explicit temple names before dispatching to `ItineraryPlanningAgent`.

---

## 14. Test Suite

Created `tests/test_itinerary_planning_agent.py` containing **27 comprehensive tests**:

| Test | Name | Coverage | Result |
|---|---|---|---|
| 1 | `test_1_base_agent_inheritance` | `isinstance(agent, BaseAgent)` & hooks | PASSED |
| 2 | `test_2_agent_name_and_description` | Name `itinerary_planning` & description | PASSED |
| 3 | `test_3_constructor_dependency_injection` | Custom `RAGTool` injection | PASSED |
| 4 | `test_4_agent_lifecycle_and_response` | `AgentResponse` contract & metadata | PASSED |
| 5 | `test_5_execution_trace` | `ExecutionTrace` step tracking & latency | PASSED |
| 6 | `test_6_router_registration` | Dynamic registration & routing | PASSED |
| 7 | `test_7_router_inactive_fallback` | Preserves `selected_agent="none"` fallback | PASSED |
| 8 | `test_8_coordinator_registration` | Coordinator agent registration | PASSED |
| 9 | `test_9_coordinator_dispatch` | End-to-end coordinator execution | PASSED |
| 10 | `test_10_single_temple_one_day_itinerary` | Single temple schedule & Fact vs Suggestion | PASSED |
| 11 | `test_11_multi_temple_two_day_itinerary` | Multi-temple 2-day itinerary sequencing | PASSED |
| 12 | `test_12_timing_aware_planning` | Verified opening & darshan hours integration | PASSED |
| 13 | `test_13_seva_aware_planning` | Seva integration and source grounding | PASSED |
| 14 | `test_14_annadanam_prasadam_integration` | Meal & Annadanam schedule integration | PASSED |
| 15 | `test_15_accommodation_guidance` | Static accommodation guidance | PASSED |
| 16 | `test_16_live_data_disclaimer` | Mandatory deterministic disclaimer | PASSED |
| 17 | `test_17_no_fabricated_travel_durations` | Zero fabricated inter-temple driving times | PASSED |
| 18 | `test_18_source_attribution` | Grounded JSON source attribution | PASSED |
| 19 | `test_19_unknown_temple` | Controlled refusal for unregistered temples | PASSED |
| 20 | `test_20_zero_temple_clarification` | Clarification request for zero-temple queries | PASSED |
| 21 | `test_21_empty_query` | Safe error containment on empty query | PASSED |
| 22 | `test_22_whitespace_query` | Safe error containment on whitespace query | PASSED |
| 23 | `test_23_multi_intent_compatibility` | Phase H sequential pipeline execution | PASSED |
| 24 | `test_24_conversation_memory_compatibility` | Phase I multi-turn pronoun resolution | PASSED |
| 25 | `test_25_complete_list_registry_alignment` | All 20 canonical temples detected | PASSED |
| 26 | `test_26_strict_rag_boundary` | Zero forbidden imports AST check | PASSED |
| 27 | `test_27_deterministic_repeated_execution` | Identical output across repeated runs | PASSED |

---

## 15. Regression Results

All 15 certified suites pass with zero failures:

| Category | Suites | Tests | Result |
|---|---|---|---|
| Pre-Phase-M Modern Baseline | 13 suites (`test_agent_contracts`, `test_rag_tool`, `test_temple_information_agent`, `test_agent_router`, `test_response_aggregator`, `test_master_agent_coordinator`, `test_agent_state`, `test_multi_intent_pipeline`, `test_conversation_memory`, `test_query_planner`, `test_complete_list_retrieval`, `test_comparison_agent`, `test_cross_temple_aggregation_agent`) | 248/248 | PASSED |
| Legacy Suite | 1 suite (`test_cross_temple_aggregation`) | 13/13 | PASSED |
| Phase M Suite | 1 suite (`test_itinerary_planning_agent`) | 27/27 | PASSED |
| **TOTAL** | **15 suites** | **288/288** | **100% PASS** |

---

## 16. Data Integrity Results

- **Temple Directories**: 20 verified (all 20 exist).
- **Source JSON Files**: 417 verified.
- **Ground Truth Item Counts**:
  - Dharmapuri sevas = 10 verified.
  - Yadadri facilities = 26 verified.
  - Edupayala prasadam = 2 verified.
  - River-bank temples = 11 verified.
- **Protected Directories & Files**:
  - `qdrant_db/`: untouched.
  - `bm25_index/`: untouched.
  - `evaluation/`: untouched.
  - `.env`: untouched.
  - `frontend/`: untouched.
  - `backend/app/api/chat.py`: untouched.
  - `backend/app/main.py`: untouched.
  - `backend/app/rag/`: untouched.

---

## 17. Static RAG Boundary Audit

Automated AST and textual inspection of `backend/app/agents/itinerary_planning_agent.py`:
- Forbidden DB imports (`qdrant_client`, `rank_bm25`, `sentence_transformers`, `CrossEncoder`, `LocalQdrantManager`, `LocalBM25Manager`, `PilgrimRAGService`): **NONE**
- Forbidden filesystem direct access (`open(`, `json.load`): **NONE**
- RAG Boundary Audit: **PASS**

---

## 18. Known Limitations

- Real-time traffic, dynamic driving times, weather forecasts, and live room booking are strictly out-of-scope and not simulated.
- Static travel notes from `travel.json` provide regional transit guidance, but inter-temple driving durations are never fabricated.

---

## 19. Certification

Phase M is certified **COMPLETE**.  
All tests, integrity checks, and regression suites are green.  
Phase N is **NOT STARTED**.
