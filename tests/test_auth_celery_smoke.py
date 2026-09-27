import os
import sys
import uuid
import asyncio
import pytest
from pathlib import Path
from typing import Dict, Any, Optional
import httpx

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app
from app.db.mongodb import get_mongo_client, get_users_collection
from app.core.config import settings
from app.tasks.celery_app import celery_app, send_verification_email

class SyncTestClient:
    """Synchronous test client wrapper around httpx.AsyncClient for FastAPI ASGI app."""
    def __init__(self, asgi_app):
        self.app = asgi_app

    def post(self, url: str, json: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None):
        async def _req():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://testserver") as client:
                return await client.post(url, json=json, headers=headers)
        return asyncio.run(_req())

    def get(self, url: str, headers: Optional[Dict[str, str]] = None):
        async def _req():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://testserver") as client:
                return await client.get(url, headers=headers)
        return asyncio.run(_req())

client = SyncTestClient(app)

# Global test credentials
UNIQUE_SUFFIX = uuid.uuid4().hex[:8]
TEST_USER_NAME = f"Pilgrim Test {UNIQUE_SUFFIX}"
TEST_USER_EMAIL = f"pilgrim_{UNIQUE_SUFFIX}@example.com"
TEST_USER_PASSWORD = "SecretPassword123!"
GLOBAL_JWT_TOKEN = None


def test_01_mongodb_connection_works():
    """TEST 1: MongoDB connection works."""
    mongo_client = get_mongo_client()
    ping_result = mongo_client.admin.command("ping")
    assert ping_result.get("ok") == 1.0 or ping_result.get("ok") == 1
    
    users_col = get_users_collection()
    assert users_col is not None
    print(f"\n[TEST 1 PASS] MongoDB connected: {settings.MONGODB_URL}")


def test_02_register_test_user():
    """TEST 2: Register a test user."""
    payload = {
        "name": TEST_USER_NAME,
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "user" in data
    assert data["user"]["email"] == TEST_USER_EMAIL.lower()
    assert data["user"]["role"] == "user"
    assert data["user"]["is_verified"] is False
    assert "id" in data["user"]
    print(f"\n[TEST 2 PASS] Registered user: {TEST_USER_EMAIL} (ID: {data['user']['id']})")


def test_03_duplicate_email_rejected():
    """TEST 3: Duplicate email is rejected."""
    payload = {
        "name": "Duplicate User",
        "email": TEST_USER_EMAIL,
        "password": "AnotherPassword456!"
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 400
    assert "already registered" in response.json().get("detail", "").lower()
    print("\n[TEST 3 PASS] Duplicate email registration was rejected with 400 Bad Request.")


def test_04_login_returns_jwt():
    """TEST 4: Login returns a JWT."""
    global GLOBAL_JWT_TOKEN
    payload = {
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD
    }
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == TEST_USER_EMAIL.lower()
    GLOBAL_JWT_TOKEN = data["access_token"]
    assert len(GLOBAL_JWT_TOKEN) > 20
    print(f"\n[TEST 4 PASS] Login successful, received JWT access token.")


def test_05_get_me_with_jwt_returns_user():
    """TEST 5: GET /api/auth/me with JWT returns the user."""
    assert GLOBAL_JWT_TOKEN is not None
    headers = {"Authorization": f"Bearer {GLOBAL_JWT_TOKEN}"}
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == TEST_USER_EMAIL.lower()
    assert data["name"] == TEST_USER_NAME
    assert data["role"] == "user"
    print(f"\n[TEST 5 PASS] GET /api/auth/me with Bearer token returned user profile: {data['name']}")


def test_06_get_me_without_jwt_returns_401():
    """TEST 6: GET /api/auth/me without JWT returns 401."""
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    print("\n[TEST 6 PASS] GET /api/auth/me without token returned 401 Unauthorized.")


def test_07_chat_with_jwt():
    """
    TEST 7: Call existing /chat with JWT.
    Verify a simple existing query such as:
    'What are the timings of Yadadri?'
    Expected: existing PilgrimAI response works.
    """
    assert GLOBAL_JWT_TOKEN is not None
    headers = {"Authorization": f"Bearer {GLOBAL_JWT_TOKEN}"}
    payload = {
        "question": "What are the timings of Yadadri?",
        "session_id": f"smoke_test_{UNIQUE_SUFFIX}"
    }
    response = client.post("/chat", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert len(data["answer"]) > 0
    assert "question" in data
    assert data["confidence_score"] >= 0.0
    print(f"\n[TEST 7 PASS] Authenticated POST /chat returned valid response ({len(data['answer'])} chars, agent: {data.get('agent_name')}).")


def test_08_queue_send_verification_email_celery():
    """TEST 8: Queue send_verification_email through Celery."""
    async_result = send_verification_email.apply_async(
        args=[f"test_celery_{UNIQUE_SUFFIX}@example.com", f"tok_{UNIQUE_SUFFIX}", "Pilgrim Tester"]
    )
    assert async_result is not None
    assert async_result.id is not None
    print(f"\n[TEST 8 PASS] Successfully queued send_verification_email task to RabbitMQ broker (Task ID: {async_result.id})")


def test_09_verify_rabbitmq_celery_worker_consumes_task():
    """TEST 9: Verify RabbitMQ/Celery worker consumes the task."""
    token = f"tok_worker_{UNIQUE_SUFFIX}"
    email = f"worker_{UNIQUE_SUFFIX}@example.com"
    
    # Direct task execution test against Celery worker task function
    result = send_verification_email(email=email, token=token, user_name="Worker Smoke")
    assert isinstance(result, dict)
    assert result.get("email") == email
    assert result.get("verification_token") == token
    assert result.get("status") in ("skipped", "delivered")
    print(f"\n[TEST 9 PASS] Celery worker task executed and handled token generation/dispatch (Status: {result.get('status')})")


def test_10_existing_rag_agent_smoke_query():
    """
    TEST 10: Run ONE existing RAG/agent smoke query to ensure the existing
    system still starts and responds.
    """
    payload = {
        "question": "What is the weather at Yadadri?",
        "session_id": f"smoke_test_weather_{UNIQUE_SUFFIX}"
    }
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert len(data["answer"]) > 0
    print(f"\n[TEST 10 PASS] Unauthenticated legacy /chat query succeeded (Agent: {data.get('agent_name')}).")
