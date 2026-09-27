# PilgrimAI Comprehensive RAG Evaluation Suite

This directory contains the automated, deterministic, read-only evaluation framework for the PilgrimAI Telangana Temples RAG system.

---

## 1. Quickstart / Reproducibility

To run the complete evaluation against the local production RAG and Ollama service:

```powershell
& 'D:\temple rag 1\.venv\Scripts\python.exe' evaluation/run_evaluation.py
```

---

## 2. Directory Structure

- `dataset_generator.py`: Generates the canonical ~250 ground-truth evaluation questions from the 20 temple JSON folders with fixed seed (`42`).
- `evaluator.py`: Multi-stage evaluator evaluating Qdrant, BM25, Hybrid RRF, Cross-Encoder reranking, temple isolation, and Ollama `qwen2.5:1.5b` grounded generation.
- `run_evaluation.py`: Main CLI runner that executes all queries, computes metrics, and outputs artifacts.
- `evaluation_dataset.json`: Canonical ground-truth evaluation dataset with 252 questions.
- `metadata.json`: Metadata for all 20 discovered temples.
- `evaluation_results.json`: Detailed per-query execution records across all stages.
- `retrieval_results.json`: Dense vs Sparse vs Hybrid retrieval metrics.
- `contamination_results.json`: Cross-temple isolation records.
- `answer_results.json`: Model-generated answers and grading.
- `metrics.json`: Summary and per-temple aggregate metrics.
- `evaluation_report.md`: Formatted human-readable evaluation report.

---

## 3. Evaluation Rubric & Thresholds

| Metric | Target Standard | Description |
|---|---|---|
| **Temple Isolation** | ≥ 99.0% | Ensures queries for a temple only retrieve context from that temple. |
| **Hybrid Top-5 Retrieval** | ≥ 90.0% | Ensures relevant temple documents are present in candidate context. |
| **Answer Accuracy** | ≥ 85.0% | Deterministic factual match against ground-truth dataset facts. |
| **Groundedness Rate** | ≥ 90.0% | Ensures generated answers do not contain unsupported claims. |
| **Negative Handling** | ≥ 90.0% | Ensures unanswerable queries are gracefully refused without hallucinations. |
