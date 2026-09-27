# PilgrimAI — Emergency Agent Implementation Plan

**Date**: 2026-09-25  
**Component**: `EmergencyAgent` (Specialist Agent #9)  
**Status**: Planned & Certified Design (Phase 0 Audit Complete)  

---

## 1. Architectural Context & Motivation

PilgrimAI operates as a RAG-based multi-agent assistant for pilgrimage temples in Telangana. Pilgrims frequently require urgent assistance regarding medical facilities, local police stations, temple first-aid clinics, ambulance helplines, and devasthanam administrative help desks.

The goal of this phase is to implement `EmergencyAgent` as an isolated, grounded specialist agent integrated cleanly into the existing multi-agent coordinator and router pipeline.

### Core Architectural Principles:
1. **Additive & Non-Disruptive**: Must not modify frozen RAG retrieval, vector database collections, BM25 indexes, or the 417 source JSON files.
2. **Zero Fabrication**: All hospital names, police stations, phone numbers, and emergency facilities must derive strictly from verified local records (`emergency_nos.json`, `contacts.json`, `facilities.json`). If unrecorded, the agent must explicitly state that verified local contacts are unavailable; it must never invent plausible-looking emergency details.
3. **Temple-Scoped**: Emergency contacts must remain strictly scoped to the user-specified or contextually-resolved temple, with zero cross-temple contamination.
4. **Universal Helplines**: If no specific temple is identified or if general emergency assistance is needed, verified statutory helplines (112 National Emergency, 108 State Ambulance, 100 Police, 101 Fire) recorded across the knowledge base are supplied.
5. **Seamless Pipeline Integration**: Operates via existing `POST /chat`, `MasterAgentCoordinator`, `AgentRouter`, and `SequentialMultiIntentPipeline`.

---

## 2. Frozen Components (Strictly Read-Only)

The following components are production-frozen and will **NOT** be modified:
- `qdrant_db/` (Local vector database)
- `bm25_index/` (Local sparse index)
- `evaluation/` (Regression benchmark suites)
- `backend/app/rag/` (Core RAG retrieval, chunker, query planner, reranker, LLM service, validators)
- 417 source temple JSON files (SHA-256 baseline recorded)
- Existing specialist agents (`temple_information_agent.py`, `comparison_agent.py`, `cross_temple_aggregation_agent.py`, `itinerary_planning_agent.py`, `live_weather_agent.py`, `budget_agent.py`, `live_navigation_agent.py`, `voice_multilingual_agent.py`)
- Google Maps, Routes, and Places API keys in `.env`

---

## 3. Files to Be Created and Modified

### A. New Files to Create:
1. `backend/app/agents/emergency_agent.py`: Concrete `EmergencyAgent` implementation subclassing `BaseAgent`.
2. `tests/test_emergency_agent.py`: Dedicated unit and integration test suite covering all emergency query types, scoping, lack of fabrication, and coordinator/router integration.
3. `docs/EMERGENCY_AGENT_IMPLEMENTATION_CERTIFICATION.md`: Final post-implementation certification and regression audit report.

### B. Minimal Existing Files to Modify:
1. `backend/app/agents/router.py`:
   - Add `self._emergency_patterns` to `_init_taxonomies_and_patterns()`.
   - Add `"emergency"` sub-intent pattern to `self._sub_intent_patterns`.
   - Add Priority 2.8 routing rule for emergency intent.
2. `backend/app/agents/coordinator.py`:
   - Add `emergency_agent: Optional[Any] = None` parameter to `MasterAgentCoordinator.__init__()`.
   - Register `emergency_agent` into `self.agents` dictionary.
3. `backend/app/api/chat.py`:
   - Instantiate `EmergencyAgent` and pass to `MasterAgentCoordinator` in `get_coordinator()`.
4. `backend/app/static/app.js` & `backend/app/static/style.css` (Optional UI Polish):
   - Add badge mapping for `emergency` (`🚨 Emergency Services`) in `getAgentBadgeConfig()`.
   - Add `.agent-badge.badge-emergency` styling.

---

## 4. EmergencyAgent Design Specification

### 4.1 Interface Contract
- **Name**: `emergency`
- **Class**: `EmergencyAgent(BaseAgent)`
- **Dependencies**: `RAGTool` (read-only facade via lazy property)
- **Lifecycle Method**: `_run(self, state: AgentState) -> AgentResponse`

### 4.2 Data Resolution & Knowledge Retrieval
When `EmergencyAgent._run(state)` executes:
1. **Temple Identity Resolution**:
   - Inspects `state.intermediate_results["route_decision"].metadata` for `detected_temples`.
   - Falls back to `state.intermediate_results.get("memory", {}).get("referenced_temple")`.
   - Falls back to `self._detect_temple(query)`.
2. **Knowledge Extraction via RAGTool**:
   - Primary: `self.rag_tool.get_temple_category_data(canonical_temple, "emergency_contacts")`
   - Secondary: `self.rag_tool.get_temple_category_data(canonical_temple, "contacts")`
   - Tertiary: `self.rag_tool.get_temple_category_data(canonical_temple, "facilities")`
3. **Structured Response Synthesis (Zero Hallucination)**:
   - **Police Section**: Police stations, phone numbers, addresses from verified records.
   - **Medical & Hospital Section**: PHCs, Government General Hospitals, temple first-aid clinics, duty doctor availability.
   - **Temple Help Desk & Office**: Administrative landlines, accommodation desks, tollgates.
   - **Fire & Statutory Helplines**: 112, 108, 100, 101.
4. **Missing Information Guard**:
   - If a specific contact (e.g. hospital or police) is not present in the temple record, state:
     `"• Medical assistance: No verified hospital contact recorded for {temple} in the local knowledge base."`
   - If the temple has no emergency records, output a transparent unavailable notice without generating numbers.
5. **Universal Fallback**:
   - If no temple is mentioned (e.g. *"Who should I call in an emergency?"*), provide statutory national/state helplines (112, 108, 100, 101) and request the specific temple name for local medical/police assistance.

---

## 5. Router Integration & Priority Architecture

### Routing Rule: Priority 2.8
- **Placement**: Evaluated after Voice/Multilingual (Priority 2.5) and before standard travel comparison/budget/itinerary.
- **Intent**: `emergency`
- **Selected Agent**: `emergency`
- **Multi-Intent Compatibility**: If query conjoins emergency with another topic (e.g., *"What are Yadadri timings and what emergency contacts are available?"*), `_detect_multi_intent()` captures both sub-intents (`timings` and `emergency`), routing the query to `multi_intent` for sequential execution.

---

## 6. Test Plan

A dedicated test suite `tests/test_emergency_agent.py` will validate:
1. `test_emergency_agent_initialization`: Verifies agent lifecycle, name, and lazy `RAGTool` property.
2. `test_emergency_intent_routing_single_temple`: Validates queries like *"What should I do in an emergency at Yadadri?"* route to `emergency`.
3. `test_emergency_intent_routing_variations`: Tests keywords: `hospital`, `first aid`, `ambulance`, `police`, `help desk`.
4. `test_emergency_agent_temple_scoping`: Verifies Yadadri query returns Yadadri PHC/police, not Basara or Srisailam.
5. `test_emergency_agent_grounded_contacts`: Asserts returned phone numbers match exact verified JSON values.
6. `test_emergency_agent_no_fabrication`: Verifies non-existent contacts are flagged unavailable, never fabricated.
7. `test_emergency_agent_general_helpline`: Verifies general queries without a temple return universal statutory helplines.
8. `test_emergency_agent_coordinator_registration`: Confirms coordinator registers and routes to `EmergencyAgent`.
9. `test_emergency_agent_chat_endpoint_integration`: Tests live ASGI HTTP `POST /chat` invocation.
10. `test_emergency_agent_multi_intent_integration`: Tests conjoined timing + emergency queries.
11. `test_emergency_agent_conversation_memory`: Tests follow-up query: *"Tell me about Yadadri"* -> *"Give me emergency contacts"*.

---

## 7. Full Regression Plan

Following unit tests, execute the complete 24-suite regression suite (592+ tests) to guarantee:
- 100% green pass on all existing agents (TempleInfo, Comparison, Aggregation, Itinerary, Weather, Budget, Navigation, Voice).
- Zero regression in multi-intent pipeline.
- 417/417 source JSON files remain 100% SHA-256 identical.

---

## 8. Rollback Plan

If any critical issue arises:
1. Revert `backend/app/agents/coordinator.py`, `backend/app/agents/router.py`, and `backend/app/api/chat.py`.
2. Remove `backend/app/agents/emergency_agent.py` and `tests/test_emergency_agent.py`.
3. Confirm system returns to certified baseline state.
