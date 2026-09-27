# PilgrimAI — Phase I: ConversationMemoryManager Certification Report

## 1. Phase Objective

Phase I introduces in-memory, session-isolated conversational memory via `ConversationMemoryManager`:
- Session-based multi-turn conversation tracking.
- Bounded memory with LRU eviction (`MAX_SESSIONS = 1000`).
- Time-to-Live (TTL) expiration per session (`DEFAULT_TTL_SECONDS = 1800.0` / 30 minutes).
- Deterministic, rule-based pronoun/anaphora resolution (`its`, `it`, `this temple`, `that temple`, `the temple`, `there`).
- Complete isolation across concurrent/different user sessions.
- Sensitive credential and secret redaction.
- Complete independence from RAG retrieval and LLM generation.

---

## 2. Initial Architecture Audit

Before writing code, an audit of existing certified components was performed:
- `backend/app/agents/state.py`
- `backend/app/agents/base_agent.py`
- `backend/app/agents/router.py`
- `backend/app/agents/coordinator.py`
- `backend/app/agents/multi_intent_pipeline.py`
- `backend/app/agents/response_aggregator.py`
- `backend/app/agents/temple_information_agent.py`

### Findings:
1. **Lightweight Context Only**: Memory must NOT store massive RAG chunks or complete retrieved documents. Only conversational entities (`identified_temples`, `detected_intents`, brief response summaries) are retained.
2. **Deterministic Anaphora**: Pronoun resolution must be purely algorithmic (regular expressions and entity history)—no LLMs or external APIs are used.
3. **Protected RAG Foundation**: Memory resolves queries *before* routing/agent execution; the resulting resolved query enters the certified coordinator flow seamlessly.

---

## 3. Target Architecture

```text
                       New User Request
                              │
                              ▼
                  ConversationMemoryManager
                  (resolve_query with session)
                              │
            ┌─────────────────┴─────────────────┐
            ▼                                   ▼
    Ambiguous Pronoun?                 Resolved Query
    (Multiple recent temples)          (e.g., "its" -> "Dharmapuri temple's")
            │                                   │
            ▼                                   ▼
   Clarification Response                   AgentState
   ("Which temple are you referring to?")       │
                                                ▼
                                      MasterAgentCoordinator
                                                │
                                                ▼
                                           AgentRouter
                                                │
                                                ▼
                                    Specialist / Multi-Intent
                                                │
                                                ▼
                                    ResponseAggregator
                                                │
                                                ▼
                                     Record Turn into Memory
                                                │
                                                ▼
                                       Final AgentResponse
```

---

## 4. Session & Storage Model

### 4.1 In-Memory Storage
- Uses Python `OrderedDict` to track active sessions keyed by `session_id`.
- Pure in-process memory: zero Redis, PostgreSQL, or external databases.

### 4.2 LRU Bounds
- Capacity is bounded at **1,000 sessions**.
- When session 1,001 is created, the least recently used session (`popitem(last=False)`) is evicted.
- Accessing an existing session refreshes its LRU position to the most recently used (MRU) slot.

### 4.3 TTL Expiration
- Default session lifespan is **1,800 seconds (30 minutes)**.
- On any session access or turn addition, if `(current_time - last_accessed) > 1800`, the session is purged immediately.
- Uses an injectable clock provider for deterministic testing without sleeping.

---

## 5. Memory Turn Model

Each interaction is stored as a `MemoryTurn`:
```python
class MemoryTurn(BaseModel):
    session_id: str
    user_query: str
    resolved_query: str
    detected_intents: List[str]
    identified_temples: List[str]
    timestamp: float
    response_summary: str
    metadata: Dict[str, Any]
```
Large document chunks and full context windows are strictly excluded.

---

## 6. Deterministic Anaphora & Pronoun Resolution

### 6.1 Supported Reference Triggers
- Possessive: `its`, `it's` -> `{temple} temple's`
- Demonstrative: `this temple`, `that temple`, `the temple` -> `{temple} temple`
- Neutral pronoun: `it` -> `{temple} temple`
- Locative: `there` -> `at {temple} temple`
- Ellipsis: `What about sevas?` -> `What about sevas at {temple} temple?`

### 6.2 Explicit Entities Take Precedence
If the incoming query explicitly names another registered or unregistered temple (e.g., Turn 1: Dharmapuri, Turn 2: *"What are the sevas at Yadadri?"*), memory does **not** overwrite the new entity. Yadadri takes immediate precedence.

### 6.3 Ambiguity Guard
If multiple distinct temples were discussed across recent turns (e.g., Turn 1: Yadadri, Turn 2: Bhadrachalam) and the user asks *"What are its sevas?"*:
The system does not guess. It returns a controlled clarification requirement:
`"Which temple are you referring to? You recently discussed Yadadri and Bhadrachalam."`

---

## 7. Security & Sanitization

- Before recording turns, metadata is recursively sanitized.
- Keys matching `api_key`, `token`, `password`, `secret`, `authorization`, `private_key` are masked as `[REDACTED]`.
- Text attributes exceeding 1,000 characters are truncated.

---

## 8. AgentState & Coordinator Integration

- `MasterAgentCoordinator` accepts an optional `memory_manager: ConversationMemoryManager`.
- If a query's pronouns are resolved, the state records:
  ```python
  state.intermediate_results["memory"] = {
      "original_query": "What are its sevas?",
      "resolved_query": "What are Dharmapuri temple's sevas?",
      "referenced_temple": "Dharmapuri"
  }
  ```
- The original user query is preserved separately in `state.intermediate_results["memory"]["original_query"]`.
- The resolved query is routed and executed, ensuring grounded RAG retrieval.
- After processing, the completed turn is automatically recorded via `_record_memory()`.

---

## 9. Dependency Boundary Audit

Static code inspection in `test_18` confirms `backend/app/agents/memory.py` contains **ZERO** imports of:
- `qdrant_client`, `rank_bm25`, `sentence_transformers`
- `LocalQdrantManager`, `LocalBM25Manager`, `PilgrimRAGService`, `KnowledgeRegistry`, `RAGTool`
- `ollama`, `openai`, `anthropic`
- External database packages (`psycopg2`, `redis`, `motor`)

---

## 10. Test Results

### 10.1 Phase I Suite (`tests/test_conversation_memory.py`)
- Total tests: **24**
- Passing: **24 (100%)**

| Test | Focus | Result |
| :--- | :--- | :--- |
| `test_1_memory_manager_initialization` | Manager initialization & default parameters | **PASS** |
| `test_2_session_creation` | Session creation on initial access | **PASS** |
| `test_3_session_isolation` | Multi-session turn separation | **PASS** |
| `test_4_add_turn` | Turn persistence & structured attributes | **PASS** |
| `test_5_retrieve_recent_turns` | Chronological turn retrieval | **PASS** |
| `test_6_recent_turn_limit` | Bounded turn retrieval limit | **PASS** |
| `test_7_session_clearing` | Session clearing & safe no-op handling | **PASS** |
| `test_8_ttl_within_expiration` | Session survival within 30 min window | **PASS** |
| `test_9_ttl_expiration` | Session eviction after 30 min TTL | **PASS** |
| `test_10_lru_eviction_at_capacity` | LRU eviction when 1,000 session bound is exceeded | **PASS** |
| `test_11_lru_refresh_on_access` | MRU refresh on access preventing premature eviction | **PASS** |
| `test_12_dharmapuri_its_resolution` | Dharmapuri -> 'its' resolution | **PASS** |
| `test_13_yadadri_its_resolution` | Yadadri -> 'its' resolution | **PASS** |
| `test_14_explicit_new_temple_overrides_memory` | Explicit temple overrides conversational context | **PASS** |
| `test_15_ambiguous_multiple_temple_pronoun` | Clarification when recent history has multiple temples | **PASS** |
| `test_16_no_cross_session_context_leakage` | Cross-session context isolation | **PASS** |
| `test_17_secret_sanitization` | Sensitive token and key redaction | **PASS** |
| `test_18_no_raw_rag_llm_dependency` | Zero DB / LLM / RAG imports | **PASS** |
| `test_19_resolved_query_preserves_original_query` | Preservation of original query in intermediate results | **PASS** |
| `test_20_memory_immutability` | Defensive copies prevent caller history mutation | **PASS** |
| `test_21_repeated_resolution_determinism` | Deterministic resolution across identical calls | **PASS** |
| `test_22_agent_state_compatibility` | AgentState compatibility with memory manager | **PASS** |
| `test_23_coordinator_multi_turn_live_flow` | Live multi-turn Dharmapuri factual execution | **PASS** |
| `test_24_phase_h_multi_intent_compatibility` | Multi-intent pipeline compatibility | **PASS** |

### 10.2 Full Regression Suite
- `tests/test_conversation_memory.py`: **24 passed**
- `tests/test_multi_intent_pipeline.py`: **18 passed**
- `tests/test_agent_state.py`: **17 passed**
- `tests/test_master_agent_coordinator.py`: **13 passed**
- `tests/test_response_aggregator.py`: **13 passed**
- `tests/test_agent_router.py`: **13 passed**
- `tests/test_temple_information_agent.py`: **10 passed**
- `tests/test_rag_tool.py`: **10 passed**
- `tests/test_agent_contracts.py`: **10 passed**
- `tests/test_query_planner.py`: **40 passed**
- **Total Suite**: **168 passed, 0 failed**

---

## 11. Protected Assets Integrity

Strictly **0 modifications** were made to:
- `backend/app/rag/`
- `qdrant_db/`
- `bm25_index/`
- 417 temple JSON source files
- `evaluation/`
- `.env`
- `requirements.txt`
- `backend/app/api/chat.py`
- `backend/app/main.py`
- `frontend/`

---

## 12. Git Status

The workspace `D:\pligrim ai new` is not initialized as a git repository. Files created and modified for Phase I are strictly:
- **Created**: `backend/app/agents/memory.py`
- **Created**: `tests/test_conversation_memory.py`
- **Created**: `docs/PHASE_I_CONVERSATION_MEMORY.md`
- **Modified**: `backend/app/agents/coordinator.py` (added `memory_manager` support)

---

## 13. Limitations

Phase I intentionally does **NOT** implement:
- Persistent disk/database session storage (Redis, PostgreSQL)
- User authentication / JWT tracking
- FastAPI `/chat` integration
- Additional specialist agents (`ComparisonAgent`, `CrossTempleAggregationAgent`, `ItineraryPlanningAgent`)
- External APIs (live maps, weather, booking)

---

## 14. Next Recommended Phase

**Phase J — Complete-List Retrieval**

*Execution stops here per Phase I requirements.*
