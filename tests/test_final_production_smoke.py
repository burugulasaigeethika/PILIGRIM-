import pytest
import urllib.request
import json
import sys
from pathlib import Path

# Setup paths
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

def is_live_server_running():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False

def http_get(path: str):
    if is_live_server_running():
        with urllib.request.urlopen(f"http://127.0.0.1:8000{path}", timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8")
    else:
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        resp = client.get(path)
        return resp.status_code, resp.text

def http_post_chat(question: str):
    if is_live_server_running():
        payload = json.dumps({"question": question}).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:8000/chat",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    else:
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        resp = client.post("/chat", json={"question": question})
        return resp.status_code, resp.json()

def test_final_health_endpoint():
    """Verify GET /health returns 200 OK."""
    status, body = http_get("/health")
    assert status == 200
    data = json.loads(body)
    assert data.get("status") == "ok"

def test_final_root_ui_endpoint():
    """Verify GET / serves HTML frontend."""
    status, body = http_get("/")
    assert status == 200
    assert "PilgrimAI" in body or "<!DOCTYPE html>" in body

def test_final_docs_endpoint():
    """Verify GET /docs serves Swagger UI."""
    status, body = http_get("/docs")
    assert status == 200
    assert "swagger" in body.lower() or "fastapi" in body.lower()

def test_final_chat_schema_and_targeted_query():
    """Verify POST /chat response schema on targeted query."""
    status, data = http_post_chat("What are the temple timings at Bhadrachalam?")
    assert status == 200
    assert "question" in data
    assert "answer" in data
    assert "retrieved_chunks" in data
    assert "sources" in data
    assert "confidence_score" in data
    assert "4:30" in data["answer"] or "timings" in data["answer"].lower()

def test_final_complete_category_query():
    """Verify complete list category retrieval contract."""
    status, data = http_post_chat("What are all the sevas in Dharmapuri?")
    assert status == 200
    assert "Abhishekam" in data["answer"]

def test_final_cross_temple_aggregation_query():
    """Verify 20-temple dynamic aggregation contract."""
    status, data = http_post_chat("Which temples have a river bank?")
    assert status == 200
    assert "11 temples" in data["answer"]

def test_final_grounded_refusal_query():
    """Verify non-existent entity grounded refusal contract."""
    status, data = http_post_chat("Does Dharmapuri have a helicopter launch pad?")
    assert status == 200
    ans_lower = data["answer"].lower()
    assert "could not find" in ans_lower or "not available" in ans_lower
