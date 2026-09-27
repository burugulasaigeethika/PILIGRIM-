# PilgrimAI: Phase D — AgentRouter

**Date:** September 17, 2026  
**Project:** PilgrimAI: A RAG-Based Multi-Agent Assistant for Smart Pilgrimage  
**Workspace:** `d:\pligrim ai new`  
**Phase:** Phase D: AgentRouter Implementation  
**Status:** Certified & Passed (13/13 tests in 7.26s)  

---

## 1. Purpose

`AgentRouter` provides the **deterministic query classification and routing engine** for PilgrimAI.

Its sole responsibility is to analyze natural language user queries and emit an immutable, strongly-typed `AgentRouteDecision` (from Phase A), specifying:
- The target specialist agent (e.g., `"temple_information"`, or `"none"` when unhandled / clarification needed).
- The detected intent (e.g., `"temple_information"`, `"comparison"`, `"itinerary_planning"`, `"cross_temple_aggregation"`, `"multi_intent"`, `"clarification"`, `"unsupported"`).
- Deterministic routing confidence (e.g., `0.95`, `0.90`, `0.85`).
- A transparent, human-readable routing reason for debugging and execution tracing.
- Structured metadata (detected temples, sub-intents, clarification flags).

---

## 2. Architecture & Request Flow

```text
User Natural Language Query
             │
             ▼
        AgentRouter
  (100% Deterministic Rules)
             │
             └── Emits AgentRouteDecision
                       │
                       ▼
            [ Future Coordinator ]
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
TempleInformationAgent          Future Agents
 (Active in Phase C)         (Comparison, Itinerary,
        │                     Aggregation - Future)
        ▼
     RAGTool
        │
        ▼
   Frozen RAG
```

---

## 3. Strict Deterministic Routing Principles

1. **Zero LLM Usage:** The router **never** calls Ollama, external APIs, or neural classifiers for routing. It runs purely on deterministic regex word boundaries and canonical entity matching.
2. **Sub-Millisecond Execution:** Routing decisions execute in **< 1 millisecond** per query, introducing virtually zero latency overhead into the pipeline.
3. **No Execution in Router:** The router **only decides**; it does not execute specialist agents, generate answers, or touch RAG data.
4. **Active vs Future Agent Separation:** Only currently implemented specialist agents (`temple_information`) are selected (`selected_agent = "temple_information"`). Future intents (`comparison`, `itinerary_planning`, `cross_temple_aggregation`, `multi_intent`) are explicitly identified, but marked with `selected_agent = "none"` and `available: False`.

---

## 4. Intent Taxonomy & Priority Rules

The router evaluates incoming queries through a strict priority hierarchy:

| Priority | Evaluation Stage | Triggers / Conditions | Emitted Intent | Selected Agent | Confidence |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | **Empty Query** | Empty or whitespace input | `unsupported` | `"none"` | `1.0` |
| **2** | **Explicit Unsupported Temple** | Names non-registered temples (e.g., *Golden Temple, Somnath, Kedarnath, Meenakshi*) | `unsupported` | `"none"` | `0.95` |
| **3** | **Comparison Intent** | Keywords: *compare, vs, versus, difference between*, or 2+ detected temples | `comparison` | `"none"` *(Future Agent)* | `0.95` |
| **4** | **Itinerary Intent** | Keywords: *plan a trip, tour plan, itinerary for, weekend visit* | `itinerary_planning` | `"none"` *(Future Agent)* | `0.90` |
| **5** | **Cross-Temple Aggregation** | Keywords: *which temples, list all temples, all temples with, how many temples* | `cross_temple_aggregation` | `"none"` *(Future Agent)* | `0.90` |
| **6** | **Multi-Intent Query** | Conjoined multi-topic queries (e.g., *timings AND how to reach*) | `multi_intent` | `"none"` *(Future Pipeline)* | `0.85` |
| **7** | **Single Known Temple Factual** | Exactly 1 canonical temple detected + factual inquiry | `temple_information` | `"temple_information"` | `0.95` |
| **8** | **Ambiguous Temple Query** | Temple keywords present (*timings, sevas, rules*) but no temple name | `clarification` | `"none"` | `0.85` |
| **9** | **Out-of-Scope / General** | Query unrelated to pilgrimage temples (e.g., *weather, sports*) | `unsupported` | `"none"` | `0.95` |

---

## 5. Dependency Boundary Audit

Inspection of `backend/app/agents/router.py` verifies **ZERO** direct imports of:
- `qdrant_client`
- `rank_bm25`
- `sentence_transformers`
- `LocalQdrantManager`
- `LocalBM25Manager`
- `PilgrimRAGService`
- Raw database files or Ollama clients.

The router depends solely on `AgentRouteDecision` (from Phase A) and `QueryPlanner` (lightweight regex helper).

---

## 6. Verification and Test Results

### 6.1 Phase D Test Suite (`tests/test_agent_router.py`)
- Total tests: **13**
- Passing: **13 (100%)**
- Duration: **7.26 seconds**

| Test Name | Verification Focus | Result |
| :--- | :--- | :--- |
| `test_1_router_initialization` | Verifies router initializes and exposes `route()` method | **PASS** |
| `test_2_yadadri_factual_routing` | Confirms Yadadri timings query routes to `temple_information` | **PASS** |
| `test_3_dharmapuri_factual_routing` | Confirms Dharmapuri sevas query routes to `temple_information` | **PASS** |
| `test_4_case_normalization` | Verifies identical decisions across uppercase and lowercase queries | **PASS** |
| `test_5_explicit_unsupported_temple` | Flags unsupported temples (*Golden Temple*) without routing to temple agent | **PASS** |
| `test_6_ambiguous_temple_query` | Asks for clarification when query lacks temple name | **PASS** |
| `test_7_non_temple_query` | Rejects out-of-scope non-temple queries (*weather tomorrow*) | **PASS** |
| `test_8_empty_query` | Handles empty / whitespace queries cleanly | **PASS** |
| `test_9_future_comparison_intent` | Identifies comparison intent without attempting to run nonexistent agent | **PASS** |
| `test_10_future_itinerary_intent` | Identifies itinerary intent without attempting to run nonexistent agent | **PASS** |
| `test_11_multi_intent_detection` | Detects multi-intent queries (*timings + travel*) cleanly | **PASS** |
| `test_12_determinism` | 10 repeated executions return 100% identical decision payloads | **PASS** |
| `test_13_no_forbidden_dependencies` | Source code audit certifying zero database driver or LLM imports | **PASS** |

### 6.2 Full Regression Test Suite
- **Phase D (`tests/test_agent_router.py`):** **13/13 passed**
- **Phase C (`tests/test_temple_information_agent.py`):** **10/10 passed**
- **Phase B (`tests/test_rag_tool.py`):** **10/10 passed**
- **Phase A (`tests/test_agent_contracts.py`):** **10/10 passed**
- **RAG Baseline (`tests/test_query_planner.py`):** **40/40 passed**
- **Total Certified Suite:** **83 passed, 0 failed**

---

## 7. Protected Files Audit

```text
Files Created:
- backend/app/agents/router.py
- tests/test_agent_router.py
- docs/PHASE_D_AGENT_ROUTER.md

Protected Files Modified:
- NONE (0 files changed in backend/app/rag/, qdrant_db/, bm25_index/, 417 temple JSONs, .env, requirements.txt, backend/app/api/chat.py, backend/app/main.py, or frontend)
```
