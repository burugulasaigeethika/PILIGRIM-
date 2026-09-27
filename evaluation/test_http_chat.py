import urllib.request
import json
import time
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def test_real_http_chat():
    print("Testing real FastAPI HTTP endpoints on http://127.0.0.1:8000 ...")
    
    # 1. Health check
    with urllib.request.urlopen("http://127.0.0.1:8000/health") as r:
        print("Health Check:", r.status, r.read().decode())

    # 2. Query matrix
    queries = [
        "What are the temple timings at Bhadrachalam?",
        "What is the price of Abhishekam in Dharmapuri?",
        "What are all the sevas in Dharmapuri?",
        "Which temples have a river bank?",
        "Which temples don't have wheelchair facilities?",
        "What accommodation and restaurants are available near Dharmapuri?",
        "Tell me everything about Dharmapuri Temple.",
        "Does Dharmapuri have a helicopter launch pad?"
    ]

    for idx, q in enumerate(queries, 1):
        payload = json.dumps({"question": q}).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:8000/chat",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        t0 = time.perf_counter()
        with urllib.request.urlopen(req) as resp:
            elapsed = (time.perf_counter() - t0) * 1000.0
            data = json.loads(resp.read().decode("utf-8"))
            print(f"\n[{idx}/8] Query: '{q}'")
            print(f"  HTTP Status: {resp.status} | Chunks: {data.get('retrieved_chunks')} | Sources: {len(data.get('sources', []))} | Latency: {elapsed:.1f}ms")
            ans_clean = data.get("answer", "").replace("\n", " ")
            print(f"  Answer: {ans_clean[:180]}...")

if __name__ == "__main__":
    test_real_http_chat()
