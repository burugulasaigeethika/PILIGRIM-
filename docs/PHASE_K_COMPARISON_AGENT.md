# PilgrimAI — Phase K: ComparisonAgent Documentation

## 1. Objective
Phase K introduces `ComparisonAgent`, a specialized agent derived from `BaseAgent`, dedicated to neutral, factual, and strictly grounded comparisons between two or more registered pilgrimage temples. The agent fulfills comparison queries (e.g. comparing timings, sevas, facilities, or general information) without expressing subjective bias, inventing winners, or fabricating missing data.

---

## 2. Architecture
The multi-agent architecture incorporates `ComparisonAgent` within the standard orchestration flow:

```text
User Query
    ↓
AgentState
    ↓
MasterAgentCoordinator
    ↓
AgentRouter (Intent: "comparison" -> selected_agent: "comparison")
    ↓
ComparisonAgent.execute(state)
    ↓
[Temple & Category Extraction]
    ↓
RAGTool (Isolated per temple)
    ↓
Temple A Data          Temple B Data
    ↓                        ↓
[Conflict & Missing Data Validation]
    ↓
Structured Neutral Synthesis (Markdown Comparison Table / Bullets)
    ↓
AgentResponse (sources_by_temple, metadata)
```

---

## 3. ComparisonAgent
- **Class**: `ComparisonAgent(BaseAgent)` in `backend/app/agents/comparison_agent.py`.
- **Identity**:
  - `name`: `"comparison"`
  - `description`: `"Specialist agent providing neutral, grounded comparisons between two or more registered pilgrimage temples using verified knowledge."`
- **Constructor & Injection**:
  - Accepts `rag_tool: Optional[RAGTool] = None` and `category_registry: Optional[CategoryRegistry] = None`.
  - Automatically loads canonical registered temples dynamically from `RAGTool.get_registered_temples()`.
- **Lifecycle & Contracts**:
  - Inherits from `BaseAgent` and implements `_run(state: AgentState) -> AgentResponse`.
  - Fully records state execution traces (`agent_name="comparison"`, `step_name="execute"`, timing, and status).
  - Populates `state.intermediate_results["comparison"]` and `state.final_response`.

---

## 4. Router Integration
- Minimal modifications to `backend/app/agents/router.py`:
  - `AgentRouter` tracks `active_agents` (`Set[str]`).
  - Added `register_agent(agent_name: str)` method.
  - When `"comparison"` is registered:
    - Queries matching comparison patterns or referencing $\ge 2$ temples route with `selected_agent="comparison"`, `intent="comparison"`, `confidence=0.95`, and `metadata={"available": True}`.
  - When `"comparison"` is NOT registered:
    - Maintains exact backward-compatible Phase D behavior (`selected_agent="none"`, `intent="comparison"`, `metadata={"available": False}`).
  - Refined multi-intent detection so that comparison queries focused on a single factual category (e.g., timings) route cleanly to `ComparisonAgent` rather than fragmenting prematurely into general multi-intent decomposition.

---

## 5. Coordinator Integration
- Minimal modifications to `backend/app/agents/coordinator.py`:
  - `MasterAgentCoordinator.__init__` accepts `comparison_agent: Optional[Any] = None`.
  - When provided, `comparison_agent` is registered in `self.agents` and synchronized via `self.router.register_agent("comparison")`.
  - When absent, maintains exact backward-compatible fallback behavior where comparison queries return an explicit unavailable message.
  - Integrates seamlessly with `SequentialMultiIntentPipeline` and `ConversationMemoryManager`.

---

## 6. RAGTool Boundary & Anti-Leakage
`ComparisonAgent` strictly adheres to architectural boundaries:
- **Zero Direct RAG / Database Imports**:
  - `PilgrimRAGService`: NOT imported.
  - `qdrant_client`: NOT imported.
  - `rank_bm25`: NOT imported.
  - `sentence_transformers`: NOT imported.
  - `CrossEncoder`: NOT imported.
  - `LocalQdrantManager`: NOT imported.
  - Raw JSON files: NOT accessed.
- **Access Interface**:
  - All factual data is retrieved strictly via `self.rag_tool.retrieve(query=..., temple=..., category=..., top_k=...)` or `self.rag_tool.get_complete_parent_text(temple=..., category=...)`.
  - Validated by static code inspection in `tests/test_comparison_agent.py::test_16_rag_tool_only_boundary`.

---

## 7. Temple Resolution
Reuses existing canonical temple resolution and aliases:
- Identifies registered temples in order of query mention.
- Reuses canonical mappings (e.g. `Yadagirigutta` $\to$ `Yadadri`, `Visa Balaji` $\to$ `Chilkur`, `Vana Durga Bhavani` $\to$ `Edupayal`).
- Categorizes input according to the four specified safeguards:
  1. **Two Known Temples** (e.g., `Compare Yadadri and Dharmapuri`): Proceeds with normal comparison.
  2. **One Known Temple Only** (e.g., `Compare Yadadri facilities`): Controlled clarification response requesting the second temple (`error="Insufficient temples for comparison"`).
  3. **Explicitly Named Unknown Temple** (e.g., `Compare Yadadri and Atlantis Temple`): Controlled refusal indicating that the named temple is not in the verified knowledge base (`error="Unregistered temple"`). Zero hallucination.
  4. **Zero Identifiable Temples** (e.g., `Compare the temples`): Controlled clarification response prompting the user to name the temples (`error="No temples specified"`).

---

## 8. Category Resolution
- Reuses `CategoryRegistry` patterns (from `app.rag.knowledge_registry`) for deterministic category detection (`timings`, `facilities`, `sevas`, `accommodation`, `darshan`, `prasadam`, `history`, `travel`, `contact`).
- For category-specific comparisons (e.g., `Compare facilities at Yadadri and Bhadrachalam`), extracts and formats evidence specifically for that category.
- For broad comparisons without an explicit category, retrieves core factual aspects conservatively across registered categories without querying entire raw datasets.

---

## 9. Retrieval Strategy
- **Independent Temple Queries**: Evidence for Temple A and Temple B is retrieved independently using separate calls with `temple_filter=canonical_name`.
- Conceptually:
  $$\text{Temple A} \to \text{RAGTool} \to \text{Evidence A}$$
  $$\text{Temple B} \to \text{RAGTool} \to \text{Evidence B}$$
- Evidence is never merged before temple attribution is established.
- Retrieval parameters remain strictly within frozen defaults: no increase in `TOP_K` or `FINAL_RERANK_TOP_K`.

---

## 10. Temple Isolation
- Every retrieved snippet is tagged with its source temple.
- Evidence structures maintain `sources_by_temple: Dict[str, List[Dict[str, Any]]]`.
- Output formatting ensures Temple A data is strictly confined to Temple A's column or bullet group, eliminating cross-temple attribution contamination.

---

## 11. Neutral Output Behavior & "No Automatic Winner"
- Comparison output follows structured Markdown tables or formatted bullet lists:
  ```markdown
  ### Comparison: Yadadri vs Dharmapuri

  | Aspect | Yadadri | Dharmapuri |
  |---|---|---|
  | Timings | ... | ... |
  | Facilities | ... | ... |

  **Sources:**
  - **Yadadri**: ...
  - **Dharmapuri**: ...
  ```
- **Strict Neutrality**:
  - Zero subjective qualifiers (`better`, `best`, `superior`, `worse`, `winner`).
  - Differences are presented purely as factual counts or descriptions (e.g., "Yadadri lists 26 verified facilities, while Dharmapuri lists verified facilities for...").
  - Verified by `test_19_neutral_output` and `test_20_no_automatic_winner`.

---

## 12. Unknown Temple Handling
- Detects famous unregistered temples (e.g., `Atlantis`, `Golden Temple`, `Somnath`, `Kedarnath`) or syntactic temple patterns not in the 20 registered temples.
- Returns a controlled refusal: `"I don't have verified records for '<Unknown Temple>' in the pilgrimage knowledge base."`
- Never attempts retrieval for or hallucination of unregistered entities.

---

## 13. Missing-Data Handling
- Distinguishes clearly between:
  - `"No verified category data available in the current knowledge base."` (unattested in records).
  - Explicit absence: `"The temple has no such facility."` (only if authoritative sources explicitly confirm it).
- Never fabricates missing values or guesses absent categories.

---

## 14. Conflict Handling
- If conflicting operational information (e.g., disparate morning opening hours in differing sections) is detected in the evidence:
  - Preserves both reported values.
  - Informs the user of the variance with an explicit verification advisory.
  - Verified by `test_22_conflicting_data_handling`.

---

## 15. Partial Failure Handling
- If one temple's retrieval succeeds and the other yields no matching data:
  - Preserves and presents the successful temple's evidence.
  - Explicitly states that verified records were not found for the second temple.
  - Verified by `test_23_partial_retrieval_failure`.

---

## 16. Phase H Compatibility
- Compatible with `SequentialMultiIntentPipeline`.
- Complex multi-clause queries (e.g. `"What are the timings of Yadadri? Compare facilities of Yadadri vs Dharmapuri"`) are decomposed into independent sub-tasks:
  - Task 1: `temple_information` targeting `TempleInformationAgent`.
  - Task 2: `comparison` targeting `ComparisonAgent`.
- Verified by `test_24_phase_h_compatibility`.

---

## 17. Phase I Compatibility
- Seamless multi-turn compatibility with `ConversationMemoryManager`:
  - When memory safely resolves pronouns, `ComparisonAgent` processes the resolved comparison.
  - When an ambiguous pronoun co-occurs with an explicit new temple and memory safely preserves the input without guessing, `ComparisonAgent` requests clarification for the missing temple (Case 2 safeguard).
- Verified by `test_25_phase_i_compatibility`.

---

## 18. Phase J Compatibility
- Seamless compatibility with Phase J complete-list retrieval:
  - Queries comparing full listings (e.g., `"Compare all sevas at Dharmapuri and Yadadri"`) leverage complete parent representations via `RAGTool`.
  - Both sides receive verified comprehensive lists (e.g., all 10 Dharmapuri sevas).
  - Verified by `test_26_phase_j_compatibility`.

---

## 19. Test Coverage
`tests/test_comparison_agent.py` implements **30 comprehensive tests**:
1. `test_1_base_agent_inheritance`: Inherits from `BaseAgent`.
2. `test_2_agent_initialization`: Attribute verification and dependency injection.
3. `test_3_agent_lifecycle_contract`: State traces, latency, and intermediate results.
4. `test_4_router_activation`: Dynamic route activation upon agent registration.
5. `test_5_coordinator_registration`: Coordinator agent registration.
6. `test_6_coordinator_dispatch`: End-to-end dispatch through coordinator.
7. `test_7_two_canonical_temples`: Normal comparison between two known temples.
8. `test_8_temple_aliases_resolution`: Canonical resolution of temple aliases.
9. `test_9_zero_temple_clarification`: Prompting user when zero temples are identified.
10. `test_10_one_temple_clarification`: Requesting second temple when only one is identified.
11. `test_11_explicit_unknown_temple_handling`: Controlled refusal on unregistered temples.
12. `test_12_timings_comparison`: Timings comparison between temples.
13. `test_13_facilities_comparison`: Facilities comparison between temples.
14. `test_14_sevas_comparison`: Sevas comparison between temples.
15. `test_15_broad_comparison`: Broad comparison across multiple categories.
16. `test_16_rag_tool_only_boundary`: Static AST / regex check enforcing zero direct forbidden imports.
17. `test_17_temple_isolation`: Ensuring Temple A and Temple B evidence are strictly isolated.
18. `test_18_source_preservation`: Verification of `sources_by_temple` metadata.
19. `test_19_neutral_output`: Verification of neutral, non-evaluative phrasing.
20. `test_20_no_automatic_winner`: Guaranteeing absence of subjective winner declarations.
21. `test_21_missing_data_handling`: Unattested category data handling.
22. `test_22_conflicting_data_handling`: Conflict detection and advisory preservation.
23. `test_23_partial_retrieval_failure`: Partial retrieval survival without fabrication.
24. `test_24_phase_h_compatibility`: Multi-intent pipeline sub-task dispatch.
25. `test_25_phase_i_compatibility`: Conversation memory multi-turn handling.
26. `test_26_phase_j_compatibility`: Complete list integration.
27. `test_27_empty_query_handling`: Validation and graceful refusal for empty queries.
28. `test_28_whitespace_query_handling`: Validation for whitespace-only queries.
29. `test_29_deterministic_repeated_execution`: Repeated execution determinism.
30. `test_30_backward_compatibility_router_and_coordinator`: Baseline fallback preservation.

All **30/30 tests passed**.

---

## 20. Regression Results
Full regression run across all 12 test suites:
- `test_agent_contracts.py` (10 tests)
- `test_rag_tool.py` (10 tests)
- `test_temple_information_agent.py` (10 tests)
- `test_agent_router.py` (13 tests)
- `test_response_aggregator.py` (13 tests)
- `test_master_agent_coordinator.py` (13 tests)
- `test_agent_state.py` (17 tests)
- `test_multi_intent_pipeline.py` (18 tests)
- `test_conversation_memory.py` (24 tests)
- `test_query_planner.py` (40 tests)
- `test_complete_list_retrieval.py` (22 tests)
- `test_comparison_agent.py` (30 tests)

**TOTAL: 220 passed, 0 failed.**

---

## 21. Protected-File Verification & Dataset Integrity
- **Temple Directories**: 20 verified.
- **Source JSON Files**: 417 verified.
- **Specific Ground-Truth Counts**:
  - Dharmapuri sevas: 10 verified.
  - Yadadri facilities: 26 verified.
  - Edupayala prasadam: 2 verified.
- **Protected Files**:
  - `qdrant_db/`: Untouched.
  - `bm25_index/`: Untouched.
  - `evaluation/`: Untouched.
  - `.env`: Untouched.
  - `frontend/`: Untouched.
  - `backend/app/api/chat.py`: Untouched.
  - `backend/app/main.py`: Untouched.
  - `backend/app/rag/query_planner.py`: Untouched.
  - `backend/app/rag/knowledge_registry.py`: Untouched.

---

## 22. Known Limitations
- Comparison is strictly factual based on attested records in the 417 JSON files; historical or folklore comparisons rely entirely on existing summary documents.
- Comparisons involving more than 3 temples simultaneously use structured bullet lists rather than wide tabular formats to prevent layout fragmentation.

---

## 23. Next Phase
Phase K is complete and certified. Phase L is **NOT STARTED**.
