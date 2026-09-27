# Phase 7 Architecture Report: Answer-Level Grounding & Scope Control

## 1. Overview & Problem Definition
In real-world end-to-end usage, retrieval models can retrieve accurate documents, but generation layers may accidentally hallucinate facts or dump unrelated categories (e.g. answering a targeted question about *Bhadrachalam timings* with a broad overview covering *Dharmapuri Abhishekam pricing, Basara festivals, hotels, rules, and history*).

> [!IMPORTANT]
> **Core Architectural Principle**:
> *"Retrieval Completeness and Answer Scope are two separate invariants."*
> - The retrieval layer retrieves all necessary evidence.
> - The **Answer Scope Controller** and **Answer Grounding Validator** enforce that the final output answers **ONLY** what the user requested, eliminating unrequested category pollution.

---

## 2. Components Created

### A. [answer_scope_controller.py](file:///d:/PiligrimAI%20-c/backend/app/rag/answer_scope_controller.py)
Implements `AnswerScopeController` and the `AnswerScope` dataclass:
- **Scope Derivation**: Converts a `QueryPlan` into strict answer boundaries (`temples`, `categories`, `allow_unrequested_categories`, `prohibited_categories`).
- **Context Filtering**: Filters out unrequested categories from candidate documents before they reach the LLM prompt for targeted fact queries.
- **Dynamic Scoped Prompts**: Formulates tailored generation instructions explicitly forbidding foreign temples or unrequested category dumps.

### B. [answer_grounding_validator.py](file:///d:/PiligrimAI%20-c/backend/app/rag/answer_grounding_validator.py)
Implements `AnswerGroundingValidator`:
- **Temple Scope Audit**: Flags foreign temple names in single-temple queries.
- **Category Scope Audit**: Flags unrequested section headers/dumps in targeted factual responses.
- **Entity Existence Check**: Detects affirmative claims for non-existent/fictitious entities (e.g. *rocket launch pad, ski resort*) and enforces grounded refusal (`DEFAULT_REFUSAL_MESSAGE`).
- **Sanitizer / Trimmer**: Safely cleans extraneous category headers if generated.

---

## 3. Grounding & Scope Evaluation Results

| Test Query | Target Scope | Retr. Mode | Unrelated Info Detected | Status |
| :--- | :---: | :---: | :---: | :---: |
| *What are the temple timings at Bhadrachalam?* | `Bhadrachalam` / `timings` | `targeted` | **0 violations** | ✅ **PASSED** |
| *What is the price of Abhishekam in Dharmapuri?* | `Dharmapuri` / `sevas` | `targeted` | **0 violations** | ✅ **PASSED** |
| *What are all the sevas in Dharmapuri?* | `Dharmapuri` / `sevas` | `complete_category` | **0 violations** | ✅ **PASSED** |
| *List all festivals at Basara.* | `Basara` / `festivals` | `complete_category` | **0 violations** | ✅ **PASSED** |
| *List all temples that have a river bank.* | `*` / `river_bank` | `cross_temple_aggregation` | **0 violations** | ✅ **PASSED** |
| *List all temples that don't have wheelchair facilities.* | `*` / `wheelchair` | `cross_temple_aggregation` | **0 violations** | ✅ **PASSED** |
| *What accommodation and restaurants are available near Dharmapuri?* | `Dharmapuri` / `acc`, `rest` | `multi_category` | **0 violations** | ✅ **PASSED** |
| *Tell me the history of Yadadri.* | `Yadadri` / `temple` | `targeted` | **0 violations** | ✅ **PASSED** |
| *Tell me everything about Dharmapuri Temple.* | `Dharmapuri` / `*` | `broad_temple` | **0 violations** | ✅ **PASSED** |
| *Does Dharmapuri have wheelchair facilities?* | `Dharmapuri` / `wheelchair` | `targeted` | **0 violations** | ✅ **PASSED** |
| *Does Dharmapuri have a helicopter launch pad?* | `Dharmapuri` / `*` | `targeted` | **0 violations** | ✅ **PASSED (Refusal)** |

- **Unrelated Information Rate**: **`0.0%`** across all targeted queries.

---

## 4. Test Suite Summary
- **Baseline Tests (Phases 1–6)**: `119 / 119 PASSED`
- **Phase 7 Unit & Integration Tests**: `20 / 20 PASSED`
- **Total Project Tests (`pytest tests/ -v`)**: **`139 / 139 PASSED (100%)`**
- **Regressions**: **`0`**

---

## 5. Invariance & Offline Safety Confirmation
- **Source JSON files**: 100% untouched.
- **Qdrant Vector Database**: 100% untouched.
- **BM25 Inverted Index**: 100% untouched.
- **Ollama models (`D:\Ollama\models`)**: 100% untouched.
- **Local Model**: `qwen2.5:1.5b` remains the local generation model.
- **100% Offline**: Zero external APIs or cloud dependencies.
