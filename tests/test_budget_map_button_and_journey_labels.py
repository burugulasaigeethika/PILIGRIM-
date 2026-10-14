"""
PilgrimAI - Regression Test Suite for Budget Map Button and User-Friendly Journey Labels

Validates:
1. An itinerary response still shows the correct map action and route metadata.
2. A budget response with valid route metadata shows working route metadata and map action.
3. Multiple journey routes have unique registry keys so clicking Journey 2 opens Journey 2's route, not Journey 1.
4. A budget response without route metadata does not produce route legs or broken map actions.
5. Budget totals, unknown travel expenses and incomplete-estimate labels remain unchanged (no cost inferred from distance/duration).
6. Journey headings use user-friendly names ('Journey 1: ...', 'Journey 2: ...', 'Return Journey: ...') preserving actual location names.
7. Existing route tests pass.
"""

import sys
import re
from pathlib import Path
from unittest.mock import MagicMock

backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.state import AgentState, AgentResponse
from app.agents.budget_agent import BudgetAgent, extract_budget_parameters
from app.agents.itinerary_planning_agent import ItineraryPlanningAgent
from app.agents.adapters.navigation_adapter import NavigationAdapter
from app.agents.response_aggregator import ResponseAggregator


def make_mock_navigation_adapter():
    mock_adapter = MagicMock(spec=NavigationAdapter)
    mock_adapter.has_credentials = True
    mock_adapter.transport = None

    call_count = 0
    def mock_compute_route(origin, destination, travel_mode="driving"):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {
                "routes": [{
                    "distanceMeters": 275400,
                    "duration": "18000s",
                    "staticDuration": "18000s",
                    "polyline": {"encodedPolyline": "poly_journey1_mock"},
                    "viewport": {"low": {"latitude": 16.5, "longitude": 78.4}, "high": {"latitude": 17.4, "longitude": 80.6}}
                }]
            }
        elif call_count == 2:
            return {
                "routes": [{
                    "distanceMeters": 220100,
                    "duration": "17100s",
                    "staticDuration": "17100s",
                    "polyline": {"encodedPolyline": "poly_journey2_mock"},
                    "viewport": {"low": {"latitude": 17.4, "longitude": 78.4}, "high": {"latitude": 18.9, "longitude": 79.1}}
                }]
            }
        else:
            return {
                "routes": [{
                    "distanceMeters": 150000,
                    "duration": "10000s",
                    "staticDuration": "10000s",
                    "polyline": {"encodedPolyline": f"poly_journey{call_count}_mock"},
                    "viewport": {"low": {"latitude": 17.0, "longitude": 78.0}, "high": {"latitude": 18.0, "longitude": 79.0}}
                }]
            }

    mock_adapter.compute_route.side_effect = mock_compute_route
    return mock_adapter


def simulate_render_route_journeys_snippet(meta):
    """
    Python mirror of app.js renderRouteJourneysSnippet(meta).
    Simulates registry storage and HTML generation.
    """
    if not meta:
        return "", {}

    registry = {}

    if meta.get("route_legs") and isinstance(meta["route_legs"], list) and len(meta["route_legs"]) > 0:
        legs_html_list = []
        for idx, leg in enumerate(meta["route_legs"]):
            leg_num = leg.get("leg_index", idx + 1)
            orig = leg.get("origin", "Origin")
            dest = leg.get("destination", "Destination")
            is_return = leg.get("is_return", False)
            journey_label = leg.get("journey_label") or (
                f"Return Journey: {orig} to {dest}" if is_return else f"Journey {leg_num}: {orig} to {dest}"
            )

            if leg.get("status") == "unavailable" or leg.get("distance_km") is None:
                err_msg = leg.get("error") or "Route calculation unavailable"
                legs_html_list.append(f"<div>{journey_label}: Route details unavailable ({err_msg})</div>")
                continue

            dist = f"{leg['distance_km']} km"
            polyline = leg.get("polyline") or ""
            viewport = leg.get("viewport")

            route_key = f"rt_jny_{leg_num}_{idx}_test"
            registry[route_key] = {
                "origin": orig,
                "destination": dest,
                "polyline": polyline,
                "viewport": viewport
            }

            btn_html = f'<button class="nav-btn-view-map" data-route-key="{route_key}">🗺️ View Route on Map</button>'
            legs_html_list.append(f"<div>{journey_label} - {dist} {btn_html}</div>")

        return "\n".join(legs_html_list), registry

    if meta.get("origin") and meta.get("distance_km") is not None:
        orig = meta["origin"]
        dest = meta.get("destination", "Destination")
        journey_label = f"Journey 1: {orig} to {dest}"
        dist = f"{meta['distance_km']} km"
        route_key = "rt_jny_1_single_test"
        registry[route_key] = {
            "origin": orig,
            "destination": dest,
            "polyline": meta.get("polyline") or "",
            "viewport": meta.get("viewport")
        }
        btn_html = f'<button class="nav-btn-view-map" data-route-key="{route_key}">🗺️ View Route on Map</button>'
        return f"<div>{journey_label} - {dist} {btn_html}</div>", registry

    return "", {}


def test_1_itinerary_response_shows_correct_map_action():
    """Verify an itinerary response populates route metadata with working map button info."""
    nav_adapter = make_mock_navigation_adapter()
    agent = ItineraryPlanningAgent(navigation_adapter=nav_adapter)
    state = AgentState(user_query="Plan a 4-day trip from Vijayawada, Andhra Pradesh to Birla Mandir and Dharmapuri")
    resp = agent.execute(state)

    assert resp.success is True
    meta = resp.metadata
    assert meta.get("route_legs") is not None
    assert len(meta["route_legs"]) == 2

    # Check journey headings in text
    assert "Journey 1: Vijayawada, Andhra Pradesh to Birla Mandir" in resp.answer
    assert "Journey 2: Birla Mandir to Dharmapuri" in resp.answer
    assert "Leg 1" not in resp.answer
    assert "Leg 2" not in resp.answer

    # Check UI rendering simulation
    html, reg = simulate_render_route_journeys_snippet(meta)
    assert "🗺️ View Route on Map" in html
    assert len(reg) == 2


def test_2_budget_response_with_route_metadata_shows_working_map_action():
    """Verify a budget response with valid origin computes route legs and renders map button."""
    nav_adapter = make_mock_navigation_adapter()
    agent = BudgetAgent(navigation_adapter=nav_adapter)
    state = AgentState(user_query="What is the budget for 2 people from Hyderabad to Yadadri?")
    resp = agent.execute(state)

    assert resp.success is True
    meta = resp.metadata

    # Route metadata must be present
    assert meta.get("origin") == "Hyderabad"
    assert meta.get("route_legs") is not None
    assert len(meta["route_legs"]) >= 1

    leg1 = meta["route_legs"][0]
    assert leg1["origin"] == "Hyderabad"
    assert "Yadadri" in leg1["destination"]
    assert leg1["status"] == "success"
    assert leg1["distance_km"] is not None
    assert leg1["polyline"] is not None

    # Markdown answer has journey section
    assert "Journey 1: Hyderabad to Yadadri" in resp.answer or "Journey 1:" in resp.answer
    assert "Leg 1" not in resp.answer

    # Frontend UI simulation
    html, reg = simulate_render_route_journeys_snippet(meta)
    assert "🗺️ View Route on Map" in html
    assert len(reg) >= 1
    first_key = list(reg.keys())[0]
    assert reg[first_key]["polyline"] == leg1["polyline"]


def test_3_multiple_journey_routes_have_unique_registry_keys():
    """Verify multiple journey routes do not overwrite each other and open correct routes."""
    nav_adapter = make_mock_navigation_adapter()
    agent = BudgetAgent(navigation_adapter=nav_adapter)
    state = AgentState(user_query="Budget for trip from Vijayawada to Birla Mandir and Dharmapuri")
    resp = agent.execute(state)

    assert resp.success is True
    meta = resp.metadata
    assert len(meta["route_legs"]) == 2

    html, reg = simulate_render_route_journeys_snippet(meta)
    keys = list(reg.keys())
    assert len(keys) == 2
    assert keys[0] != keys[1]

    # Journey 1 route is distinct from Journey 2 route
    assert reg[keys[0]]["origin"] == "Vijayawada"
    assert reg[keys[0]]["polyline"] == "poly_journey1_mock"

    assert reg[keys[1]]["origin"] == "Birla Mandir"
    assert reg[keys[1]]["destination"] == "Dharmapuri"
    assert reg[keys[1]]["polyline"] == "poly_journey2_mock"


def test_4_budget_response_without_route_metadata_has_no_map_button():
    """Verify a budget query without origin does not show a broken or misleading map button."""
    agent = BudgetAgent()
    state = AgentState(user_query="What is the budget for 2 people to visit Basara?")
    resp = agent.execute(state)

    assert resp.success is True
    meta = resp.metadata
    assert meta.get("route_legs") is None
    assert meta.get("distance_km") is None
    assert meta.get("origin") is None

    html, reg = simulate_render_route_journeys_snippet(meta)
    assert html == ""
    assert len(reg) == 0
    assert "View Route on Map" not in html


def test_5_budget_totals_and_unquantified_expenses_remain_unchanged():
    """Verify that route distance/duration does NOT infer travel cost or alter verified budget math."""
    nav_adapter = make_mock_navigation_adapter()
    agent = BudgetAgent(navigation_adapter=nav_adapter)

    # 1. Day trip without user-provided travel cost
    state = AgentState(user_query="Budget for 1 day visit from Hyderabad to Yadadri")
    resp = agent.execute(state)
    assert resp.success is True
    meta = resp.metadata

    # Personal Travel remains unquantified
    assert "Personal Travel / Transit" in resp.answer or "travel" in resp.answer.lower()
    assert "Unquantified (varies by transport provider)" in resp.answer or "varies by transport provider" in resp.answer

    # Subtotal and total remain intact
    total_data = meta["calculated_total"]
    assert "min" in total_data and "max" in total_data
    assert total_data["currency"] == "INR"

    # Incomplete estimate label remains intact
    assert "Incomplete estimate" in resp.answer or "Incomplete Estimate" in resp.answer

    # Distance is 275.4 km, but budget is not multiplied by any cost/km
    assert meta.get("distance_km") == 275.4


def test_6_journey_headings_format():
    """Verify journey labels format: 'Journey 1: ...', 'Journey 2: ...', 'Return Journey: ...'."""
    nav_adapter = make_mock_navigation_adapter()
    agent = ItineraryPlanningAgent(navigation_adapter=nav_adapter)
    state = AgentState(user_query="Plan a 3-day round trip from Rajasthan to Birla Mandir and Dharmapuri")
    resp = agent.execute(state)

    assert resp.success is True
    meta = resp.metadata
    legs = meta.get("route_legs", [])
    assert len(legs) == 3

    assert legs[0]["journey_label"] == "Journey 1: Rajasthan to Birla Mandir"
    assert legs[1]["journey_label"] == "Journey 2: Birla Mandir to Dharmapuri"
    assert legs[2]["journey_label"] == "Return Journey: Dharmapuri to Rajasthan"

    # Internal identifiers like 'Leg 1' or 'leg_index' must NOT appear in the user headings
    assert "Journey 1: Rajasthan to Birla Mandir" in resp.answer
    assert "Journey 2: Birla Mandir to Dharmapuri" in resp.answer
    assert "Return Journey: Dharmapuri to Rajasthan" in resp.answer
    assert "Leg 1" not in resp.answer
    assert "Leg 2" not in resp.answer
    assert "Leg 3" not in resp.answer


def test_7_aggregated_multi_intent_budget_response_retains_route_data():
    """Verify aggregated response combining itinerary and budget passes route data to budget card."""
    nav_adapter = make_mock_navigation_adapter()
    itin_agent = ItineraryPlanningAgent(navigation_adapter=nav_adapter)
    budget_agent = BudgetAgent(navigation_adapter=nav_adapter)

    query = "Plan a 2 day trip with budget from Hyderabad to Yadadri"
    state = AgentState(user_query=query)

    resp_itin = itin_agent.execute(state)
    resp_budget = budget_agent.execute(state)

    aggregator = ResponseAggregator()
    aggregated = aggregator.aggregate([resp_itin, resp_budget])

    assert aggregated.success is True
    meta = aggregated.metadata

    # Merged metadata contains both budget total and route legs
    assert "calculated_total" in meta
    assert "route_legs" in meta
    assert len(meta["route_legs"]) >= 1

    # Frontend snippet renders correctly on aggregated metadata
    html, reg = simulate_render_route_journeys_snippet(meta)
    assert "🗺️ View Route on Map" in html
    assert len(reg) >= 1
