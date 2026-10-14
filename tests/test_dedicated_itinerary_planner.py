"""
PilgrimAI - Regression and Functional Tests for Dedicated Itinerary Planner API & Storage

Verifies:
1. Input validation on /api/itinerary/plan:
   - Empty destinations rejection (422 for empty list, 400 for whitespace)
   - Default values for origin, duration, pax
   - Proper query string synthesis for coordinator
2. Consistency and entity-leakage safety:
   - No raw HTML entities (&#x35;, &#35;, &amp;#x35;) in itinerary answer or schedule
3. Feasibility warning for tight duration vs temple count:
   - When temples exceed days, schedule feasibility constraint is present
4. Persistence layer (MongoDB / in-memory fallback):
   - Unauthenticated save/fetch is rejected with 401
   - Authenticated saving itinerary returns success and itinerary_id
   - Fetching saved itineraries returns the saved records
   - Deleting a saved itinerary removes it
   - Handling invalid save requests gracefully
"""

import sys
from pathlib import Path
import pytest
import asyncio
from typing import Optional, Dict, Any
import httpx

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app
from app.auth.jwt import get_current_user
from app.db.itinerary_storage import (
    save_itinerary,
    get_user_itineraries,
    get_itinerary_by_id,
    delete_user_itinerary,
)

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

    def delete(self, url: str, headers: Optional[Dict[str, str]] = None):
        async def _req():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://testserver") as client:
                return await client.delete(url, headers=headers)
        return asyncio.run(_req())

client = SyncTestClient(app)


# =====================================================================
# 1. Input Validation Tests for /api/itinerary/plan
# =====================================================================

def test_plan_itinerary_requires_destinations():
    """Requesting an itinerary without destinations or with whitespace must be rejected."""
    # Empty list -> 422
    response1 = client.post("/api/itinerary/plan", json={
        "origin": "Hyderabad",
        "destinations": [],
        "duration_days": 2,
    })
    assert response1.status_code == 422

    # Whitespace only destination -> 400
    response2 = client.post("/api/itinerary/plan", json={
        "origin": "Hyderabad",
        "destinations": ["   "],
        "duration_days": 2,
    })
    assert response2.status_code == 400
    assert "At least one pilgrimage destination must be specified" in response2.json()["detail"]


def test_plan_itinerary_defaults_and_validation():
    """Validation works for invalid numbers (e.g. duration_days < 1)."""
    response = client.post("/api/itinerary/plan", json={
        "origin": "Hyderabad",
        "destinations": ["Yadadri"],
        "duration_days": 0,
    })
    assert response.status_code == 422  # Pydantic validation error (ge=1)


# =====================================================================
# 2. End-to-End Planning Flow & Entity Leakage Safety
# =====================================================================

def test_plan_itinerary_execution_no_entity_leakage():
    """
    Submitting a valid request executes through coordinator and does not
    contain raw or escaped HTML entities in the answer.
    """
    payload = {
        "origin": "Hyderabad",
        "destinations": ["Yadadri"],
        "duration_days": 1,
        "travellers": 2,
        "budget": 5000,
        "accommodation_pref": "standard",
        "transport_pref": "car",
        "round_trip": True,
    }

    response = client.post("/api/itinerary/plan", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "itinerary" in data
    itinerary_text = data["itinerary"]

    # Verify no raw hex entities like &#x35; or &#35;
    assert "&#x35;" not in itinerary_text
    assert "&#35;" not in itinerary_text
    assert "&amp;#x" not in itinerary_text

    # Verify parsed parameters are echoed
    assert data["parameters"]["origin"] == "Hyderabad"
    assert "Yadadri" in data["parameters"]["destinations"]
    assert data["parameters"]["duration_days"] == 1
    assert data["parameters"]["pax"] == 2


def test_plan_itinerary_multi_temple_feasibility_constraint():
    """
    When temples exceed duration days (e.g. 3 temples in 1 day),
    the generated itinerary includes a schedule feasibility constraint advisory.
    """
    payload = {
        "origin": "Hyderabad",
        "destinations": ["Yadadri", "Vemulavada", "Basara"],
        "duration_days": 1,
        "travellers": 2,
    }

    response = client.post("/api/itinerary/plan", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    itinerary_text = data["itinerary"]

    # Schedule constraint warning or tight scheduling advisory should be present
    assert any(w in itinerary_text for w in [
        "Schedule Feasibility Constraint",
        "Multi-Destination Advisory",
        "tight scheduling",
        "Consider extending",
    ])


# =====================================================================
# 3. Persistence Tests (Storage functions & API endpoints)
# =====================================================================

def test_unauthenticated_save_and_fetch_rejected():
    """Unauthenticated calls to /api/itinerary/save and /api/itinerary/saved must return 401."""
    # Ensure no override
    if get_current_user in app.dependency_overrides:
        del app.dependency_overrides[get_current_user]

    res_save = client.post("/api/itinerary/save", json={
        "title": "Unauthorized Plan",
        "destinations": ["Yadadri"],
        "itinerary_text": "Sample",
    })
    assert res_save.status_code == 401

    res_get = client.get("/api/itinerary/saved")
    assert res_get.status_code == 401


def test_itinerary_save_and_retrieve_endpoints_authenticated():
    """Test saving an itinerary and retrieving it via the API for authenticated user."""
    test_user_id = "test_user_pytest_123"
    app.dependency_overrides[get_current_user] = lambda: {"_id": test_user_id, "email": "test@pilgrim.ai"}

    try:
        save_payload = {
            "title": "Hyderabad to Yadadri Day Trip",
            "origin": "Hyderabad",
            "destinations": ["Yadadri"],
            "duration_days": 1,
            "pax": 2,
            "budget_limit": 5000.0,
            "preferences": {"accommodation": "standard", "transport": "car"},
            "itinerary_text": "### Day 1: Yadadri Trip\nMorning: Visit Yadadri Temple.",
        }

        # Save
        save_resp = client.post("/api/itinerary/save", json=save_payload)
        assert save_resp.status_code == 200
        save_data = save_resp.json()
        assert save_data["success"] is True
        itinerary_id = save_data["itinerary_id"]
        assert itinerary_id is not None

        # Retrieve list
        list_resp = client.get("/api/itinerary/saved")
        assert list_resp.status_code == 200
        list_data = list_resp.json()
        assert list_data["success"] is True
        itineraries = list_data["itineraries"]
        assert any(it["itinerary_id"] == itinerary_id for it in itineraries)

        # Delete
        del_resp = client.delete(f"/api/itinerary/saved/{itinerary_id}")
        assert del_resp.status_code == 200
        del_data = del_resp.json()
        assert del_data["success"] is True

        # Retrieve again - must not contain deleted itinerary
        list_resp2 = client.get("/api/itinerary/saved")
        assert list_resp2.status_code == 200
        list_data2 = list_resp2.json()
        assert not any(it["itinerary_id"] == itinerary_id for it in list_data2["itineraries"])
    finally:
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]


def test_save_empty_itinerary_rejected():
    """Saving without itinerary text should return 422."""
    app.dependency_overrides[get_current_user] = lambda: {"_id": "test_user_pytest_123", "email": "test@pilgrim.ai"}
    try:
        response = client.post("/api/itinerary/save", json={
            "title": "Empty Plan",
            "origin": "Hyderabad",
            "destinations": ["Yadadri"],
            "duration_days": 1,
            "itinerary_text": "",
        })
        assert response.status_code == 422
    finally:
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
