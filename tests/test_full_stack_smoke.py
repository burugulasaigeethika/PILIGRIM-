import pytest
import sys
import urllib.request
import json
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

def post_chat(question: str):
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

def test_smoke_health_check():
    """Verify backend health check endpoint returns 200 OK."""
    if is_live_server_running():
        with urllib.request.urlopen("http://127.0.0.1:8000/health") as r:
            assert r.status == 200
            data = json.loads(r.read().decode("utf-8"))
            assert data == {"status": "ok"}
    else:
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

def test_smoke_targeted_query():
    """Verify targeted factual chat contract."""
    status, data = post_chat("What are the temple timings at Bhadrachalam?")
    assert status == 200
    assert "answer" in data
    assert "4:30" in data["answer"] or "timings" in data["answer"].lower()
    assert data.get("retrieved_chunks", 0) > 0

def test_smoke_complete_list_query():
    """Verify complete list category retrieval contract."""
    status, data = post_chat("What are all the sevas in Dharmapuri?")
    assert status == 200
    assert "Abhishekam" in data["answer"]

def test_smoke_cross_temple_aggregation():
    """Verify cross-temple aggregation contract."""
    status, data = post_chat("Which temples have a river bank?")
    assert status == 200
    assert "11 temples" in data["answer"]

def test_smoke_grounded_refusal():
    """Verify non-existent entity grounded refusal contract."""
    status, data = post_chat("Does Dharmapuri have a helicopter launch pad?")
    assert status == 200
    assert "could not find" in data["answer"].lower() or "not available" in data["answer"].lower()
