import sys
import json
import time
from pathlib import Path

# Setup paths
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.rag.chat import PilgrimRAGService

TEST_CASES = [
    {
        "id": "BHADRACHALAM_TIMINGS_TARGETED",
        "query": "What are the temple timings at Bhadrachalam?",
        "expected_temples": ["Badrachalam"],
        "expected_categories": ["timings"],
        "unrelated_forbidden_terms": ["Dharmapuri", "Basara", "₹500", "Abhishekam", "restaurants", "festivals", "cottages", "Papikondalu"]
    },
    {
        "id": "DHARMAPURI_ABHISHEKAM_PRICE_TARGETED",
        "query": "What is the price of Abhishekam in Dharmapuri?",
        "expected_temples": ["Dharmapuri"],
        "expected_categories": ["sevas"],
        "unrelated_forbidden_terms": ["Bhadrachalam", "Basara", "hotels", "restaurants", "timings", "dress code"]
    },
    {
        "id": "DHARMAPURI_ALL_SEVAS_COMPLETE",
        "query": "What are all the sevas in Dharmapuri?",
        "expected_temples": ["Dharmapuri"],
        "expected_categories": ["sevas"],
        "unrelated_forbidden_terms": ["Bhadrachalam", "Basara"]
    },
    {
        "id": "BASARA_ALL_FESTIVALS_COMPLETE",
        "query": "List all festivals at Basara.",
        "expected_temples": ["Basara"],
        "expected_categories": ["festivals"],
        "unrelated_forbidden_terms": ["Yadadri", "Dharmapuri"]
    },
    {
        "id": "RIVER_BANK_AGGREGATION",
        "query": "List all temples that have a river bank.",
        "expected_temples": ["*"],
        "expected_categories": ["river_bank"],
        "unrelated_forbidden_terms": []
    },
    {
        "id": "WHEELCHAIR_NEGATIVE_AGGREGATION",
        "query": "List all temples that don't have wheelchair facilities.",
        "expected_temples": ["*"],
        "expected_categories": ["wheelchair"],
        "unrelated_forbidden_terms": []
    },
    {
        "id": "MULTI_CATEGORY_ACCOMMODATION_RESTAURANTS",
        "query": "What accommodation and restaurants are available near Dharmapuri?",
        "expected_temples": ["Dharmapuri"],
        "expected_categories": ["accommodation", "restaurants"],
        "unrelated_forbidden_terms": ["Bhadrachalam", "Basara"]
    },
    {
        "id": "YADADRI_HISTORY_TARGETED",
        "query": "Tell me the history of Yadadri.",
        "expected_temples": ["Yadadri"],
        "expected_categories": ["temple"],
        "unrelated_forbidden_terms": ["Dharmapuri", "Basara"]
    },
    {
        "id": "DHARMAPURI_BROAD_OVERVIEW",
        "query": "Tell me everything about Dharmapuri Temple.",
        "expected_temples": ["Dharmapuri"],
        "expected_categories": ["*"],
        "unrelated_forbidden_terms": ["Bhadrachalam"]
    },
    {
        "id": "DHARMAPURI_WHEELCHAIR_TARGETED",
        "query": "Does Dharmapuri have wheelchair facilities?",
        "expected_temples": ["Dharmapuri"],
        "expected_categories": ["wheelchair"],
        "unrelated_forbidden_terms": ["Bhadrachalam"]
    },
    {
        "id": "HELIPAD_GROUNDED_REFUSAL",
        "query": "Does Dharmapuri have a helicopter launch pad?",
        "expected_temples": ["Dharmapuri"],
        "expected_categories": ["*"],
        "unrelated_forbidden_terms": ["The helicopter launch pad is available", "Helipad fee"]
    }
]

def run_evaluation():
    print("==================================================")
    print("Starting Phase 7 Answer Grounding & Scope Evaluation")
    print("==================================================")

    rag = PilgrimRAGService()
    results = []

    unrelated_violations_count = 0

    for tc in TEST_CASES:
        q_id = tc["id"]
        query = tc["query"]
        print(f"\nEvaluating [{q_id}] - '{query}'")

        start = time.perf_counter()
        res = rag.answer(query)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        ans = res.get("answer", "")
        plan = res.get("plan")
        scope = res.get("scope")

        # Check for forbidden unrequested terms
        violations = []
        for term in tc["unrelated_forbidden_terms"]:
            if term.lower() in ans.lower():
                violations.append(f"Forbidden unrequested term found: '{term}'")

        has_scope_violation = len(violations) > 0
        if has_scope_violation:
            unrelated_violations_count += 1

        eval_entry = {
            "id": q_id,
            "query": query,
            "retrieval_mode": plan.retrieval_mode if plan else "unknown",
            "scope_temples": scope.temples if scope else [],
            "scope_categories": scope.categories if scope else [],
            "answer_preview": ans[:200] + ("..." if len(ans) > 200 else ""),
            "answer_full": ans,
            "latency_ms": round(elapsed_ms, 2),
            "unrelated_terms_detected": violations,
            "passed": not has_scope_violation
        }
        results.append(eval_entry)

        status_str = "[PASSED]" if not has_scope_violation else "[FAILED]"
        print(f"  {status_str} Mode: {plan.retrieval_mode} | Latency: {elapsed_ms:.1f}ms | Violations: {len(violations)}")
        if violations:
            print(f"    Violations: {violations}")

    out_dir = Path(__file__).resolve().parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save JSON results
    with open(out_dir / "phase7_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # Generate Markdown report
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    unrelated_info_rate = (unrelated_violations_count / total_count) * 100.0

    md = f"""# Phase 7 Answer Grounding & Scope Control Evaluation Report

## 1. Executive Summary
- **Evaluation Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}
- **Total Test Queries Evaluated**: {total_count}
- **Passed Scope Tests**: {passed_count} / {total_count} ({passed_count/total_count*100:.1f}%)
- **Unrelated Information Rate for Targeted Queries**: **{unrelated_info_rate:.1f}%** (Target: 0.0%)
- **Local Environment**: 100% Local / Offline (Qwen 2.5:1.5B via Ollama)

---

## 2. Benchmark Query Scope & Grounding Results

| Test ID | Query | Retrieval Mode | Scope Temples | Scope Categories | Unrelated Info Violations | Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
"""
    for r in results:
        status_badge = "✅ PASSED" if r["passed"] else "❌ FAILED"
        md += f"| `{r['id']}` | *{r['query']}* | `{r['retrieval_mode']}` | `{r['scope_temples']}` | `{r['scope_categories']}` | {len(r['unrelated_terms_detected'])} | {status_badge} |\n"

    md += """
---

## 3. Detailed Query Responses

"""
    for r in results:
        md += f"""### `{r['id']}`
- **Query**: *"{r['query']}"*
- **Planned Mode**: `{r['retrieval_mode']}` | Scope Temples: `{r['scope_temples']}` | Categories: `{r['scope_categories']}`
- **Latency**: `{r['latency_ms']} ms`
- **Answer Output**:
> {r['answer_full']}

"""

    with open(out_dir / "PHASE7_ANSWER_GROUNDING_REPORT.md", "w", encoding="utf-8") as f:
        f.write(md)

    print(f"\n==================================================")
    print(f"Phase 7 Benchmark Complete! ({passed_count}/{total_count} Passed)")
    print(f"Unrelated Information Rate: {unrelated_info_rate:.1f}%")
    print(f"Reports saved to {out_dir}")
    print(f"==================================================")

if __name__ == "__main__":
    run_evaluation()
