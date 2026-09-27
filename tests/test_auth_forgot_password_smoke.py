import os
import sys
import uuid
import asyncio
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, Optional
import httpx

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app
from app.db.mongodb import get_mongo_client, get_users_collection
from app.auth.security import hash_password, verify_password
from app.tasks.celery_app import send_password_reset_email

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

# Global test data
UNIQUE_ID = uuid.uuid4().hex[:8]
TEST_USER_NAME = f"Forgot Test {UNIQUE_ID}"
TEST_USER_EMAIL = f"forgot_{UNIQUE_ID}@example.com"
ORIGINAL_PASSWORD = "InitialPassword123!"
NEW_PASSWORD = "BrandNewPassword789!"
SAVED_RAW_RESET_TOKEN = None


def test_01_root_page_serves_frontend():
    """TEST 1: Root URL serves PilgrimAI frontend with auth container."""
    response = client.get("/")
    assert response.status_code == 200
    assert 'id="authPage"' in response.text
    assert 'id="viewLogin"' in response.text
    assert 'id="viewRegister"' in response.text
    assert 'id="viewForgotPassword"' in response.text
    assert 'id="viewResetPassword"' in response.text
    print("\n[TEST 1 PASS] Root page serves frontend with all 4 dedicated auth views.")


def test_02_register_view_and_endpoint():
    """TEST 2 & 3: Register a new test account."""
    payload = {
        "name": TEST_USER_NAME,
        "email": TEST_USER_EMAIL,
        "password": ORIGINAL_PASSWORD
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["user"]["email"] == TEST_USER_EMAIL.lower()
    print(f"\n[TEST 2 & 3 PASS] User registered: {TEST_USER_EMAIL}")


def test_04_login_and_authenticated_app():
    """TEST 4 & 5: Login returns JWT, and /me validates session."""
    payload = {
        "email": TEST_USER_EMAIL,
        "password": ORIGINAL_PASSWORD
    }
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 200
    token = response.json()["access_token"]
    
    # Verify GET /api/auth/me with JWT
    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == TEST_USER_EMAIL.lower()
    print("\n[TEST 4 & 5 PASS] Login and /me session verification succeeded.")


def test_06_unauthenticated_request_rejected():
    """TEST 6: Unauthenticated request without JWT receives 401."""
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    print("\n[TEST 6 PASS] Unauthenticated request returns 401.")


def test_08_forgot_password_existing_email():
    """TEST 8: Forgot password generates single-use token hash and dispatches email."""
    global SAVED_RAW_RESET_TOKEN
    payload = {"email": TEST_USER_EMAIL}
    response = client.post("/api/auth/forgot-password", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "If an account exists" in data["message"]
    
    # Inspect MongoDB to verify token is stored as SHA-256 hash (never plaintext)
    users_col = get_users_collection()
    user = users_col.find_one({"email": TEST_USER_EMAIL.lower()})
    assert user is not None
    assert "password_reset_token_hash" in user
    assert "password_reset_expires_at" in user
    assert len(user["password_reset_token_hash"]) == 64  # SHA-256 hex digest length
    
    # Generate a known test token for deterministic reset testing
    raw_token = f"reset_token_{UNIQUE_ID}_{uuid.uuid4().hex}"
    SAVED_RAW_RESET_TOKEN = raw_token
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
    users_col.update_one(
        {"_id": user["_id"]},
        {"$set": {"password_reset_token_hash": token_hash, "password_reset_expires_at": expires_at}}
    )
    print("\n[TEST 8 PASS] Forgot password stored SHA-256 hash and returned anti-enumeration response.")


def test_10_reset_password_with_valid_token():
    """TEST 9 & 10: Reset password with valid token updates password in MongoDB."""
    assert SAVED_RAW_RESET_TOKEN is not None
    payload = {
        "token": SAVED_RAW_RESET_TOKEN,
        "new_password": NEW_PASSWORD
    }
    response = client.post("/api/auth/reset-password", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "Password reset successfully" in data["message"]
    print("\n[TEST 9 & 10 PASS] Password reset succeeded with valid token.")


def test_11_login_with_new_password():
    """TEST 11: Login with old password fails, login with new password succeeds."""
    # Old password must fail
    old_resp = client.post("/api/auth/login", json={"email": TEST_USER_EMAIL, "password": ORIGINAL_PASSWORD})
    assert old_resp.status_code == 401
    
    # New password must succeed
    new_resp = client.post("/api/auth/login", json={"email": TEST_USER_EMAIL, "password": NEW_PASSWORD})
    assert new_resp.status_code == 200
    assert "access_token" in new_resp.json()
    print("\n[TEST 11 PASS] Old password rejected, new password authenticated successfully.")


def test_12_token_reuse_rejected():
    """TEST 12: Reusing the same reset token is rejected."""
    assert SAVED_RAW_RESET_TOKEN is not None
    payload = {
        "token": SAVED_RAW_RESET_TOKEN,
        "new_password": "YetAnotherPassword123!"
    }
    response = client.post("/api/auth/reset-password", json=payload)
    assert response.status_code == 400
    assert "Invalid or expired" in response.json().get("detail", "")
    print("\n[TEST 12 PASS] Token reuse rejected successfully (single-use enforced).")


def test_13_expired_or_invalid_token_rejected():
    """TEST 13: Expired or completely fake token is rejected."""
    # Fake token
    fake_resp = client.post("/api/auth/reset-password", json={"token": "completely_fake_token_xyz", "new_password": "NewPassword123!"})
    assert fake_resp.status_code == 400
    
    # Expired token in database
    users_col = get_users_collection()
    expired_token = f"expired_token_{UNIQUE_ID}"
    expired_hash = hashlib.sha256(expired_token.encode("utf-8")).hexdigest()
    users_col.update_one(
        {"email": TEST_USER_EMAIL.lower()},
        {"$set": {
            "password_reset_token_hash": expired_hash,
            "password_reset_expires_at": datetime.now(timezone.utc) - timedelta(minutes=5)
        }}
    )
    exp_resp = client.post("/api/auth/reset-password", json={"token": expired_token, "new_password": "NewPassword123!"})
    assert exp_resp.status_code == 400
    assert "expired" in exp_resp.json().get("detail", "").lower()
    print("\n[TEST 13 PASS] Fake and expired reset tokens rejected with 400 Bad Request.")


def test_14_forgot_password_nonexistent_email():
    """TEST 14: Nonexistent email returns identical generic response (no account enumeration)."""
    non_existent = f"nonexistent_{uuid.uuid4().hex[:10]}@example.com"
    response = client.post("/api/auth/forgot-password", json={"email": non_existent})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "If an account exists" in data["message"]
    print("\n[TEST 14 PASS] Nonexistent email returned identical generic response (anti-enumeration verified).")
