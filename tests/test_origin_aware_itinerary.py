"""
PilgrimAI - Origin-Aware Itinerary Planning Test Suite

Focused, offline tests validating:
1. Origin and destination extraction.
2. Origin not being treated as a destination temple (e.g. registered temple as origin).
3. Backward compatibility when no origin is supplied.
4. Route distance and estimated duration inclusion when route succeeds.
5. Graceful fallback when route calculation fails (timeout / network error / no credentials).
6. Feasibility warning for long journeys on single-day trips without suppressing itinerary.
7. Memory follow-up resolution ("What if I start from Warangal instead?").
8. Router correctly directs origin-aware itinerary queries to itinerary_planning.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.state import AgentState, AgentResponse
from app.agents.itinerary_planning_agent import ItineraryPlanningAgent
from app.agents.adapters.navigation_adapter import NavigationAdapter
from app.agents.adapters.external_adapter import ExternalTimeoutError
from app.agents.router import AgentRouter
from app.agents.memory import ConversationMemoryManager


def test_1_origin_and_destination_extraction():
    agent = ItineraryPlanningAgent()
    q1 = "Plan a one-day trip from Hyderabad to Basara"
    origin1 = agent.extract_origin(q1)
    temples1 = agent.detect_temples(q1, origin=origin1)
    assert origin1 == "Hyderabad"
    assert temples1 == ["Basara"]

    q2 = "Plan a 2-day trip to Vemulavada and Dharmapuri from Warangal"
    origin2 = agent.extract_origin(q2)
    temples2 = agent.detect_temples(q2, origin=origin2)
    assert origin2 == "Warangal"
    assert temples2 == ["Vemulavada", "Dharmapuri"]

    q3 = "Trip starting from Nizamabad to Basara"
    origin3 = agent.extract_origin(q3)
    temples3 = agent.detect_temples(q3, origin=origin3)
    assert origin3 == "Nizamabad"
    assert temples3 == ["Basara"]


def test_2_origin_not_treated_as_destination_temple():
    agent = ItineraryPlanningAgent()
    # Yadadri is a registered canonical temple, but is specified as origin
    q = "Plan a trip from Yadadri to Vemulavada"
    origin = agent.extract_origin(q)
    assert origin == "Yadadri"
    temples = agent.detect_temples(q, origin=origin)
    assert temples == ["Vemulavada"]
    assert "Yadadri" not in temples


def test_3_existing_behaviour_when_no_origin_supplied():
    agent = ItineraryPlanningAgent()
    state = AgentState(user_query="Plan a one-day trip to Basara", session_id="test_no_origin")
    resp = agent.execute(state)

    assert resp.success is True
    assert "Basara" in resp.answer
    assert resp.metadata.get("origin") is None
    assert resp.metadata.get("distance_km") is None
    assert resp.metadata.get("duration_days") == 1
    assert "Live-Data Limitation" in resp.answer


def test_4_route_distance_and_duration_mock_success():
    mock_adapter = MagicMock(spec=NavigationAdapter)
    mock_adapter.has_credentials = True
    mock_adapter.transport = None
    mock_adapter.compute_route.return_value = {
        "routes": [
            {
                "distanceMeters": 210500,
                "duration": "16200s", # 270 minutes (4.5 hours)
                "staticDuration": "16200s",
                "polyline": {"encodedPolyline": "mock_polyline_xyz"},
                "viewport": {"low": {"latitude": 17.0, "longitude": 78.0}, "high": {"latitude": 18.0, "longitude": 79.0}}
            }
        ]
    }

    agent = ItineraryPlanningAgent(navigation_adapter=mock_adapter)
    state = AgentState(user_query="Plan a one-day trip from Hyderabad to Basara", session_id="test_mock_success")
    resp = agent.execute(state)

    assert resp.success is True
    assert "210.5 km" in resp.answer
    assert "4 hr 30 min" in resp.answer
    assert resp.metadata["origin"] == "Hyderabad"
    assert resp.metadata["destination"] == "Basara"
    assert resp.metadata["distance_km"] == 210.5
    assert resp.metadata["duration_minutes"] == 270.0
    assert resp.metadata["polyline"] == "mock_polyline_xyz"


def test_5_itinerary_available_when_route_fails():
    mock_adapter = MagicMock(spec=NavigationAdapter)
    mock_adapter.has_credentials = True
    mock_adapter.transport = None
    mock_adapter.compute_route.side_effect = ExternalTimeoutError("Navigation request timed out")

    agent = ItineraryPlanningAgent(navigation_adapter=mock_adapter)
    state = AgentState(user_query="Plan a one-day trip from Hyderabad to Basara", session_id="test_mock_timeout")
    resp = agent.execute(state)

    # Itinerary must NOT crash or fail
    assert resp.success is True
    assert "Basara" in resp.answer
    assert "Route details could not be calculated" in resp.answer
    assert resp.metadata.get("distance_km") is None
    assert resp.metadata.get("duration_minutes") is None


def test_6_long_journey_feasibility_warning():
    mock_adapter = MagicMock(spec=NavigationAdapter)
    mock_adapter.has_credentials = True
    mock_adapter.transport = None
    mock_adapter.compute_route.return_value = {
        "routes": [
            {
                "distanceMeters": 210000,
                "duration": "16200s", # 4.5 hours each way = 9 hours round trip
                "staticDuration": "16200s",
                "polyline": {"encodedPolyline": "mock_poly"}
            }
        ]
    }

    agent = ItineraryPlanningAgent(navigation_adapter=mock_adapter)
    state = AgentState(user_query="Plan a one-day trip from Hyderabad to Basara", session_id="test_feasibility")
    resp = agent.execute(state)

    assert resp.success is True
    # Feasibility warning must be present
    assert "Travel Feasibility Advisory" in resp.answer
    assert "overnight stay" in resp.answer.lower()
    assert resp.metadata.get("feasibility_warning") is not None
    # Complete itinerary must still be returned
    assert "Day 1: Basara" in resp.answer


def test_7_memory_origin_followup_resolution():
    memory = ConversationMemoryManager()
    session_id = "test_memory_session_1"

    # Turn 1: user discusses Basara
    memory.add_turn(
        session_id=session_id,
        user_query="Plan a one-day trip to Basara",
        resolved_query="Plan a one-day trip to Basara",
        detected_intents=["itinerary_planning"],
        identified_temples=["Basara"],
        response_summary="Itinerary for Basara"
    )

    # Turn 2: follow-up query specifying new origin
    turn2_query = "What if I start from Warangal instead?"
    resolution = memory.resolve_query(session_id, turn2_query)

    assert resolution["is_ambiguous"] is False
    assert resolution["referenced_temple"] == "Basara"
    assert "Plan a trip from Warangal to Basara" in resolution["resolved_query"]


def test_8_router_origin_itinerary_routing():
    router = AgentRouter()
    router.register_agent("itinerary_planning")
    decision = router.route("Plan a one-day trip from Hyderabad to Basara")
    assert decision.intent == "itinerary_planning"
    assert decision.selected_agent == "itinerary_planning"


def test_9_two_temples_with_origin_consecutive_legs():
    """
    Validates:
    - Origin-to-first-temple and first-to-second-temple legs are calculated.
    - Previous temple is used as the next leg's origin.
    - Each leg retains distinct distance and duration metadata without overwriting.
    - Return leg is NOT included when not requested, and response explicitly notes it.
    - Schedule accounts for inter-temple travel time.
    """
    mock_adapter = MagicMock(spec=NavigationAdapter)
    mock_adapter.has_credentials = True
    mock_adapter.transport = None

    call_idx = 0
    def mock_compute_route(origin, destination, travel_mode="driving"):
        nonlocal call_idx
        call_idx += 1
        if call_idx == 1:
            # Leg 1: Vijayawada -> Birla Mandir
            return {
                "routes": [{
                    "distanceMeters": 275400,
                    "duration": "18600s", # 310 min (~5 hr 10 min)
                    "staticDuration": "18000s",
                    "polyline": {"encodedPolyline": "poly_leg1_vjw_birla"},
                    "viewport": {"low": {"latitude": 16.5, "longitude": 78.4}, "high": {"latitude": 17.4, "longitude": 80.6}}
                }]
            }
        else:
            # Leg 2: Birla Mandir to Dharmapuri
            return {
                "routes": [{
                    "distanceMeters": 220100,
                    "duration": "17100s", # 285 min (~4 hr 45 min)
                    "staticDuration": "17100s",
                    "polyline": {"encodedPolyline": "poly_leg2_birla_dharmapuri"},
                    "viewport": {"low": {"latitude": 17.4, "longitude": 78.4}, "high": {"latitude": 18.9, "longitude": 79.1}}
                }]
            }

    mock_adapter.compute_route.side_effect = mock_compute_route

    agent = ItineraryPlanningAgent(navigation_adapter=mock_adapter)
    query = "Plan a 4 day trip from Vijayawada, Andhra Pradesh, to Birla Mandir and Dharmapuri Temple."
    state = AgentState(user_query=query, session_id="test_multi_leg_1")
    resp = agent.execute(state)

    assert resp.success is True
    assert "Birla Mandir" in resp.answer
    assert "Dharmapuri" in resp.answer

    # Verify legs metadata
    route_legs = resp.metadata.get("route_legs")
    assert route_legs is not None
    assert len(route_legs) == 2 # Leg 1 and Leg 2, NO return leg

    leg1 = route_legs[0]
    assert leg1["leg_index"] == 1
    assert "Vijayawada" in leg1["origin"]
    assert leg1["destination"] == "Birla Mandir"
    assert leg1["distance_km"] == 275.4
    assert leg1["duration_minutes"] == 300.0 or leg1["duration_minutes"] == 310.0
    assert leg1["polyline"] == "poly_leg1_vjw_birla"
    assert leg1["is_return"] is False

    leg2 = route_legs[1]
    assert leg2["leg_index"] == 2
    assert leg2["origin"] == "Birla Mandir"
    assert leg2["destination"] == "Dharmapuri"
    assert leg2["distance_km"] == 220.1
    assert leg2["duration_minutes"] == 285.0
    assert leg2["polyline"] == "poly_leg2_birla_dharmapuri"
    assert leg2["is_return"] is False

    # Return leg must NOT be requested
    assert resp.metadata.get("return_leg_requested") is False
    assert "return leg" in resp.answer.lower() or "return journey" in resp.answer.lower()
    assert "not included" in resp.answer.lower()

    # Verify both journeys are displayed in the answer with distinct metrics
    assert "Journey 1" in resp.answer
    assert "Journey 2" in resp.answer
    assert "275.4 km" in resp.answer
    assert "220.1 km" in resp.answer

    # Verify inter-temple travel is reflected in the schedule
    assert "Inter-Temple Transit" in resp.answer or "transit to Dharmapuri" in resp.answer


def test_10_return_leg_when_explicitly_requested():
    """
    Validates that a return leg (last temple -> origin) is calculated ONLY
    when explicitly requested in the query.
    """
    mock_adapter = MagicMock(spec=NavigationAdapter)
    mock_adapter.has_credentials = True
    mock_adapter.transport = None

    call_count = 0
    def mock_compute_route(origin, destination, travel_mode="driving"):
        nonlocal call_count
        call_count += 1
        return {
            "routes": [{
                "distanceMeters": 150000 + call_count * 10000,
                "duration": f"{7200 + call_count * 600}s",
                "staticDuration": f"{7200 + call_count * 600}s",
                "polyline": {"encodedPolyline": f"poly_leg_{call_count}"}
            }]
        }

    mock_adapter.compute_route.side_effect = mock_compute_route

    agent = ItineraryPlanningAgent(navigation_adapter=mock_adapter)
    query = "Plan a 4 day round trip from Warangal to Vemulavada and Dharmapuri"
    state = AgentState(user_query=query, session_id="test_return_leg")
    resp = agent.execute(state)

    assert resp.success is True
    route_legs = resp.metadata.get("route_legs")
    assert route_legs is not None
    # 3 legs: Warangal -> Vemulavada, Vemulavada -> Dharmapuri, Dharmapuri -> Warangal
    assert len(route_legs) == 3

    assert route_legs[0]["origin"] == "Warangal"
    assert route_legs[0]["destination"] == "Vemulavada"
    assert route_legs[0]["is_return"] is False

    assert route_legs[1]["origin"] == "Vemulavada"
    assert route_legs[1]["destination"] == "Dharmapuri"
    assert route_legs[1]["is_return"] is False

    assert route_legs[2]["origin"] == "Dharmapuri"
    assert route_legs[2]["destination"] == "Warangal"
    assert route_legs[2]["is_return"] is True

    assert resp.metadata["return_leg_requested"] is True
    assert "Return Journey" in resp.answer


def test_11_partial_leg_failure_does_not_erase_successful_routes():
    """
    Validates that if one leg fails (e.g. timeout on Leg 2), Leg 1 retains its data,
    Leg 2 is clearly marked unavailable, and the complete itinerary remains intact.
    """
    mock_adapter = MagicMock(spec=NavigationAdapter)
    mock_adapter.has_credentials = True
    mock_adapter.transport = None

    call_index = 0
    def mock_compute_route(origin, destination, travel_mode="driving"):
        nonlocal call_index
        call_index += 1
        if call_index == 1:
            return {
                "routes": [{
                    "distanceMeters": 180000,
                    "duration": "10800s",
                    "staticDuration": "10800s",
                    "polyline": {"encodedPolyline": "poly_leg1_success"}
                }]
            }
        else:
            raise ExternalTimeoutError("Navigation provider timed out on Leg 2")

    mock_adapter.compute_route.side_effect = mock_compute_route

    agent = ItineraryPlanningAgent(navigation_adapter=mock_adapter)
    query = "Plan a 3-day trip from Hyderabad to Basara and Dharmapuri"
    state = AgentState(user_query=query, session_id="test_partial_failure")
    resp = agent.execute(state)

    assert resp.success is True
    route_legs = resp.metadata.get("route_legs")
    assert len(route_legs) == 2

    # Leg 1 succeeded
    assert route_legs[0]["status"] == "success"
    assert route_legs[0]["distance_km"] == 180.0
    assert route_legs[0]["polyline"] == "poly_leg1_success"

    # Leg 2 failed gracefully
    assert route_legs[1]["status"] == "unavailable"
    assert route_legs[1]["distance_km"] is None
    assert "timed out" in route_legs[1]["error"].lower()

    # Verified itinerary for both temples is intact
    assert "Basara" in resp.answer
    assert "Dharmapuri" in resp.answer
    assert "180.0 km" in resp.answer
    assert "Route details could not be calculated" in resp.answer
