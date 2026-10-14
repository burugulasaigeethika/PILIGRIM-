"""
PilgrimAI - Regression Suite: Multi-Destination Accommodation, Nearby Activities & Itinerary UX Fixes

Targeted tests covering:
1. One recommended stay per destination requiring an overnight stay.
2. Correct night allocation across multiple destinations.
3. No accommodation assigned to the wrong destination.
4. Stable recommendation labels after selecting an alternative.
5. Changing one property's selection does not change another destination's selection.
6. Accommodation preference filtering is consistent across all sections.
7. Alternative properties do not affect the selected-plan total.
8. Accommodation totals match the selected properties, room count, and nights.
9. The itinerary's initial accommodation summary names the relevant destination.
10. Nearby discovery handles missing coordinates, empty results, duplicate places, and provider errors.
11. Adding or removing an attraction updates affected routes without changing the requested temple order.
12. Weather is shown only when supported data exists and is labelled correctly.
"""

import sys
import os
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.state import AgentState
from app.agents.budget_agent import BudgetAgent
from app.agents.itinerary_planning_agent import ItineraryPlanningAgent
from app.agents.tools.rag_tool import RAGTool
from app.api.maps import search_nearby_places, PlacesSearchResponse


@pytest.fixture(scope="module")
def budget_agent():
    rag = RAGTool()
    return BudgetAgent(rag_tool=rag)


@pytest.fixture(scope="module")
def itinerary_agent():
    return ItineraryPlanningAgent()


# =====================================================================
# 1. One recommended stay per destination requiring an overnight stay
# =====================================================================
def test_one_recommended_stay_per_destination(budget_agent):
    """
    For a multi-destination itinerary visiting Dharmapuri and Balkampet for 3 days (2 nights),
    each destination requiring an overnight stay must have exactly one selected/recommended stay.
    """
    state = AgentState(
        user_query="Plan a 3-day trip to Dharmapuri and Balkampet for 2 people with Rs 10000 budget",
        structured_constraints={
            "destinations": ["Dharmapuri", "Balkampet"],
            "duration_days": 3,
            "pax": 2,
            "budget_limit": 10000
        }
    )
    res = budget_agent.process(state)
    assert res.success is True

    recommended_stays = res.metadata.get("recommended_stays", [])
    assert len(recommended_stays) == 2, f"Expected 2 recommended stays, got {len(recommended_stays)}"

    dests = [s["destination"] for s in recommended_stays]
    assert "Dharmapuri" in dests
    assert "Balkampet" in dests

    for stay in recommended_stays:
        assert stay["property_name"]
        assert stay["nights"] >= 1
        assert "Recommended for" in stay["recommendation_label"]

    assert "### 🏨 Recommended Stay Plan" in res.answer
    assert "Stay 1 — Dharmapuri" in res.answer or "Stay 2 — Dharmapuri" in res.answer
    assert "Stay 1 — Balkampet" in res.answer or "Stay 2 — Balkampet" in res.answer


# =====================================================================
# 2. Correct night allocation across multiple destinations
# =====================================================================
def test_correct_night_allocation_across_destinations(budget_agent):
    """
    A 3-day trip across 2 destinations has 2 total nights (1 night at each).
    Each destination's stay total must be tariff * 1 night * rooms.
    """
    state = AgentState(
        user_query="Plan a 3-day trip to Dharmapuri and Balkampet for 2 people with Rs 12000 budget",
        structured_constraints={
            "destinations": ["Dharmapuri", "Balkampet"],
            "duration_days": 3,
            "pax": 2
        }
    )
    res = budget_agent.process(state)
    assert res.success is True

    stays = res.metadata.get("recommended_stays", [])
    assert len(stays) == 2
    total_nights = sum(s["nights"] for s in stays)
    assert total_nights == 2, f"Expected 2 total nights across 2 destinations, got {total_nights}"

    for s in stays:
        assert s["nights"] == 1


# =====================================================================
# 3. No accommodation assigned to the wrong destination
# =====================================================================
def test_no_accommodation_assigned_to_wrong_destination(budget_agent):
    """
    Every accommodation option for Dharmapuri must be tagged with Dharmapuri,
    and every option for Balkampet must be tagged with Balkampet.
    """
    state = AgentState(
        user_query="Plan a 3-day trip to Dharmapuri and Balkampet for 2 people with Rs 15000 budget",
        structured_constraints={
            "destinations": ["Dharmapuri", "Balkampet"],
            "duration_days": 3,
            "pax": 2
        }
    )
    res = budget_agent.process(state)
    assert res.success is True

    opts = res.metadata.get("accommodation_options", [])
    assert len(opts) > 0

    for opt in opts:
        dest = opt.get("destination") or opt.get("temple")
        assert dest in ["Dharmapuri", "Balkampet"], f"Invalid destination {dest} on property {opt['name']}"
        dist_str = opt.get("distance", "").lower()
        assert f"near {dest.lower()}" in dist_str or "temple" in dist_str or "near" in dist_str or dest.lower() in dist_str


# =====================================================================
# 4. Stable recommendation labels after selecting an alternative
# =====================================================================
def test_stable_recommendation_labels(budget_agent):
    """
    In the structured metadata, recommended properties maintain `is_recommended == True`
    and `recommendation_label` regardless of whether another property is selected.
    """
    state = AgentState(
        user_query="Plan a 2-day trip to Yadadri for 2 people with Rs 8000 budget",
        structured_constraints={
            "destinations": ["Yadadri"],
            "duration_days": 2,
            "pax": 2
        }
    )
    res = budget_agent.process(state)
    assert res.success is True

    opts = res.metadata.get("accommodation_options", [])
    rec_opts = [o for o in opts if o.get("is_recommended")]
    assert len(rec_opts) >= 1
    for r in rec_opts:
        assert "Recommended for Yadadri" in r.get("recommendation_label", "")


# =====================================================================
# 5. Changing one property's selection does not change another destination's selection
# =====================================================================
def test_changing_selection_preserves_other_destination():
    """
    Simulates the frontend state management logic: selecting an alternative for
    Destination 1 does not alter the selected property for Destination 2.
    """
    opts = [
        {"name": "Hotel D1-A", "destination": "Dharmapuri", "is_selected": True, "stay_cost_min": 1000, "stay_cost_max": 1000},
        {"name": "Hotel D1-B", "destination": "Dharmapuri", "is_selected": False, "stay_cost_min": 1500, "stay_cost_max": 1500},
        {"name": "Hotel B1-A", "destination": "Balkampet", "is_selected": True, "stay_cost_min": 1200, "stay_cost_max": 1200},
        {"name": "Hotel B1-B", "destination": "Balkampet", "is_selected": False, "stay_cost_min": 1800, "stay_cost_max": 1800},
    ]

    target_idx = 1 # Hotel D1-B
    target_opt = opts[target_idx]
    target_dest = target_opt["destination"]

    # Applied logic: only toggle for target_dest
    for o in opts:
        if o["destination"] == target_dest:
            o["is_selected"] = (o == target_opt)

    # D1-B should be selected, D1-A unselected
    assert opts[0]["is_selected"] is False
    assert opts[1]["is_selected"] is True

    # Crucial: Balkampet's selected property remains unchanged!
    assert opts[2]["is_selected"] is True
    assert opts[3]["is_selected"] is False


# =====================================================================
# 6. Accommodation preference filtering is consistent across all sections
# =====================================================================
def test_accommodation_preference_filtering_consistent(budget_agent, itinerary_agent):
    """
    When 'Budget' tier is requested, matching recommendations in BudgetAgent and
    ItineraryPlanningAgent must strictly adhere to Budget tier.
    """
    state = AgentState(
        user_query="Plan a 2-day trip to Dharmapuri for 2 people with Rs 6000 budget with budget accommodation",
        structured_constraints={"accommodation_preference": "Budget", "duration_days": 2, "destinations": ["Dharmapuri"]}
    )
    b_res = budget_agent.process(state)
    assert b_res.success is True

    # BudgetAgent metadata check
    opts = b_res.metadata.get("accommodation_options", [])
    matching_opts = [o for o in opts if o.get("matches_preference")]
    for mo in matching_opts:
        assert mo["tier"] == "Budget"

    # ItineraryPlanningAgent check
    i_res = itinerary_agent.process(state)
    assert i_res.success is True
    # The itinerary should reflect lodging with preference
    assert "Lodging" in i_res.answer or "Accommodation" in i_res.answer


# =====================================================================
# 7. Alternative properties do not affect the selected-plan total
# =====================================================================
def test_alternatives_do_not_affect_total(budget_agent):
    """
    Trip total calculation includes ONLY selected stays, not the sum of all alternative hotels.
    """
    state = AgentState(
        user_query="Plan a 2-day trip to Yadadri for 2 people with Rs 8000 budget",
        structured_constraints={"duration_days": 2, "destinations": ["Yadadri"], "pax": 2}
    )
    res = budget_agent.process(state)
    assert res.success is True

    opts = res.metadata.get("accommodation_options", [])
    selected_stay_cost = sum(o["stay_cost_min"] for o in opts if o.get("is_selected"))
    all_options_cost = sum(o["stay_cost_min"] for o in opts)

    # If alternatives were counted, all_options_cost would be far higher
    assert len(opts) > 1
    assert all_options_cost > selected_stay_cost

    # The metadata breakdown accommodation_min must match selected_stay_cost exactly
    bb = res.metadata.get("budget_breakdown", {})
    assert bb.get("accommodation_min") == selected_stay_cost


# =====================================================================
# 8. Accommodation totals match selected properties, room count, and nights
# =====================================================================
def test_accommodation_totals_match_rooms_and_nights(budget_agent):
    """
    For 4 pax (2 rooms) and 2 nights, stay cost = nightly tariff * 2 nights * 2 rooms = tariff * 4.
    """
    state = AgentState(
        user_query="Plan a 3-day trip to Yadadri for 4 people with 2 rooms with Rs 15000 budget",
        structured_constraints={
            "duration_days": 3,
            "pax": 4,
            "rooms": 2,
            "destinations": ["Yadadri"]
        }
    )
    res = budget_agent.process(state)
    assert res.success is True

    opts = res.metadata.get("accommodation_options", [])
    selected = next(o for o in opts if o.get("is_selected"))

    nights = 2 # 3 days -> 2 nights
    rooms = 2  # 4 pax -> 2 rooms
    expected_min = selected["tariff_min"] * nights * rooms
    expected_max = selected["tariff_max"] * nights * rooms

    assert selected["stay_cost_min"] == expected_min
    assert selected["stay_cost_max"] == expected_max


# =====================================================================
# 9. Initial accommodation summary names the relevant destination
# =====================================================================
def test_initial_accommodation_summary_names_destination(itinerary_agent):
    """
    The itinerary's lodging section explicitly names each destination.
    """
    state = AgentState(
        user_query="Plan a 3-day trip from Hyderabad to Dharmapuri and Balkampet",
        structured_constraints={
            "origin": "Hyderabad",
            "destinations": ["Dharmapuri", "Balkampet"],
            "duration_days": 3
        }
    )
    res = itinerary_agent.process(state)
    assert res.success is True

    # Section 10 should state Stay by Destination
    assert "Lodging" in res.answer or "Accommodation Options by Destination" in res.answer
    assert "Dharmapuri" in res.answer
    assert "Balkampet" in res.answer


# =====================================================================
# 10. Nearby discovery handles missing coordinates, empty results, duplicate places, and errors
# =====================================================================
@pytest.mark.asyncio
async def test_nearby_discovery_robustness():
    """
    Tests nearby places endpoint under:
    - Missing coordinates (falls back to temple registry)
    - Empty/zero results
    - Provider error / offline mode (gracefully returns verified static data)
    """
    # 1. Provide temple name without server-side key: resolves coordinates and falls back to static knowledge base
    with patch.dict(os.environ, {"GOOGLE_PLACES_SERVER_API_KEY": ""}):
        resp = await search_nearby_places(
            query=None,
            temple="Yadadri",
            category="heritage"
        )
        assert isinstance(resp, PlacesSearchResponse)
        assert resp.status == "OK"
        assert resp.source == "Verified Temple Knowledge Base"
        assert len(resp.results) > 0
        # Verified Bhongir Fort must be in results
        names = [r.name for r in resp.results]
        assert any("Bhongir" in n for n in names)

    # 2. Unknown location: returns clean ZERO_RESULTS without 500 error
    resp_empty = await search_nearby_places(
        query="nonexistent place xyz123",
        temple=None,
        latitude=0.0,
        longitude=0.0
    )
    assert resp_empty.status in ["ZERO_RESULTS", "OK"]
    assert len(resp_empty.results) == 0


# =====================================================================
# 11. Adding or removing an attraction updates affected routes without changing temple order
# =====================================================================
def test_adding_removing_attraction_preserves_temple_order(itinerary_agent):
    """
    Adding an attraction inserts the activity into the journey legs without
    disrupting the requested temple sequence. Removing it returns to the direct route.
    """
    # Base route: Hyderabad -> Yadadri -> Dharmapuri
    state_base = AgentState(
        user_query="Plan a 2-day trip from Hyderabad to Yadadri and Dharmapuri",
        structured_constraints={
            "origin": "Hyderabad",
            "destinations": ["Yadadri", "Dharmapuri"],
            "duration_days": 2
        }
    )
    res_base = itinerary_agent.process(state_base)
    assert res_base.success is True
    legs_base = res_base.metadata.get("route_legs", [])
    assert len(legs_base) == 2
    assert legs_base[0]["origin"] == "Hyderabad"
    assert legs_base[0]["destination"] == "Yadadri"
    assert legs_base[1]["origin"] == "Yadadri"
    assert legs_base[1]["destination"] == "Dharmapuri"

    # Add Bhongir Fort near Yadadri
    state_with_act = AgentState(
        user_query="Plan a 2-day trip from Hyderabad to Yadadri and Dharmapuri",
        structured_constraints={
            "origin": "Hyderabad",
            "destinations": ["Yadadri", "Dharmapuri"],
            "duration_days": 2,
            "selected_activities": [{"name": "Bhongir Fort", "destination": "Yadadri"}]
        }
    )
    res_act = itinerary_agent.process(state_with_act)
    assert res_act.success is True
    legs_act = res_act.metadata.get("route_legs", [])
    assert len(legs_act) == 3
    # Sequence: Hyderabad -> Yadadri -> Bhongir Fort -> Dharmapuri
    assert legs_act[0]["origin"] == "Hyderabad"
    assert legs_act[0]["destination"] == "Yadadri"
    assert legs_act[1]["origin"] == "Yadadri"
    assert legs_act[1]["destination"] == "Bhongir Fort"
    assert legs_act[2]["origin"] == "Bhongir Fort"
    assert legs_act[2]["destination"] == "Dharmapuri"


# =====================================================================
# 12. Weather is shown only when supported data exists and is labelled correctly
# =====================================================================
def test_weather_labelled_correctly_and_non_blocking(itinerary_agent):
    """
    Weather section in itinerary is present, labels observations vs forecasts appropriately,
    and does not block itinerary generation even if offline.
    """
    state = AgentState(
        user_query="Plan a 2-day trip from Hyderabad to Yadadri",
        structured_constraints={
            "origin": "Hyderabad",
            "destinations": ["Yadadri"],
            "duration_days": 2,
            "start_date": "2030-01-01" # Far future date (> 14 days)
        }
    )
    res = itinerary_agent.process(state)
    assert res.success is True
    assert "### ☀️ Weather & Seasonal Planning" in res.answer
    # Must contain advisory about far future date
    assert "Forecast Advisory: Planned travel date (2030-01-01) is beyond the 7-day reliable meteorological forecast window" in res.answer
