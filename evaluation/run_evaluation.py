import os
import sys
import json
import time
import statistics
from pathlib import Path
from typing import Dict, Any, List

# Setup sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from evaluation.dataset_generator import generate_evaluation_dataset
from evaluation.evaluator import ComprehensiveEvaluator

def calculate_percentile(data: List[float], percentile: float) -> float:
    """Calculate p95 or other percentiles safely."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * (percentile / 100.0))
    idx = min(idx, len(sorted_data) - 1)
    return round(sorted_data[idx], 2)

def run_full_evaluation():
    eval_dir = root_dir / "evaluation"
    eval_dir.mkdir(parents=True, exist_ok=True)
    dataset_file = eval_dir / "evaluation_dataset.json"

    if not dataset_file.exists():
        print("Evaluation dataset not found. Generating...")
        generate_evaluation_dataset()

    with open(dataset_file, "r", encoding="utf-8") as f:
        dataset_payload = json.load(f)

    questions = dataset_payload["questions"]
    metadata = dataset_payload["metadata"]

    print("==================================================")
    print(f"STARTING COMPREHENSIVE EVALUATION ON {len(questions)} QUERIES")
    print(f"Total Temples: {metadata['total_temples']}")
    print(f"Random Seed  : {metadata['random_seed']}")
    print("==================================================")

    evaluator = ComprehensiveEvaluator()

    all_results = []
    retrieval_records = []
    contamination_records = []
    answer_records = []
    failures = []

    start_time = time.time()

    for idx, item in enumerate(questions, 1):
        q_id = item["id"]
        q_text = item["question"]
        t_id = item["temple_id"]

        print(f"[{idx:03d}/{len(questions):03d}] ({t_id}) {q_text[:60]}...", flush=True)

        try:
            res = evaluator.evaluate_single_query(item)
            all_results.append(res)

            # Stage records
            retrieval_records.append({
                "id": q_id,
                "temple_id": t_id,
                "question": q_text,
                "expected_sources": item.get("source_files", []),
                "qdrant": res["stages"]["qdrant"],
                "bm25": res["stages"]["bm25"],
                "hybrid_rerank": res["stages"]["hybrid_rerank"]
            })

            contamination_records.append({
                "id": q_id,
                "temple_id": t_id,
                "question": q_text,
                "answerable": item.get("answerable", True),
                "isolation": res["stages"]["isolation"],
                "top3_temples": res["stages"]["hybrid_rerank"]["top3_temples"]
            })

            answer_records.append({
                "id": q_id,
                "temple_id": t_id,
                "question": q_text,
                "expected_answer": item.get("expected_answer", ""),
                "generated_answer": res["stages"]["generation"]["generated_answer"],
                "answer_grade": res["stages"]["generation"]["answer_grade"],
                "confidence_score": res["stages"]["generation"]["confidence_score"],
                "hallucination_detected": res["stages"]["generation"]["hallucination_detected"],
                "total_latency_ms": res["stages"]["generation"]["total_latency_ms"]
            })

        except Exception as e:
            print(f"  [ERROR] Query {q_id} failed: {e}")
            failures.append({
                "id": q_id,
                "temple_id": t_id,
                "question": q_text,
                "error": str(e)
            })

    total_eval_time = time.time() - start_time
    print(f"\nEvaluation loop completed in {total_eval_time:.2f} seconds.")

    # -----------------------------------------------------------------
    # METRICS COMPUTATION
    # -----------------------------------------------------------------
    total_q = len(all_results)
    ans_q = [r for r in all_results if r["answerable"]]
    unans_q = [r for r in all_results if not r["answerable"]]

    # Qdrant Metrics
    q_top1 = sum(1 for r in ans_q if r["stages"]["qdrant"]["top1_temple"]) / len(ans_q) * 100 if ans_q else 0
    q_top3 = sum(1 for r in ans_q if r["stages"]["qdrant"]["top3_temple"]) / len(ans_q) * 100 if ans_q else 0
    q_top5 = sum(1 for r in ans_q if r["stages"]["qdrant"]["top5_temple"]) / len(ans_q) * 100 if ans_q else 0
    q_src_hit = sum(1 for r in ans_q if r["stages"]["qdrant"]["top3_source"]) / len(ans_q) * 100 if ans_q else 0

    # BM25 Metrics
    bm_top1 = sum(1 for r in ans_q if r["stages"]["bm25"]["top1_temple"]) / len(ans_q) * 100 if ans_q else 0
    bm_top3 = sum(1 for r in ans_q if r["stages"]["bm25"]["top3_temple"]) / len(ans_q) * 100 if ans_q else 0
    bm_top5 = sum(1 for r in ans_q if r["stages"]["bm25"]["top5_temple"]) / len(ans_q) * 100 if ans_q else 0
    bm_src_hit = sum(1 for r in ans_q if r["stages"]["bm25"]["top3_source"]) / len(ans_q) * 100 if ans_q else 0

    # Hybrid & Rerank Metrics
    hy_top1 = sum(1 for r in ans_q if r["stages"]["hybrid_rerank"]["top1_temple"]) / len(ans_q) * 100 if ans_q else 0
    hy_top3 = sum(1 for r in ans_q if r["stages"]["hybrid_rerank"]["top3_temple"]) / len(ans_q) * 100 if ans_q else 0
    hy_top5 = sum(1 for r in ans_q if r["stages"]["hybrid_rerank"]["top5_temple"]) / len(ans_q) * 100 if ans_q else 0
    hy_src_hit = sum(1 for r in ans_q if r["stages"]["hybrid_rerank"]["top3_source"]) / len(ans_q) * 100 if ans_q else 0
    rerank_improvements = sum(r["stages"]["hybrid_rerank"]["rerank_improvement"] for r in ans_q)

    # Temple Isolation & Contamination
    top1_contams = sum(1 for r in ans_q if r["stages"]["isolation"]["top1_contamination"])
    top3_contams = sum(1 for r in ans_q if r["stages"]["isolation"]["top3_contamination"])
    top5_contams = sum(1 for r in ans_q if r["stages"]["isolation"]["top5_contamination"])
    isolation_rate = (1.0 - (top1_contams / len(ans_q))) * 100 if ans_q else 100.0

    # Answer Quality
    correct_count = sum(1 for r in all_results if r["stages"]["generation"]["answer_grade"] == "CORRECT")
    partial_count = sum(1 for r in all_results if r["stages"]["generation"]["answer_grade"] == "PARTIAL")
    incorrect_count = sum(1 for r in all_results if r["stages"]["generation"]["answer_grade"] in ["INCORRECT", "REFUSED_ANSWERABLE"])
    hallucinated_count = sum(1 for r in all_results if r["stages"]["generation"]["hallucination_detected"])
    unans_handled = sum(1 for r in unans_q if r["stages"]["generation"]["answer_grade"] == "CORRECT")

    accuracy_rate = (correct_count / total_q) * 100 if total_q else 0
    partial_rate = (partial_count / total_q) * 100 if total_q else 0
    incorrect_rate = (incorrect_count / total_q) * 100 if total_q else 0
    hallucination_rate = (hallucinated_count / total_q) * 100 if total_q else 0
    unans_accuracy = (unans_handled / len(unans_q)) * 100 if unans_q else 100.0
    groundedness_rate = 100.0 - hallucination_rate

    # Latency Distributions
    latencies_qdrant = [r["stages"]["qdrant"]["latency_ms"] for r in all_results]
    latencies_bm25 = [r["stages"]["bm25"]["latency_ms"] for r in all_results]
    latencies_rerank = [r["stages"]["hybrid_rerank"]["rerank_latency_ms"] for r in all_results]
    latencies_total = [r["stages"]["generation"]["total_latency_ms"] for r in all_results]

    latency_metrics = {
        "qdrant_avg_ms": round(statistics.mean(latencies_qdrant), 2),
        "qdrant_median_ms": round(statistics.median(latencies_qdrant), 2),
        "qdrant_p95_ms": calculate_percentile(latencies_qdrant, 95),
        "bm25_avg_ms": round(statistics.mean(latencies_bm25), 2),
        "bm25_median_ms": round(statistics.median(latencies_bm25), 2),
        "bm25_p95_ms": calculate_percentile(latencies_bm25, 95),
        "rerank_avg_ms": round(statistics.mean(latencies_rerank), 2),
        "rerank_median_ms": round(statistics.median(latencies_rerank), 2),
        "rerank_p95_ms": calculate_percentile(latencies_rerank, 95),
        "total_avg_ms": round(statistics.mean(latencies_total), 2),
        "total_median_ms": round(statistics.median(latencies_total), 2),
        "total_p95_ms": calculate_percentile(latencies_total, 95),
        "total_min_ms": round(min(latencies_total), 2),
        "total_max_ms": round(max(latencies_total), 2)
    }

    # Per-Temple Breakdown
    per_temple_metrics = {}
    temples_list = sorted(list({r["temple_id"] for r in all_results}))

    for tid in temples_list:
        t_records = [r for r in all_results if r["temple_id"] == tid]
        t_ans_records = [r for r in t_records if r["answerable"]]
        t_corr = sum(1 for r in t_records if r["stages"]["generation"]["answer_grade"] == "CORRECT")
        t_contam = sum(1 for r in t_ans_records if r["stages"]["isolation"]["top1_contamination"])
        t_hy_top5 = sum(1 for r in t_ans_records if r["stages"]["hybrid_rerank"]["top5_temple"])
        t_latencies = [r["stages"]["generation"]["total_latency_ms"] for r in t_records]

        per_temple_metrics[tid] = {
            "temple_name": t_records[0]["temple_name"],
            "total_questions": len(t_records),
            "answer_accuracy_pct": round((t_corr / len(t_records)) * 100, 2),
            "hybrid_top5_pct": round((t_hy_top5 / len(t_ans_records)) * 100, 2) if t_ans_records else 100.0,
            "isolation_pct": round((1.0 - (t_contam / len(t_ans_records))) * 100, 2) if t_ans_records else 100.0,
            "avg_latency_ms": round(statistics.mean(t_latencies), 2)
        }

    # Summary Metrics Payload
    metrics_payload = {
        "metadata": {
            "total_questions": total_q,
            "total_temples": len(temples_list),
            "answerable_questions": len(ans_q),
            "unanswerable_questions": len(unans_q),
            "evaluation_duration_seconds": round(total_eval_time, 2)
        },
        "retrieval": {
            "qdrant": {
                "top1_pct": round(q_top1, 2),
                "top3_pct": round(q_top3, 2),
                "top5_pct": round(q_top5, 2),
                "source_hit_pct": round(q_src_hit, 2)
            },
            "bm25": {
                "top1_pct": round(bm_top1, 2),
                "top3_pct": round(bm_top3, 2),
                "top5_pct": round(bm_top5, 2),
                "source_hit_pct": round(bm_src_hit, 2)
            },
            "hybrid": {
                "top1_pct": round(hy_top1, 2),
                "top3_pct": round(hy_top3, 2),
                "top5_pct": round(hy_top5, 2),
                "source_hit_pct": round(hy_src_hit, 2),
                "rerank_improvements": rerank_improvements
            }
        },
        "temple_isolation": {
            "isolation_rate_pct": round(isolation_rate, 2),
            "top1_contamination_count": top1_contams,
            "top3_contamination_count": top3_contams,
            "top5_contamination_count": top5_contams
        },
        "answer_quality": {
            "accuracy_pct": round(accuracy_rate, 2),
            "partial_pct": round(partial_rate, 2),
            "incorrect_pct": round(incorrect_rate, 2),
            "hallucination_pct": round(hallucination_rate, 2),
            "groundedness_pct": round(groundedness_rate, 2),
            "unanswerable_handling_pct": round(unans_accuracy, 2)
        },
        "latency": latency_metrics,
        "per_temple": per_temple_metrics,
        "failures": failures
    }

    # -----------------------------------------------------------------
    # SAVE ALL OUTPUT ARTIFACTS
    # -----------------------------------------------------------------
    with open(eval_dir / "evaluation_results.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    with open(eval_dir / "retrieval_results.json", "w", encoding="utf-8") as f:
        json.dump(retrieval_records, f, indent=2, ensure_ascii=False)

    with open(eval_dir / "contamination_results.json", "w", encoding="utf-8") as f:
        json.dump(contamination_records, f, indent=2, ensure_ascii=False)

    with open(eval_dir / "answer_results.json", "w", encoding="utf-8") as f:
        json.dump(answer_records, f, indent=2, ensure_ascii=False)

    with open(eval_dir / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics_payload, f, indent=2, ensure_ascii=False)

    # Markdown Report
    report_md = f"""# PilgrimAI Comprehensive RAG Evaluation Report

**Evaluation Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}  
**Total Questions Evaluated**: {total_q}  
**Total Temples Evaluated**: {len(temples_list)}  
**Evaluation Duration**: {total_eval_time:.2f}s  
**Model Config**: Ollama `qwen2.5:1.5b` (Local @ `http://localhost:11434`)  
**Storage**: `D:\\PiligrimAI -c\\qdrant_db` & `D:\\PiligrimAI -c\\bm25_index`

---

## 1. Executive Summary & Threshold Classification

| Evaluation Metric | Measured Value | Standard Threshold | Status |
|---|---|---|---|
| **Temple Isolation Rate** | **{isolation_rate:.2f}%** | ≥ 99.0% | {'PASS' if isolation_rate >= 99.0 else 'WARNING'} |
| **Hybrid Top-5 Retrieval** | **{hy_top5:.2f}%** | ≥ 90.0% | {'PASS' if hy_top5 >= 90.0 else 'WARNING'} |
| **Answer Accuracy** | **{accuracy_rate:.2f}%** | ≥ 85.0% | {'PASS' if accuracy_rate >= 85.0 else 'WARNING'} |
| **Groundedness Rate** | **{groundedness_rate:.2f}%** | ≥ 90.0% | {'PASS' if groundedness_rate >= 90.0 else 'WARNING'} |
| **Negative Query Handling** | **{unans_accuracy:.2f}%** | ≥ 90.0% | {'PASS' if unans_accuracy >= 90.0 else 'WARNING'} |

---

## 2. Retrieval Performance Comparison

| Retriever Stage | Top-1 Accuracy | Top-3 Accuracy | Top-5 Accuracy | Source Hit Rate |
|---|---|---|---|---|
| **Qdrant (Dense)** | {q_top1:.2f}% | {q_top3:.2f}% | {q_top5:.2f}% | {q_src_hit:.2f}% |
| **BM25 (Sparse)** | {bm_top1:.2f}% | {bm_top3:.2f}% | {bm_top5:.2f}% | {bm_src_hit:.2f}% |
| **Hybrid + Reranker** | **{hy_top1:.2f}%** | **{hy_top3:.2f}%** | **{hy_top5:.2f}%** | **{hy_src_hit:.2f}%** |

---

## 3. Cross-Temple Contamination & Isolation

- **Overall Isolation Percentage**: **{isolation_rate:.2f}%**
- **Top-1 Contamination Count**: {top1_contams} / {len(ans_q)}
- **Top-3 Contamination Count**: {top3_contams} / {len(ans_q)}
- **Top-5 Contamination Count**: {top5_contams} / {len(ans_q)}

---

## 4. Answer Quality & Generation

- **Correct Answers**: {correct_count} ({accuracy_rate:.2f}%)
- **Partially Correct Answers**: {partial_count} ({partial_rate:.2f}%)
- **Incorrect / Refused**: {incorrect_count} ({incorrect_rate:.2f}%)
- **Hallucinations Detected**: {hallucinated_count} ({hallucination_rate:.2f}%)
- **Unanswerable Questions Refused Correctly**: {unans_handled} / {len(unans_q)} ({unans_accuracy:.2f}%)

---

## 5. Latency Profile

| Stage | Average Latency | Median Latency | P95 Latency |
|---|---|---|---|
| **Qdrant Dense Search** | {latency_metrics['qdrant_avg_ms']} ms | {latency_metrics['qdrant_median_ms']} ms | {latency_metrics['qdrant_p95_ms']} ms |
| **BM25 Sparse Search** | {latency_metrics['bm25_avg_ms']} ms | {latency_metrics['bm25_median_ms']} ms | {latency_metrics['bm25_p95_ms']} ms |
| **Cross-Encoder Reranker** | {latency_metrics['rerank_avg_ms']} ms | {latency_metrics['rerank_median_ms']} ms | {latency_metrics['rerank_p95_ms']} ms |
| **Total End-to-End Pipeline** | **{latency_metrics['total_avg_ms']} ms** | **{latency_metrics['total_median_ms']} ms** | **{latency_metrics['total_p95_ms']} ms** |

---

## 6. Per-Temple Detailed Breakdown

| Temple Name | Questions | Hybrid Top-5 | Answer Accuracy | Temple Isolation | Avg Latency |
|---|---|---|---|---|---|
"""
    for tid, pdata in per_temple_metrics.items():
        report_md += f"| **{pdata['temple_name']}** | {pdata['total_questions']} | {pdata['hybrid_top5_pct']}% | {pdata['answer_accuracy_pct']}% | {pdata['isolation_pct']}% | {pdata['avg_latency_ms']} ms |\n"

    report_md += f"""
---

## 7. Failure Analysis

- **Total Execution Exceptions**: {len(failures)}
"""
    if failures:
        for fail in failures:
            report_md += f"- `{fail['id']}` ({fail['temple_id']}): {fail['error']}\n"
    else:
        report_md += "*(Zero runtime crashes or fatal pipeline errors encountered)*\n"

    with open(eval_dir / "evaluation_report.md", "w", encoding="utf-8") as f:
        f.write(report_md)

    print(f"\n[OK] All evaluation files successfully generated in: {eval_dir}")
    return metrics_payload

if __name__ == "__main__":
    run_full_evaluation()
