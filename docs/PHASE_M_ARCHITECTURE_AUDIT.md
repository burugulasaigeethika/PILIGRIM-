# PilgrimAI — Phase M: ItineraryPlanningAgent Architecture Audit & Implementation Plan

**Date:** September 20, 2026  
**Project:** PilgrimAI: A RAG-Based Multi-Agent Assistant for Smart Pilgrimage  
**Workspace:** `D:\pligrim ai new`  
**Audit Type:** Architecture Audit & Implementation Plan (No Production Code Modified)  
**Status:** Audit Complete — Implementation NOT Started  

---

## 1. Current Certified Baseline

Phase L was successfully certified. The repository currently maintains a 100% green certified baseline across all 14 test suites:

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
| **—** | **Subtotal Modern Test Baseline** | **248/248** | **100% GREEN** |
| 14 | `test_cross_temple_aggregation.py` (Legacy RAG Compatibility) | 13/13 | PASSED |
| **TOTAL** | **Certified Regression Baseline (Modern + Legacy)** | **261/261** | **100% GREEN** |

All protected assets remain completely intact:
- 20 temple directories
- 417 source JSON files
- `qdrant_db/` (1,578 parent chunks)
- `bm25_index/` (4,458 child chunks)
- Verified ground truth counts: Dharmapuri sevas = 10, Yadadri facilities = 26, Edupayala prasadam = 2, River-bank temples = 11.

---

## 2. Current Agent Inventory

Inspection of `backend/app/agents/` confirms the following specialist agent inventory:

| Agent Name | Source File | Router Intent | Registration Status | Coordinator Integration | Verified Test Coverage |
|---|---|---|---|---|---|
| `TempleInformationAgent` | `backend/app/agents/temple_information_agent.py` | `temple_information` | Registered by default (`active_agents`) | Primary default specialist | `tests/test_temple_information_agent.py` (10 tests) |
| `ComparisonAgent` | `backend/app/agents/comparison_agent.py` | `comparison` | Registered dynamically via `router.register_agent("comparison")` | Conditionally injected via `comparison_agent` param | `tests/test_comparison_agent.py` (30 tests) |
| `CrossTempleAggregationAgent` | `backend/app/agents/cross_temple_aggregation_agent.py` | `cross_temple_aggregation` | Registered dynamically via `router.register_agent("cross_temple_aggregation")` | Conditionally injected via `cross_temple_agent` param | `tests/test_cross_temple_aggregation_agent.py` (28 tests) + legacy (13 tests) |
| `ItineraryPlanningAgent` | *(Non-existent)* | `itinerary_planning` | **NOT REGISTERED** (`selected_agent="none"`, `available=False`) | **NOT INTEGRATED** (`is_unimplemented` fallback) | Router recognition test only (`test_agent_router.py`) |

---

## 3. Existing Phase M Roadmap

In [`docs/AGENT_REBUILD_AUDIT.md`](file:///D:/pligrim ai new/docs/AGENT_REBUILD_AUDIT.md) Section 11, Phase M is specified as:
```text
### Phase M: ItineraryPlanningAgent
- Implement pilgrimage itinerary generator considering opening hours, sevas, and travel times.
```
In `backend/app/agents/router.py`, the routing layer already defines `self._itinerary_patterns` matching:
- `plan (a) trip / tour / visit / itinerary / journey / travel`
- `itinerary for / to`, `tour plan`, `travel itinerary`, `day trip`, `weekend trip`
- `how to plan (my) visit`

However, the roadmap description must be critically audited against real repository capabilities rather than implemented blindly.

---

## 4. ItineraryPlanningAgent Current Status
- **Source Code**: Does not exist (0% implemented).
- **Router Status**: Evaluated at Priority 4. Query matching `_itinerary_patterns` returns:
  - `intent="itinerary_planning"`
  - `selected_agent="none"`
  - `confidence=0.90`
  - `metadata={"available": False, "target_agent": "ItineraryPlanningAgent"}`
- **Coordinator Status**: Evaluated under `is_unimplemented`, returning:
  `"The requested capability ('Itinerary Planning') is not yet available in the current agent build."`
- **Tests**: Only intent classification in `test_agent_router.py`.

---

## 5. Available Knowledge in Current Repository

Detailed inspection of the 417 JSON files across 20 temples reveals what factual data is available:

| Category Key | Attested Facts Available in Knowledge Base | Application to Itinerary Planning |
|---|---|---|
| `timings` | Opening hours, closing hours, afternoon break, morning/evening darshan slots | Establishes feasible visit windows (morning, afternoon rest, evening darshan) |
| `sevas` | Daily and periodic sevas, ritual names, timings, ticket prices | Suggests specific morning or evening rituals (e.g., Suprabhata Seva, Nijabhishekam) |
| `travel` | General transit options, highway connectivity, distance to nearest railway station/airport/Hyderabad | Provides regional transit advice and nearest rail/air connectivity |
| `accommodation`| Verified guest houses, rooms, cottages, booking rules | Recommends on-site overnight stay options |
| `crowd` | Busy days, peak rush hours, expected queue times | Informs optimal arrival windows to minimize queue wait |
| `prasadam` | Free Annadanam meal hours, prasadam counter timings | Schedules lunch/meal breaks aligned with temple Annadanam hours |
| `facilities` | Cloakrooms, parking, wheelchairs, drinking water | Notes practical visitor amenities |

---

## 6. Travel-Time and Navigation Capability Audit

**Crucial Finding**:
- The knowledge base contains static transit notes (e.g. `Raigir Railway Station is 6 km away`, `Located ~60 km from Hyderabad on NH-163`).
- It does **NOT** contain a pairwise distance/duration matrix between arbitrary temples (e.g., distance from Dharmapuri to Ahobilam).
- It does **NOT** contain road navigation, live traffic routing, or GPS coordinate calculations.
- **Strict Anti-Hallucination Boundary**:
  - The agent MUST NOT generate fabricated travel times between arbitrary temples (e.g., claiming "Dharmapuri to Yadadri takes 3 hours 12 minutes").
  - The agent MUST clearly distinguish verified static transit notes from arbitrary inter-temple travel estimations.
  - The agent MUST include a deterministic disclaimer when travel times or route conditions are not available in verified records.

---

## 7. Live-Agent Status

Grep and filesystem audits confirm:
- `LiveNavigationAgent`: **NON-EXISTENT** (0%)
- `LiveWeatherAgent`: **NON-EXISTENT** (0%)
- `LivePlacesBookingAgent`: **NON-EXISTENT** (0%)
- `VoiceMultilingualAgent`: **NON-EXISTENT** (0%)

**Enforced Constraint**:
Because external live API agents do not exist in the current architecture, Phase M MUST NOT attempt to mock, fabricate, or hallucinate:
1. Live traffic conditions
2. Live weather forecasts
3. Real-time road closures or travel durations
4. Live room availability or booking reservations
5. Real-time queue or crowd sensor data

---

## 8. BaseAgent Contract for ItineraryPlanningAgent

The agent will strictly conform to the Phase A `BaseAgent` lifecycle:
```python
class ItineraryPlanningAgent(BaseAgent):
    name = "itinerary_planning"
    description = "Specialist agent providing grounded, timing-aware pilgrimage itinerary planning across registered temples using verified knowledge."

    def __init__(
        self,
        rag_tool: Optional[RAGTool] = None,
        name: str = "itinerary_planning",
        description: str = "..."
    ):
        super().__init__(name=name, description=description)
        self.rag_tool = rag_tool or RAGTool()

    def _run(self, state: AgentState) -> AgentResponse:
        ...
```
- Execution is triggered via `agent.execute(state)`.
- Enforces standardized execution timing, error containment, execution trace updates, and populates `state.intermediate_results["itinerary_planning"]`.

---

## 9. RAGTool Boundary

`ItineraryPlanningAgent` will access factual data strictly through `RAGTool` (`backend/app/agents/tools/rag_tool.py`):
- `rag_tool.get_registered_temples()`: Validates requested temples against the 20 canonical pilgrimage sites.
- `rag_tool.get_temple_category_data(temple, category)`: Fetches static records for `timings`, `sevas`, `travel`, `accommodation`, `prasadam`, and `crowd`.
- `rag_tool.get_complete_parent_text(temple, category)`: Retrieves full category context where needed.
- `rag_tool.retrieve(query, temple, category, top_k)`: Scoped semantic candidate retrieval.
- **Zero Forbidden Imports**: AST inspection will enforce zero imports of `PilgrimRAGService`, `qdrant_client`, `rank_bm25`, `sentence_transformers`, `LocalQdrantManager`, `CrossEncoder`, or raw filesystem JSON paths.

---

## 10. Router Audit & Proposed Changes

In `backend/app/agents/router.py`:
- Priority 4 currently returns `selected_agent="none"`, `available=False`.
- Update Priority 4:
  ```python
  is_active = "itinerary_planning" in self.active_agents
  return AgentRouteDecision(
      selected_agent="itinerary_planning" if is_active else "none",
      intent="itinerary_planning",
      confidence=0.90,
      reason="Query matches itinerary planning intent and is routed to ItineraryPlanningAgent." if is_active else "Query matches itinerary planning intent, but ItineraryPlanningAgent is not yet implemented.",
      metadata={
          "available": is_active,
          "target_agent": "ItineraryPlanningAgent",
          "detected_temples": detected_temples
      }
  )
  ```
- When `ItineraryPlanningAgent` is registered, queries route to it (`available=True`).
- When unregistered, preserves the exact Phase D fallback.

---

## 11. Coordinator Audit & Proposed Changes

In `backend/app/agents/coordinator.py`:
- Add `itinerary_agent: Optional[Any] = None` to `__init__`.
- Register in `self.agents` and synchronize with `router.register_agent("itinerary_planning")`.
- Update `is_unimplemented`:
  ```python
  is_unimplemented = (
      (route_decision.intent == "itinerary_planning" and "itinerary_planning" not in self.agents) or
      (route_decision.intent == "cross_temple_aggregation" and "cross_temple_aggregation" not in self.agents) or
      (route_decision.intent == "comparison" and "comparison" not in self.agents) or
      route_decision.selected_agent not in self.agents
  )
  ```
- When present, dispatches itinerary queries directly to `itinerary_agent.execute(state)`.

---

## 12. Multi-Intent Pipeline Compatibility

The existing `SequentialMultiIntentPipeline` will handle compound queries involving itinerary planning without requiring redesign:
- Example: `"What are the timings of Yadadri? Plan a one-day visit there"`
  - Task 1: `temple_information` $\to$ `TempleInformationAgent`
  - Task 2: `itinerary_planning` $\to$ `ItineraryPlanningAgent`
- Example: `"Compare Yadadri and Dharmapuri, then plan a 2-day pilgrimage"`
  - Task 1: `comparison` $\to$ `ComparisonAgent`
  - Task 2: `itinerary_planning` $\to$ `ItineraryPlanningAgent`

---

## 13. Conversation Memory Compatibility

Integration with `ConversationMemoryManager`:
- Turn 1: *"I want to visit Yadadri and Dharmapuri."*
- Turn 2: *"Plan a 2-day itinerary for them."*
- `ConversationMemoryManager.resolve_query()` will resolve pronouns to the recent canonical temples (`Yadadri` and `Dharmapuri`), passing the resolved query to `ItineraryPlanningAgent`.
- Queries lacking identifiable temples will safely trigger clarification prompts rather than guessing.

---

## 14. CrossTempleAggregationAgent Integration

For queries such as *"Plan an itinerary visiting temples with river bank access"*:
- Direct agent-to-agent coupling is avoided.
- The itinerary agent extracts candidate temples using verified metadata or multi-intent pipeline coordination, evaluating candidate temples via `RAGTool`.

---

## 15. ComparisonAgent Integration

Comparison and itinerary planning remain strictly separated:
- Comparison focuses on side-by-side contrast of attributes.
- Itinerary planning focuses on sequential chronological scheduling (Day 1, Day 2, morning, afternoon, evening).
- Interactions between the two are orchestrated via `SequentialMultiIntentPipeline`.

---

## 16. Itinerary Output Contract

The generated output will be clean, structured Markdown distinguishing **Verified Facts** from **Planning Suggestions**:

```markdown
### Pilgrimage Itinerary: Yadadri & Dharmapuri (2 Days)

#### Day 1: Yadadri Temple
- **Morning Window (4:00 AM – 12:00 PM)**:
  - *Verified Darshan Timings*: 4:00 AM to 9:45 PM (Afternoon rest: 3:00 PM – 4:00 PM).
  - *Recommended Seva*: Suprabhata Seva (Early morning ritual).
- **Afternoon Window (12:00 PM – 4:00 PM)**:
  - *Prasadam / Lunch*: Free Annadanam counters available. Note temple afternoon break between 3:00 PM and 4:00 PM.
- **Evening Window (4:00 PM – 9:00 PM)**:
  - *Darshan & Harathi*: Evening darshan and Maha Harathi.
- **Accommodation & Logistics**:
  - *Verified Stays*: TGRTC guest houses and Devasthanam cottages available on-site.

#### Day 2: Dharmapuri Temple
...

---
*(Note: Travel times, road traffic conditions, live weather forecasts, and dynamic room availability are not available in the verified knowledge base. Please verify local transit schedules before travel).*

**Sources:**
- **Yadadri**: yadadri/timings.json, yadadri/sevas.json, yadadri/accommodation.json
- **Dharmapuri**: dharmapuri/timings.json, dharmapuri/sevas.json
```

---

## 17. Error Handling

Deterministic, grounded handling for all edge cases:
- **Empty / Whitespace Query**: Returns `success=False`, `error="Empty query"`.
- **Explicit Unknown Temple** (*"Plan a trip to Atlantis Temple"*): Returns controlled refusal indicating the temple is not in the 20 registered sites (`error="Unregistered temple"`). Zero hallucination.
- **Zero Temples Specified** (*"Plan a pilgrimage itinerary"*): Prompts user to specify temples (`error="Missing temple specification"`).
- **Missing Specific Category** (e.g. no verified accommodation record for a temple): Explicitly states no verified accommodation records exist; does NOT claim false absence.

---

## 18. Proposed Phase M Scope

### 19. In-Scope Capabilities
1. Grounded single-temple 1-day itinerary planning.
2. Grounded multi-temple multi-day itinerary sequencing (up to 3 temples).
3. Timing-aware visit structuring (morning opening, afternoon break, evening closing).
4. Seva-aware suggestions based on verified `sevas.json` records.
5. Annadanam & meal window integration based on verified `prasadam.json`.
6. Accommodation guidance based on verified `accommodation.json`.
7. Transit guidance based on verified `travel.json` (nearest rail, airport, highway).
8. Deterministic Live-Data Disclaimer.
9. Full integration with Router, Coordinator, Pipeline, and Memory.

### 20. Out-of-Scope Capabilities
1. Live navigation, turn-by-turn directions, GPS routing.
2. Real-time traffic, congestion levels, or road delays.
3. Arbitrary pairwise travel time calculations (e.g. "it takes 2 hours 15 mins to drive").
4. Live weather reports, rain forecasts, temperature data.
5. Real-time room booking availability, checkout payments.
6. Dynamic crowd density sensor readings.

---

## 21. Proposed Files

### Files to Create:
- `backend/app/agents/itinerary_planning_agent.py`: Specialist agent implementation.
- `tests/test_itinerary_planning_agent.py`: 25+ comprehensive test cases.
- `docs/PHASE_M_ITINERARY_PLANNING.md`: Full documentation and certification report.

### Files to Modify (Minimal):
- `backend/app/agents/router.py`: Enable dynamic routing for Priority 4 (`itinerary_planning`).
- `backend/app/agents/coordinator.py`: Accept `itinerary_agent` dependency and register with router.

### Protected Files (DO NOT MODIFY):
- 417 source JSON files
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

## 22. Proposed Architecture

```text
User Query ("Plan a 2-day pilgrimage to Yadadri and Dharmapuri")
    ↓
AgentState
    ↓
MasterAgentCoordinator
    ↓
AgentRouter (Intent: "itinerary_planning" -> selected_agent: "itinerary_planning")
    ↓
ItineraryPlanningAgent.execute(state)
    ↓
[Temple & Duration Extraction]
    ↓
RAGTool (Per-temple retrieval for timings, sevas, travel, accommodation, prasadam)
    ↓
Chronological Sequencing & Window Allocation
    ├── Morning Window (Opening timings, morning sevas)
    ├── Afternoon Window (Afternoon break, Annadanam meal timings)
    └── Evening Window (Evening darshan, night closing, lodging)
    ↓
Disclaimer Integration (No live navigation, traffic, weather, booking)
    ↓
AgentResponse (Markdown answer, sources_by_temple, metadata)
    ↓
ResponseAggregator
```

---

## 23. Proposed Implementation Order

- **M1**: Audit & Plan Approval (Current Step).
- **M2**: Implement `ItineraryPlanningAgent(BaseAgent)` in `backend/app/agents/itinerary_planning_agent.py`.
- **M3**: Wire `AgentRouter` Priority 4 dynamic activation.
- **M4**: Wire `MasterAgentCoordinator` optional `itinerary_agent` dependency injection.
- **M5**: Implement test suite in `tests/test_itinerary_planning_agent.py` (25+ tests).
- **M6**: Verify multi-intent pipeline and conversation memory compatibility.
- **M7**: Run full regression suite (248 modern + 13 legacy + Phase M tests).
- **M8**: Verify dataset integrity (417 JSONs, 20 temples, ground truth counts).
- **M9**: Create `docs/PHASE_M_ITINERARY_PLANNING.md`.
- **M10**: Produce final certification report and STOP.

---

## 24. Test Plan (Minimum 25 Tests)

`tests/test_itinerary_planning_agent.py` will validate:
1. `test_1_base_agent_inheritance`: Inherits from `BaseAgent`.
2. `test_2_agent_name_and_description`: Verification of name and description.
3. `test_3_constructor_dependency_injection`: Custom `RAGTool` injection.
4. `test_4_agent_lifecycle_and_response_contract`: Execution contract and `AgentResponse`.
5. `test_5_execution_trace_recording`: Correct step tracing in `state.execution_trace`.
6. `test_6_router_registration_and_activation`: Route activation when registered.
7. `test_7_router_fallback_when_inactive`: Inactive fallback preservation.
8. `test_8_coordinator_registration`: Registration in `MasterAgentCoordinator`.
9. `test_9_coordinator_dispatch_end_to_end`: Full dispatch via coordinator.
10. `test_10_single_temple_one_day_itinerary`: Single temple 1-day plan.
11. `test_11_multi_temple_two_day_itinerary`: Multi-temple 2-day plan.
12. `test_12_timing_aware_window_allocation`: Incorporating verified opening/break hours.
13. `test_13_seva_aware_planning`: Incorporating verified morning/evening sevas.
14. `test_14_annadanam_prasadam_integration`: Lunch window aligned with Annadanam.
15. `test_15_accommodation_guidance`: Incorporating verified stay options.
16. `test_16_live_data_disclaimer_present`: Mandatory disclaimer regarding live traffic/weather.
17. `test_17_no_fabricated_travel_times`: Ensuring no fake inter-temple driving durations.
18. `test_18_source_attribution_preservation`: Preserving JSON source paths.
19. `test_19_unknown_temple_refusal`: Controlled refusal on unregistered temples.
20. `test_20_zero_temple_clarification`: Prompting user when no temple is specified.
21. `test_21_empty_query_handling`: Graceful handling of empty input.
22. `test_22_whitespace_query_handling`: Graceful handling of whitespace input.
23. `test_23_multi_intent_pipeline_compatibility`: Decomposing compound queries (Phase H).
24. `test_24_conversation_memory_compatibility`: Multi-turn pronoun resolution (Phase I).
25. `test_25_complete_list_compatibility`: Seamless operation with Phase J complete records.
26. `test_26_strict_rag_boundary`: Static AST audit enforcing zero raw DB imports.
27. `test_27_deterministic_repeated_execution`: Consistent output across repeated runs.

---

## 25. Data Integrity Plan

After Phase M implementation, verify:
- 20 temple directories intact
- 417 source JSON files intact
- Specific ground-truth counts unchanged:
  - Dharmapuri sevas = 10
  - Yadadri facilities = 26
  - Edupayala prasadam = 2
  - River-bank temples = 11
- Zero vector DB modifications, zero BM25 modifications.

---

## 26. Risk Analysis & Mitigations

| Risk | Impact | Concrete Mitigation |
|---|---|---|
| **Hallucinated Travel Durations** | High | Strictly prohibit calculating driving times between temples; limit travel output to verified static transit facts (nearest rail/airport/highway) and include the Live-Data Disclaimer. |
| **Hallucinated Temple Timings** | High | Every suggested visit window must ground in verified `timings.json` records retrieved via `RAGTool`. |
| **Circular Imports** | Medium | Use lazy property initialization for `RAGTool` (established in Phase L). |
| **Router Regressions** | High | Router Priority 4 activates ONLY when `"itinerary_planning"` is explicitly registered in `active_agents`. |
| **Coordinator Regressions** | High | Coordinator checks `(route_decision.intent == "itinerary_planning" and "itinerary_planning" not in self.agents)` before fallback. |

---

## 27. Acceptance Criteria

Phase M will be accepted only if:
- `ItineraryPlanningAgent` inherits from `BaseAgent`.
- Lifecycle `execute(state)` and `_run(state)` function cleanly.
- `RAGTool` is the exclusive knowledge access boundary.
- Zero forbidden direct RAG/database imports.
- Itinerary output contains grounded timings, sevas, transit, and accommodation where available.
- Zero fabricated travel times or distances.
- Deterministic Live-Data Disclaimer is present.
- Router and Coordinator integrations function cleanly.
- Phase H, Phase I, Phase J, Phase K, and Phase L remain fully compatible.
- All 261 existing tests remain green.
- All 25+ Phase M tests pass.
- Dataset and index integrity are 100% preserved.

---

## 28. Phase N: NOT STARTED

Phase N (`FastAPI /chat Integration`) is **NOT STARTED**. No Phase N code or planning will occur until Phase M is fully certified.
