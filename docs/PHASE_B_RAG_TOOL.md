# PilgrimAI: Phase B — RAGTool Read-Only Facade

**Date:** September 17, 2026  
**Project:** PilgrimAI: A RAG-Based Multi-Agent Assistant for Smart Pilgrimage  
**Workspace:** `d:\pligrim ai new`  
**Phase:** Phase B: RAGTool Read-Only Facade  
**Status:** Certified & Passed (10/10 tests in 41.14s)  

---

## 1. RAGTool Purpose

`RAGTool` serves as the **strictly controlled, read-only boundary** separating all future specialist agents (`TempleInformationAgent`, `ComparisonAgent`, `CrossTempleAggregationAgent`, `CompleteListRetriever`, `ItineraryPlanningAgent`) from the frozen low-level RAG infrastructure.

By wrapping `PilgrimRAGService` and `KnowledgeRegistry`, `RAGTool` eliminates any possibility of:
- Agents directly modifying on-disk vector stores (`qdrant_db/`) or sparse inverted indices (`bm25_index/`).
- Agents accessing raw filesystem JSONs or creating fragmented ingestion scripts.
- Agents depending directly on low-level database drivers (`qdrant_client`, `rank_bm25`, `sentence_transformers`).

---

## 2. Architecture & Layering

```text
Future Specialist Agents
          │
          ▼
       RAGTool
   READ-ONLY FACADE
          │
          ▼
  PilgrimRAGService
          │
    ┌─────┼─────┐
    ▼     ▼     ▼
 Qdrant  BM25  Reranker
          │
          ▼
    Verified Dataset
 (417 Source JSON Files)
```

---

## 3. Public Method Contracts & Delegation Mapping

`RAGTool` exposes a clean, strongly-typed interface that maps directly to the verified methods of the existing RAG pipeline:

| RAGTool Method | Underlying RAG Target | Return Type | Purpose |
| :--- | :--- | :--- | :--- |
| `retrieve(query, temple, category, top_k)` | `PilgrimRAGService.retrieve_with_metadata()` or `retrieve()` | `List[RAGChunk]` | Hybrid Dense + Sparse + Cross-Encoder retrieval normalized to `RAGChunk`. |
| `get_temple_category_data(temple, category)` | `KnowledgeRegistry.get_temple_raw_data()` | `Optional[Any]` | Read-only inspection of source JSON data (lists or dictionaries). |
| `get_complete_parent_text(temple, category)` | `KnowledgeRegistry.get_complete_parent()` | `Optional[str]` | Exhaustive, non-truncated parent category text from parent store. |
| `get_registered_temples()` | `KnowledgeRegistry.get_temples()` | `List[str]` | Sorted list of all 20 canonical registered temples. |
| `get_registered_categories()` | `KnowledgeRegistry.get_categories()` | `List[str]` | List of all 21 registered dataset categories. |
| `execute_grounded_rag(question)` | `PilgrimRAGService.answer()` | `Dict[str, Any]` | Full end-to-end grounded query execution via Qwen2.5 with answer scoping. |

---

## 4. Read-Only Rules and Data Protection

1. **Zero Write Methods:** `RAGTool` does not implement or expose methods such as `ingest()`, `rebuild()`, `delete()`, `update()`, `insert()`, `upsert()`, `reset()`, or `modify_dataset()`.
2. **Immutable Chunks:** Chunks returned by `RAGTool` are immutable Pydantic instances (`model_config = ConfigDict(frozen=True)`).
3. **No File Mutation:** All dataset reads through `KnowledgeRegistry` operate strictly in read mode (`open(..., "r")`).

---

## 5. Result Normalization: `RAGChunk`

To prevent future agents from coupling to LangChain's internal `Document` schema, `RAGTool` converts all retrieved documents into `RAGChunk`:

```python
class RAGChunk(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    text: str = Field(..., description="Text content of the retrieved passage or parent context")
    temple: Optional[str] = Field(default=None, description="Associated canonical temple name if identified")
    category: Optional[str] = Field(default=None, description="Category of the passage (e.g., 'timings', 'sevas')")
    source: Optional[str] = Field(default=None, description="Relative source path (e.g., 'yadadri/timings.json')")
    score: Optional[float] = Field(default=None, description="Cross-encoder rerank relevance score")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional passage metadata")
```

---

## 6. Error Handling Strategy

- **No Silent Fallbacks:** If an invalid query (e.g., empty string) is provided to `execute_grounded_rag()`, it raises a descriptive `ValueError` rather than inventing an answer.
- **Exception Transparency:** Underlying RAG exceptions are logged with full stack traces and propagated to the caller, enabling future agent coordinators to make informed routing or recovery decisions.

---

## 7. Dependency Boundaries Audit

Verification confirms:
- `backend/app/agents/tools/rag_tool.py` **DOES NOT IMPORT**:
  - `qdrant_client`
  - `rank_bm25`
  - `sentence_transformers`
  - `LocalQdrantManager`
  - `LocalBM25Manager`
- `RAGTool` interacts exclusively with the high-level services `PilgrimRAGService` and `KnowledgeRegistry`.

---

## 8. Verification and Test Results

### 8.1 Phase B Integration Tests (`tests/test_rag_tool.py`)
- Total tests: **10**
- Passing: **10 (100%)**
- Duration: **41.14 seconds** (executing against live local models & indices)

| Test Name | Focus | Result |
| :--- | :--- | :--- |
| `test_1_rag_tool_initialization` | Verifies RAGTool initializes and connects to underlying RAG service | **PASS** |
| `test_2_retrieve_factual_query` | Confirms `retrieve()` returns normalized `RAGChunk` list | **PASS** |
| `test_3_chunk_metadata_and_source_normalization` | Confirms chunk fields (text, source, score, metadata) | **PASS** |
| `test_4_execute_grounded_rag_delegation` | Tests grounded answer generation for Yadadri timings query | **PASS** |
| `test_5_get_registered_temples` | Confirms exactly 20 canonical temples returned | **PASS** |
| `test_6_get_registered_categories` | Confirms all 21 dataset categories returned | **PASS** |
| `test_7_raw_category_and_complete_parent_retrieval` | Confirms read-only access to JSON and parent store | **PASS** |
| `test_8_rag_tool_is_strictly_read_only` | Validates zero write/mutation methods exposed | **PASS** |
| `test_9_rag_tool_does_not_import_database_internals` | Inspects source code to certify strict dependency boundary | **PASS** |
| `test_10_error_handling_and_no_hallucinated_fallbacks` | Confirms empty queries raise errors and do not fabricate facts | **PASS** |

### 8.2 Regression Integrity Checks
- **Phase A Contracts (`tests/test_agent_contracts.py`):** **10/10 passed** (0.20s)
- **RAG Baseline (`tests/test_query_planner.py`):** **40/40 passed** (0.09s)

---

## 9. Protected Files Verification

```text
Files Created:
- backend/app/agents/tools/__init__.py
- backend/app/agents/tools/rag_tool.py
- tests/test_rag_tool.py
- docs/PHASE_B_RAG_TOOL.md

Protected Files Modified:
- NONE (0 files changed in backend/app/rag/, qdrant_db/, bm25_index/, temple JSONs, .env, requirements.txt, frontend, or legacy agents)
```
