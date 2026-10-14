import sys
from pathlib import Path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pytest
from typing import Dict, Any, Optional

from app.agents.adapters.navigation_adapter import NavigationAdapter
from app.agents.live_navigation_agent import LiveNavigationAgent, NavigationResult
from app.agents.coordinate_registry import TempleCoordinateRegistry


class MockNavTransport:
    def __init__(self, response_data: Optional[Dict[str, Any]] = None, status_code: int = 200):
        if response_data is not None:
            self.response_data = response_data
        else:
            self.response_data = {
                "routes": [
                    {
                        "distanceMeters": 71000,
                        "duration": "7140s",
                        "staticDuration": "6500s",
                        "description": "Keesara - Yadagirigutta Rd",
                        "polyline": {
                            "encodedPolyline": "sufiBqq~}Mt@FpEz@nDbAtAXVAxAFx"
                        },
                        "viewport": {
                            "low": {"latitude": 17.3905599, "longitude": 78.4758925},
                            "high": {"latitude": 17.5046334, "longitude": 78.9293795}
                        },
                        "travelAdvisory": {
                            "speedReadingIntervals": [
                                {"startPolylinePointIndex": 0, "endPolylinePointIndex": 10, "speed": "NORMAL"},
                                {"startPolylinePointIndex": 10, "endPolylinePointIndex": 25, "speed": "SLOW"}
                            ]
                        }
                    }
                ]
            }
        self.status_code = status_code
        self.last_headers = None
        self.last_payload = None

    def __call__(self, method: str, url: str, headers: dict = None, json: Any = None, **kwargs):
        self.last_headers = headers
        self.last_payload = json
        class MockResp:
            def __init__(self, sc, d):
                self.status_code = sc
                self._data = d
                self.headers = {}
                self.text = ""
            def json(self):
                return self._data
        return MockResp(self.status_code, self.response_data)


def test_navigation_adapter_requests_polyline_and_traffic():
    """Verify NavigationAdapter includes polyline, viewport and traffic intervals in FieldMask."""
    transport = MockNavTransport()
    adapter = NavigationAdapter(api_key="TEST_KEY", transport=transport)
    res = adapter.compute_route(
        origin="Hyderabad",
        destination="Yadadri",
        travel_mode="driving"
    )
    assert transport.last_headers is not None
    field_mask = transport.last_headers.get("X-Goog-FieldMask", "")
    assert "routes.polyline.encodedPolyline" in field_mask
    assert "routes.viewport" in field_mask
    assert "routes.travelAdvisory.speedReadingIntervals" in field_mask
    assert transport.last_payload.get("extraComputations") == ["TRAFFIC_ON_POLYLINE"]
    assert "routes" in res
    assert "polyline" in res["routes"][0]


def test_navigation_adapter_walking_omits_traffic_computations():
    """Verify walking mode does not request DRIVE-only traffic parameters."""
    transport = MockNavTransport()
    adapter = NavigationAdapter(api_key="TEST_KEY", transport=transport)
    res = adapter.compute_route(
        origin="Origin",
        destination="Destination",
        travel_mode="walking"
    )
    field_mask = transport.last_headers.get("X-Goog-FieldMask", "")
    assert "routes.polyline.encodedPolyline" in field_mask
    assert "routes.viewport" in field_mask
    assert "speedReadingIntervals" not in field_mask
    assert "extraComputations" not in transport.last_payload


def test_live_navigation_agent_extracts_polyline_and_intervals():
    """Verify LiveNavigationAgent captures polyline, viewport, and speed reading intervals in metadata."""
    transport = MockNavTransport()
    adapter = NavigationAdapter(api_key="TEST_KEY", transport=transport)
    agent = LiveNavigationAgent(adapter=adapter)
    
    from app.agents.state import AgentState
    state = AgentState(user_query="How to reach Yadadri from Hyderabad")
    response = agent.execute(state)
    if not response.success:
        print("Agent failed with:", response.error, response.answer)
    assert response.success is True
    meta = response.metadata
    assert meta["origin"] == "Hyderabad"
    assert "polyline" in meta
    assert meta["polyline"] == "sufiBqq~}Mt@FpEz@nDbAtAXVAxAFx"
    assert "viewport" in meta
    assert meta["viewport"]["low"]["latitude"] == 17.3905599
    assert "speed_reading_intervals" in meta
    assert len(meta["speed_reading_intervals"]) == 2
    assert meta["speed_reading_intervals"][1]["speed"] == "SLOW"


def test_live_navigation_agent_backward_compatible_without_geometry():
    """Verify LiveNavigationAgent gracefully handles provider responses without polyline or traffic."""
    legacy_response = {
        "routes": [
            {
                "distanceMeters": 4600,
                "duration": "690s",
                "description": "Inner Ring Rd"
            }
        ]
    }
    transport = MockNavTransport(response_data=legacy_response)
    adapter = NavigationAdapter(api_key="TEST_KEY", transport=transport)
    agent = LiveNavigationAgent(adapter=adapter)
    
    from app.agents.state import AgentState
    state = AgentState(user_query="distance from Chikkadpally to Birla Mandir")
    response = agent.execute(state)
    if not response.success:
        print("Agent failed with:", response.error, response.answer)
    assert response.success is True
    meta = response.metadata
    assert meta["distance_km"] == 4.6
    assert meta["polyline"] is None
    assert meta["viewport"] is None
    assert meta["speed_reading_intervals"] is None


def test_polyline_decoder_algorithm():
    """Verify standard Google polyline decoding logic matching app.js decodePolyline."""
    # Standard complete encoded polyline for points (38.5, -120.2), (40.7, -120.95), (43.252, -126.453)
    encoded = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
    points = []
    index = 0
    length = len(encoded)
    lat = 0
    lng = 0
    while index < length:
        shift = 0
        result = 0
        while True:
            if index >= length:
                break
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat

        shift = 0
        result = 0
        while True:
            if index >= length:
                break
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng

        points.append({"lat": round(lat / 1e5, 5), "lng": round(lng / 1e5, 5)})

    assert len(points) == 3
    assert points[0]["lat"] == 38.5
    assert points[0]["lng"] == -120.2
    assert points[1]["lat"] == 40.7
    assert points[1]["lng"] == -120.95


if __name__ == "__main__":
    print("Running test_navigation_adapter_requests_polyline_and_traffic...")
    test_navigation_adapter_requests_polyline_and_traffic()
    print("  PASS")

    print("Running test_navigation_adapter_walking_omits_traffic_computations...")
    test_navigation_adapter_walking_omits_traffic_computations()
    print("  PASS")

    print("Running test_live_navigation_agent_extracts_polyline_and_intervals...")
    test_live_navigation_agent_extracts_polyline_and_intervals()
    print("  PASS")

    print("Running test_live_navigation_agent_backward_compatible_without_geometry...")
    test_live_navigation_agent_backward_compatible_without_geometry()
    print("  PASS")

    print("Running test_polyline_decoder_algorithm...")
    test_polyline_decoder_algorithm()
    print("  PASS")

    print("\nALL 5 FOCUSED ROUTE & MAP VISUALIZATION TESTS PASSED!")
