"""
PilgrimAI - Live API Latency & Acceptance Verification (Phase P)
Tests all 10 required verification queries against the running FastAPI service.
"""

import sys
import time
import requests
import json

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_URL = "http://127.0.0.1:8000"

QUERIES = [
    "Plan a 2 day itinerary to Yadadri with a budget of ₹5000",
    "Plan a 2 day trip to Yadadri under ₹5000 including accommodation",
    "Which temples currently have temperatures above 27°C?",
    "What are the current temperatures at Yadadri, Basara, Bhadrachalam and Vemulavada?",
    "Recommend a temple where the temperature is around 25–30°C",
    "Compare Yadadri and Basara accommodation.",
    "Which temples are on a river bank?",
    "What are Yadadri temple timings?",
    "How far is Hyderabad from Yadadri?",
    "What emergency services are available at Yadadri?"
]

def run_verification():
    print(f"Connecting to {BASE_URL}...")
    try:
        health = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"Health check: {health.status_code} - {health.json()}\n")
    except Exception as e:
        print(f"Could not connect to {BASE_URL}: {e}")
        return

    # Profile timing query latency breakdown first
    timing_query = "What are Yadadri temple timings?"
    print(f"=== Profiling Query: '{timing_query}' ===")
    t0 = time.perf_counter()
    resp = requests.post(f"{BASE_URL}/chat", json={"question": timing_query}, timeout=120)
    total_elapsed_ms = (time.perf_counter() - t0) * 1000.0
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"Status: 200 OK")
        print(f"Agent Name: {data.get('agent_name')}")
        print(f"Total API Latency: {total_elapsed_ms:.2f} ms ({total_elapsed_ms/1000:.2f}s)")
        print(f"Coordinator Internal Latency: {data.get('latency_ms')} ms")
        print(f"Retrieved Chunks: {data.get('retrieved_chunks')}")
        print(f"Confidence: {data.get('confidence_score')}")
        print(f"Answer:\n{data.get('answer')[:200]}...\n")
    else:
        print(f"Error {resp.status_code}: {resp.text}\n")

    # Run all 10 verification queries
    print("============================================================")
    print("RUNNING ALL 10 FINAL VERIFICATION QUERIES")
    print("============================================================")
    
    results = []
    for i, q in enumerate(QUERIES, 1):
        print(f"\n--- Query {i}: '{q}' ---")
        t_start = time.perf_counter()
        try:
            r = requests.post(f"{BASE_URL}/chat", json={"question": q}, timeout=120)
            elapsed_ms = (time.perf_counter() - t_start) * 1000.0
            if r.status_code == 200:
                res_data = r.json()
                agent = res_data.get("agent_name")
                ans = res_data.get("answer", "")
                sources = res_data.get("sources", [])
                meta = res_data.get("metadata", {})
                print(f"  Selected Agent/Pipeline : {agent}")
                print(f"  Latency                 : {elapsed_ms:.2f} ms")
                print(f"  Sources Count           : {len(sources)}")
                print(f"  Answer Preview:\n{ans[:250]}...")
                results.append({
                    "query_id": i,
                    "query": q,
                    "agent": agent,
                    "latency_ms": elapsed_ms,
                    "sources": sources,
                    "answer": ans,
                    "metadata": meta,
                    "success": True
                })
            else:
                print(f"  FAILED: HTTP {r.status_code} - {r.text}")
                results.append({
                    "query_id": i,
                    "query": q,
                    "success": False,
                    "error": r.text
                })
        except Exception as e:
            print(f"  EXCEPTION: {e}")
            results.append({
                "query_id": i,
                "query": q,
                "success": False,
                "error": str(e)
            })

    with open("final_verification_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\n[OK] All results saved to final_verification_results.json")

if __name__ == "__main__":
    run_verification()
