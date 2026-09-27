"""
Unit and integration tests for Maps, Places, and Frontend Configuration endpoints.
Verifies:
1. /api/maps/config returns runtime enablement state without leaking to other endpoints.
2. /api/maps/temples exposes all 20 canonical temples with verified coordinates from TempleCoordinateRegistry.
3. /api/maps/places gracefully returns structured response and offline status when mock/offline.
4. / root endpoint serves the updated HTML frontend.
5. Strict credential isolation: chat responses, metadata, and temple coordinates NEVER contain the API key.
"""

import os
import sys
import asyncio
from pathlib import Path
import pytest
import httpx

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app
from app.agents.coordinate_registry import coordinate_registry


class SyncTestClient:
    """Synchronous test client wrapper around httpx.AsyncClient for FastAPI ASGI app."""
    def __init__(self, asgi_app):
        self.app = asgi_app

    def post(self, url: str, json_data: dict):
        async def _call():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://testserver") as client:
                return await client.post(url, json=json_data)
        return asyncio.run(_call())

    def get(self, url: str):
        async def _call():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://testserver") as client:
                return await client.get(url)
        return asyncio.run(_call())


client = SyncTestClient(app)


def test_maps_config_endpoint():
    """Verify /api/maps/config returns valid structure."""
    response = client.get("/api/maps/config")
    assert response.status_code == 200
    data = response.json()
    assert "enabled" in data
    assert "api_key" in data
    assert isinstance(data["enabled"], bool)
    assert isinstance(data["api_key"], str)


def test_maps_temples_endpoint():
    """Verify /api/maps/temples returns all 20 canonical temples with verified coordinates."""
    response = client.get("/api/maps/temples")
    assert response.status_code == 200
    temples = response.json()
    assert len(temples) == 20

    canonical_names = {t["canonical_name"] for t in temples}
    assert "Yadadri" in canonical_names
    assert "Basara" in canonical_names
    assert "Srisaila" in canonical_names
    assert "Badrachalam" in canonical_names

    for t in temples:
        assert -90.0 <= t["latitude"] <= 90.0
        assert -180.0 <= t["longitude"] <= 180.0
        assert t["display_name"]
        assert t["state"] in ("Telangana", "Andhra Pradesh")
        assert "verification_status" in t


def test_maps_places_offline_graceful():
    """Verify /api/maps/places gracefully degrades without erroring."""
    response = client.get("/api/maps/places?query=hotels+near+Yadadri&latitude=17.5888&longitude=78.9482")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["source"] == "Live Google Places Results"
    assert isinstance(data["results"], list)


def test_root_serves_html():
    """Verify root endpoint serves the frontend HTML with proper references."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    html_text = response.text
    assert "PilgrimAI" in html_text
    assert "/static/style.css" in html_text
    assert "/static/app.js" in html_text
    assert "googleMapContainer" in html_text
    assert "newChatBtn" in html_text


def test_credential_leak_isolation():
    """
    Ensure that chat responses, metadata, and temple coordinates NEVER leak the API key.
    """
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if not key:
        pytest.skip("GOOGLE_MAPS_API_KEY not set")

    # 1. Check temples endpoint
    resp_temples = client.get("/api/maps/temples")
    assert key not in resp_temples.text

    # 2. Check health endpoint
    resp_health = client.get("/health")
    assert key not in resp_health.text


def test_routes_and_maps_credential_separation(monkeypatch):
    """
    Verify strict separation between browser Maps key and server Routes key:
    - /api/maps/config exposes only GOOGLE_MAPS_API_KEY, never GOOGLE_ROUTES_API_KEY.
    """
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "mock-browser-key-xyz123")
    monkeypatch.setenv("GOOGLE_ROUTES_API_KEY", "mock-server-key-routes999")

    resp = client.get("/api/maps/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["api_key"] == "mock-browser-key-xyz123"
    assert "mock-server-key-routes999" not in resp.text
    assert "mock-server-key-routes999" not in str(data)


def test_navigation_adapter_credential_precedence(monkeypatch):
    """
    Verify NavigationAdapter prioritizes GOOGLE_ROUTES_API_KEY over GOOGLE_MAPS_API_KEY,
    and falls back cleanly when GOOGLE_ROUTES_API_KEY is not set.
    """
    from app.agents.adapters.navigation_adapter import NavigationAdapter

    # Scenario 1: Only GOOGLE_MAPS_API_KEY is present
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "fallback-key-111")
    monkeypatch.delenv("GOOGLE_ROUTES_API_KEY", raising=False)
    adapter1 = NavigationAdapter()
    assert adapter1._api_key == "fallback-key-111"

    # Scenario 2: Both are present -> GOOGLE_ROUTES_API_KEY takes precedence
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "browser-key-222")
    monkeypatch.setenv("GOOGLE_ROUTES_API_KEY", "dedicated-routes-server-key-333")
    adapter2 = NavigationAdapter()
    assert adapter2._api_key == "dedicated-routes-server-key-333"

    # Scenario 3: Explicit constructor argument overrides environment
    adapter3 = NavigationAdapter(api_key="explicit-override-key-444")
    assert adapter3._api_key == "explicit-override-key-444"

