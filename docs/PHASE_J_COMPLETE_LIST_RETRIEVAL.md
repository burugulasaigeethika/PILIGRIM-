# PilgrimAI — Phase J: Complete-List Retrieval Documentation

## 1. Phase J Objective

The primary objective of Phase J is to resolve the semantic top-k retrieval limitation where user queries requesting exhaustive or complete category lists (e.g., *"List all sevas at Dharmapuri temple"*, *"Show all prasadam items at Edupayala"*, *"Give me the complete list of facilities at Yadadri"*) were subject to arbitrary truncation by ordinary semantic top-k retrieval (such as `TOP_K=3`).

Phase J enables the PilgrimAI architecture to deterministically detect complete-list intent, resolve the canonical target temple and category, and retrieve 100% of the verified source records from the authoritative knowledge base without modifying any frozen source datasets or disturbing targeted factual retrieval.

---

## 2. Initial Architecture Audit

Before modifying code, an audit of the current architecture was conducted:
- **`backend/app/rag/query_planner.py`**: A 100% deterministic query planner already produced a structured `QueryPlan` containing `intent`, `retrieval_mode`, `exhaustive`, `temples`, and `categories`. However, its completeness triggers only covered basic keywords and missed common explicit phrases such as `"every"`, `"full list"`, `"entire list"`, `"give me all"`, and `"show every"`.
- **`backend/app/rag/knowledge_registry.py`**: Contained `get_complete_parent(temple, category)` which looked up `parent_{temple}_{cat}_complete` in `_parent_store`. For single-parent files whose keys included hashes (such as `parent_yadadri_facilities_70f7e113`) or split categories, the lookup returned `None`.
- **`backend/app/rag/chat.py`**: Already contained Route 2 (`plan.retrieval_mode == "complete_category"`), which retrieved the full parent text and passed it to `build_complete_category_context` without top-k truncation.
- **`backend/app/agents/tools/rag_tool.py`**: Exposed read-only facades `get_complete_parent_text(temple, category)` and `get_temple_category_data(temple, category)`.
- **`backend/app/agents/temple_information_agent.py`**: Routed factual queries to `RAGTool.execute_grounded_rag()` and enforced strict anti-hallucination temple isolation.

---

## 3. Existing Retrieval Limitation

In standard RAG architectures, all queries pass through dense vector search + BM25 sparse search + Cross-Encoder reranking, returning a fixed `TOP_K` (e.g. 3) number of chunks.
For targeted questions (e.g., *"What is the price of Abhishekam at Dharmapuri?"*), `TOP_K=3` is optimal because it focuses LLM attention on the single relevant passage.
However, when a pilgrim asks *"List all sevas at Dharmapuri temple"*, returning only 3 chunks truncates the remaining 7 verified sevas (Dharmapuri has 10 verified sevas). The user receives an incomplete answer with missing records.

---

## 4. Design Chosen

Rather than globally increasing `TOP_K` (which would degrade performance and introduce unrelated noise into ordinary questions), a dual-mode retrieval architecture was established:

1. **Mode 1 — Targeted Retrieval (Default)**:
   - Queries like *"What is the Abhishekam price at Dharmapuri?"* continue using the frozen hybrid Qdrant + BM25 -> RRF -> Cross-Encoder Top-3 path.
   - Retrieval constants remain unchanged (`TOP_K=3`, `FINAL_RERANK_TOP_K=3`).

2. **Mode 2 — Complete-List Retrieval (Selective)**:
   - Activated only when deterministic completeness intent is detected for a registered category.
   - Bypasses vector candidate truncation and retrieves the complete authoritative parent category representation.
   - Formats and presents all verified source items without loss.

---

## 5. Complete-List Detection

Completeness detection is 100% deterministic, implemented in `QueryPlanner.complete_list_triggers` using regex boundary patterns:
- Explicit completeness markers: `all`, `every`, `every single`, `complete list`, `full list`, `entire list`, `list all`, `show all`, `what are all`, `give me all`, `everything available`, `complete details`, `all available`, `all types`, `all options`, `show every`, `names of all`.
- Category inquiry patterns: `what sevas are available`, `which festivals are celebrated`, `facilities list`, etc.
- List-oriented categories (`sevas`, `prasadam`, `facilities`, `festivals`, `accommodation`, `restaurants`, `nearby_attractions`, `sub_temples`, `donations`, `faq`).

Ordinary targeted questions (e.g., *"What is the Abhishekam price?"*, *"What time does the temple open?"*, *"How much is one laddu?"*) do not match completeness patterns and remain strictly `intent="targeted_fact"`, `retrieval_mode="targeted"`.

---

## 6. Temple and Category Resolution

Temple and category resolution reuse existing canonical registries:
- **Temple Identification**: `QueryPlanner.detect_temple()` resolves aliases for all 20 canonical temples (e.g., "Yadagirigutta" -> "Yadadri", "Vana Durga Bhavani" -> "Edupayal").
- **Category Resolution**: `CategoryRegistry.match_categories()` deterministically maps query terms to canonical category keys (`sevas`, `prasadam`, `facilities`, `timings`, etc.).
- **Missing Temple Handling**: A complete-list query without a temple (e.g., *"List all sevas"*) does not guess; `TempleInformationAgent` returns a controlled clarification request asking the user to specify one of the 20 temples.

---

## 7. Complete Retrieval Mechanism

When `plan.retrieval_mode == "complete_category"`:
1. `PilgrimRAGService` invokes `knowledge_registry.get_complete_parent(temple, category)`.
2. `KnowledgeRegistry` resolves the complete parent using a multi-stage strategy:
   - **Primary lookup**: `parent_{temple}_{category}_complete` in `_parent_store`.
   - **Canonical alias check**: `wheelchair` -> `elderly_ppl`, `emergency_contacts` -> `emergency_nos`.
   - **Prefix matching**: Matches single-parent hashed keys (e.g., `parent_yadadri_facilities_70f7e113`) or multi-parent chunk lists (e.g., `parent_yadadri_accommodation_0_...` to `_7_...`).
   - **Safe fallback**: If indexed parent text is absent, `_format_raw_category_data()` reads verified source data via `get_temple_raw_data()` and formats it into structured document text. Raw JSON is never exposed directly to agents.
3. The complete parent document is passed to `ContextBuilder.build_complete_category_context()`, which injects metadata headers `[TEMPLE]`, `[CATEGORY]`, `[SOURCE]`, `[COMPLETENESS]`, and `[CONTENT]`.

---

## 8. Targeted Retrieval Preservation

Ordinary targeted factual queries are completely protected:
- Queries with specific targets (`"What is the Abhishekam price at Dharmapuri?"`) produce `intent="targeted_fact"`, `retrieval_mode="targeted"`, `exhaustive=False`.
- Execution continues through Route 5 in `chat.py`:
  - Qdrant dense candidate pool (`top_k=20`)
  - BM25 candidate pool (`top_k=20`)
  - Reciprocal Rank Fusion
  - Cross-Encoder reranking (`top_k=3`)
- Zero retrieval constants were modified.

---

## 9. Completeness Validation

The existing `CompletenessValidator` (`backend/app/rag/completeness_validator.py`) inspects availability states and guarantees that missing records are never confused with confirmed absence. In complete-list mode, the system exposes the verified item count in the context header, preventing the LLM from truncating records or inventing non-existent items.

---

## 10. Grounding Behavior

- Every item in a complete-list response is directly derived from verified source JSON records.
- In `test_complete_list_retrieval.py`, test assertions verify that 100% of the 10 sevas in `dharmapuri/sevas.json` and 100% of the 2 prasadams in `edupayal/prasadam.json` exist verbatim in the retrieved parent context.
- If a category contains zero records, the system returns a controlled no-data response rather than hallucinating.

---

## 11. Cross-Temple Isolation

Complete-list retrieval enforces strict single-temple scope:
- Context is constructed solely from the target temple's parent records.
- `TempleInformationAgent._run()` enforces source filtering: any source that does not match the canonical target temple or its aliases is suppressed.
- Assertions in `test_10_cross_temple_isolation` confirm that a Dharmapuri complete-list query yields zero text or source mentions of Yadadri, Bhadrachalam, Edupayala, or Srisailam.

---

## 12. Phase H Multi-Intent Compatibility

Phase H introduces the `SequentialMultiIntentPipeline`, which splits compound queries into sub-tasks.
Phase J seamlessly composes with Phase H:
- Query: *"What are the timings of Yadadri and list all sevas at Dharmapuri"*
- `SequentialMultiIntentPipeline.decompose_query()` splits into Task 1 (`Yadadri timings`) and Task 2 (`Dharmapuri sevas`).
- Task 2 is planned deterministically as `intent="complete_list"`, `retrieval_mode="complete_category"`.
- Verified in `test_12_phase_h_multi_intent_compatibility`.

---

## 13. Phase I Conversation-Memory Compatibility

Phase I introduces `ConversationMemoryManager` for multi-turn pronoun and anaphora resolution.
Phase J integrates with Phase I without duplication:
- Turn 1: *"Tell me about Dharmapuri temple."* -> `identified_temples=["Dharmapuri"]`
- Turn 2: *"List all its sevas."* -> `resolve_query()` resolves `"its"` to `"Dharmapuri"`.
- The resolved query is routed to `QueryPlanner`, which detects `complete_list` for Dharmapuri sevas.
- Verified in `test_13_phase_i_conversation_memory_compatibility`.

---

## 14. Certification Tests

All 22 certification tests in `tests/test_complete_list_retrieval.py` passed:
1. `test_1_completeness_intent_detection`: Validates `complete_list` classification for "List all sevas at Dharmapuri".
2. `test_2_targeted_query_remains_targeted`: Validates `targeted_fact` classification for "What is the Abhishekam price at Dharmapuri?".
3. `test_3_dharmapuri_complete_sevas`: Validates all 10 verified Dharmapuri sevas present in complete parent text.
4. `test_4_no_top_k_truncation`: Validates that 10 records are retrieved (exceeding standard `top_k=3`).
5. `test_5_targeted_retrieval_unaffected`: Validates that targeted timings, travel, and sevas queries maintain `retrieval_mode="targeted"`.
6. `test_6_complete_prasadam_category`: Validates Edupayala prasadam retrieval (both Laddu and Tamarind Pulihora present).
7. `test_7_explicit_completeness_variants`: Validates 15 phrasing variations (`all`, `every`, `complete list`, `full list`, `entire list`, `give me all`, etc.).
8. `test_8_no_temple_clarification`: Validates that "List all sevas" requests clarification without guessing.
9. `test_9_unknown_category`: Validates that queries for non-existent categories do not hallucinate.
10. `test_10_cross_temple_isolation`: Validates zero bleed of Yadadri/Bhadrachalam data into Dharmapuri responses.
11. `test_11_source_grounding`: Validates that every seva name corresponds verbatim to source JSON data.
12. `test_12_phase_h_multi_intent_compatibility`: Validates query decomposition and task routing with `SequentialMultiIntentPipeline`.
13. `test_13_phase_i_conversation_memory_compatibility`: Validates multi-turn resolution from Turn 1 to Turn 2 complete list.
14. `test_14_no_raw_rag_duplication`: Validates reuse of `RAGTool` and `KnowledgeRegistry` singletons.
15. `test_15_frozen_dataset_integrity`: Validates all 417 source JSON files exist and are intact.
16. `test_16_deterministic_behavior`: Validates identical query plans across repeated runs.
17. `test_17_large_category_retrieval_yadadri_facilities`: Validates that all 26 facility entries in `yadadri/facilities.json` are retrieved in full.
18. `test_18_targeted_questions_for_list_categories_remain_targeted`: Validates that specific price or timing questions on list categories remain targeted.
19. `test_19_case_insensitivity`: Validates uppercase and mixed-case query handling.
20. `test_20_empty_and_whitespace_queries`: Validates safe error handling on empty input.
21. `test_21_safe_formatted_fallback`: Validates internal fallback formatting without raw JSON exposure.
22. `test_22_temple_information_agent_metadata_propagation`: Validates `is_complete_list` flag in `AgentResponse.metadata`.

---

## 15. Regression Results

### Baseline Regression (Phases A through I):
```text
Phase I (ConversationMemoryManager):        24 passed
Phase H (SequentialMultiIntentPipeline):     18 passed
Phase G (AgentState + ExecutionTrace):      17 passed
Phase F (MasterAgentCoordinator):           13 passed
Phase E (ResponseAggregator):               13 passed
Phase D (AgentRouter):                      13 passed
Phase C (TempleInformationAgent):           10 passed
Phase B (RAGTool Read-Only Facade):         10 passed
Phase A (Agent Contracts & BaseAgent):      10 passed
RAG QueryPlanner Baseline:                  40 passed
-----------------------------------------------------
Baseline Total:                             168 passed, 0 failed
```

### Phase J Certification:
```text
Phase J (Complete-List Retrieval):          22 passed, 0 failed
-----------------------------------------------------
Combined Certified Total:                   190 passed, 0 failed
```

---

## 16. Source-Data Integrity Verification

All source assets were verified byte-for-byte read-only:
- `417 JSON files` across 20 temple directories verified intact.
- `qdrant_db/`: untouched.
- `bm25_index/`: untouched.
- `evaluation/`: untouched.
- `.env`: untouched.
- `backend/app/api/chat.py`: untouched.
- `backend/app/main.py`: untouched.
- `frontend/`: untouched.

---

## 17. Files Created

1. `tests/test_complete_list_retrieval.py` — Certification test suite containing 22 tests.
2. `docs/PHASE_J_COMPLETE_LIST_RETRIEVAL.md` — Comprehensive architecture and certification report.

---

## 18. Files Modified

1. `backend/app/rag/query_planner.py` — Expanded `complete_list_triggers` to deterministically match all required completeness phrasing.
2. `backend/app/rag/knowledge_registry.py` — Enhanced `get_complete_parent()` to support prefix matching for hashed single-parent chunks and a safe internal formatting fallback from raw JSON.
3. `backend/app/agents/temple_information_agent.py` — Propagated `is_complete_list` flag and retrieval plan in `AgentResponse.metadata`.

---

## 19. Dependency Boundary

Zero external libraries, databases, or LLM-based intent classifiers were introduced:
- Intent detection: 100% deterministic Python regex.
- Complete retrieval: In-memory registry lookup from existing `_parent_store` and verified source files.
- Vector store: Local Qdrant on-disk store reused without schema changes.
- Sparse index: Local BM25 reused without modifications.
- LLM generation: Existing Ollama path preserved for answer synthesis.

---

## 20. Performance Considerations

- **Targeted Fast-Path**: Ordinary factual queries bypass complete parent retrieval entirely, continuing through the cached hybrid top-3 pipeline.
- **Constant Memory Footprint**: Complete category parent strings are either pre-indexed in memory (`parent_store.json`) or read on-demand without unbounded memory consumption.
- **Budget-Aware Context**: Only the requested temple and category are assembled into LLM context, preventing context overflow.

---

## 21. Known Limitations

1. **Single-Temple Complete Lists Only**: Phase J resolves complete lists for an individual temple. Cross-temple list aggregation (e.g. *"Which temples have Abhishekam?"*) belongs to a future aggregation phase.
2. **Pre-requisite of Registered Categories**: Only categories supported by `CategoryRegistry` (e.g. sevas, prasadam, facilities, timings, etc.) are recognized. Unsupported arbitrary concepts (e.g. "spaceships") safely fall back to targeted search.

---

## 22. Next Phase

```text
Next Phase: Phase K — ComparisonAgent
```
