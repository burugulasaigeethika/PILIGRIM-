# PilgrimAI Comprehensive RAG Evaluation Report

**Evaluation Date**: 2026-08-24 22:39:02  
**Total Questions Evaluated**: 252  
**Total Temples Evaluated**: 20  
**Evaluation Duration**: 7666.04s  
**Model Config**: Ollama `qwen2.5:1.5b` (Local @ `http://localhost:11434`)  
**Storage**: `D:\PiligrimAI -c\qdrant_db` & `D:\PiligrimAI -c\bm25_index`

---

## 1. Executive Summary & Threshold Classification

| Evaluation Metric | Measured Value | Standard Threshold | Status |
|---|---|---|---|
| **Temple Isolation Rate** | **77.73%** | ≥ 99.0% | WARNING |
| **Hybrid Top-5 Retrieval** | **93.70%** | ≥ 90.0% | PASS |
| **Answer Accuracy** | **84.52%** | ≥ 85.0% | WARNING |
| **Groundedness Rate** | **99.21%** | ≥ 90.0% | PASS |
| **Negative Query Handling** | **85.71%** | ≥ 90.0% | WARNING |

---

## 2. Retrieval Performance Comparison

| Retriever Stage | Top-1 Accuracy | Top-3 Accuracy | Top-5 Accuracy | Source Hit Rate |
|---|---|---|---|---|
| **Qdrant (Dense)** | 68.91% | 84.03% | 88.24% | 65.97% |
| **BM25 (Sparse)** | 23.11% | 59.66% | 75.63% | 36.97% |
| **Hybrid + Reranker** | **77.73%** | **85.29%** | **93.70%** | **77.31%** |

---

## 3. Cross-Temple Contamination & Isolation

- **Overall Isolation Percentage**: **77.73%**
- **Top-1 Contamination Count**: 53 / 238
- **Top-3 Contamination Count**: 131 / 238
- **Top-5 Contamination Count**: 179 / 238

---

## 4. Answer Quality & Generation

- **Correct Answers**: 213 (84.52%)
- **Partially Correct Answers**: 24 (9.52%)
- **Incorrect / Refused**: 13 (5.16%)
- **Hallucinations Detected**: 2 (0.79%)
- **Unanswerable Questions Refused Correctly**: 12 / 14 (85.71%)

---

## 5. Latency Profile

| Stage | Average Latency | Median Latency | P95 Latency |
|---|---|---|---|
| **Qdrant Dense Search** | 120.86 ms | 105.91 ms | 262.38 ms |
| **BM25 Sparse Search** | 43.58 ms | 44.1 ms | 70.01 ms |
| **Cross-Encoder Reranker** | 868.37 ms | 836.17 ms | 1464.31 ms |
| **Total End-to-End Pipeline** | **29385.94 ms** | **25435.34 ms** | **58086.61 ms** |

---

## 6. Per-Temple Detailed Breakdown

| Temple Name | Questions | Hybrid Top-5 | Answer Accuracy | Temple Isolation | Avg Latency |
|---|---|---|---|---|---|
| **Ahobilam** | 13 | 91.67% | 84.62% | 83.33% | 19766.44 ms |
| **Badrachalam** | 13 | 100.0% | 92.31% | 75.0% | 21971.31 ms |
| **Balkampet** | 12 | 91.67% | 83.33% | 83.33% | 18412.24 ms |
| **Basara** | 13 | 91.67% | 76.92% | 75.0% | 17382.51 ms |
| **Birla Mandir** | 13 | 91.67% | 100.0% | 75.0% | 25706.68 ms |
| **Chilkur** | 13 | 100.0% | 92.31% | 83.33% | 35546.69 ms |
| **Dharmapuri** | 13 | 100.0% | 84.62% | 66.67% | 34093.75 ms |
| **Edupayal** | 13 | 91.67% | 69.23% | 91.67% | 28841.93 ms |
| **Jogulamba(New)** | 12 | 100.0% | 100.0% | 100.0% | 34413.33 ms |
| **Kaleshvaram** | 12 | 83.33% | 66.67% | 75.0% | 34227.02 ms |
| **Karmanghat** | 13 | 91.67% | 76.92% | 66.67% | 30621.89 ms |
| **Medaram** | 13 | 100.0% | 76.92% | 41.67% | 30879.29 ms |
| **Ramappa** | 12 | 100.0% | 91.67% | 72.73% | 28155.69 ms |
| **Srisaila** | 12 | 83.33% | 75.0% | 75.0% | 33270.64 ms |
| **Thousand Pillar** | 13 | 91.67% | 92.31% | 83.33% | 25777.91 ms |
| **Ttd** | 11 | 81.82% | 63.64% | 81.82% | 44185.0 ms |
| **Ujjaini** | 13 | 91.67% | 76.92% | 66.67% | 29334.94 ms |
| **Veera Satyanarayana** | 12 | 100.0% | 100.0% | 83.33% | 37011.31 ms |
| **Vemulavada** | 13 | 100.0% | 92.31% | 100.0% | 27647.85 ms |
| **Yadadri** | 13 | 91.67% | 92.31% | 75.0% | 33454.99 ms |

---

## 7. Failure Analysis

- **Total Execution Exceptions**: 0
*(Zero runtime crashes or fatal pipeline errors encountered)*
