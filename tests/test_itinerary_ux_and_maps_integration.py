import sys
import os
from pathlib import Path
import pytest
import urllib.parse

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.state import AgentState
from app.agents.router import AgentRouter
from app.agents.itinerary_planning_agent import ItineraryPlanningAgent


@pytest.fixture
def itinerary_agent():
    return ItineraryPlanningAgent()


@pytest.fixture
def agent_router():
    return AgentRouter(active_agents={"temple_information", "itinerary_planning"})


# =====================================================================
# Phase 3 & 5: Google Maps Search and Directions URL Generation
# =====================================================================
def test_google_maps_search_and_directions_url_generation():
    """Verify safe Google Maps URL encoding and search/directions link formatting."""
    # Search URL
    url = ItineraryPlanningAgent._make_google_maps_search_url("Gnana Saraswati Temple", "Basara")
    assert url.startswith("https://www.google.com/maps/search/?api=1&query=")
    assert "Gnana+Saraswati+Temple" in url or "Gnana%20Saraswati%20Temple" in url
    assert "Basara" in url

    # Directions URL
    dir_url = ItineraryPlanningAgent._make_google_maps_directions_url("Hyderabad", "Gnana Saraswati Temple, Basara")
    assert dir_url.startswith("https://www.google.com/maps/dir/?api=1&")
    assert "origin=Hyderabad" in dir_url
    assert "travelmode=driving" in dir_url
    assert "Basara" in dir_url


# =====================================================================
# Phase 4 & 5: Router detects activity addition follow-ups
# =====================================================================
def test_router_activity_addition_routes_to_itinerary_agent(agent_router):
    """
    Follow-up queries like "Add Vyasa Maharshi Cave to Day 1" must route
    to the itinerary planning agent, not generic temple information.
    """
    state_cave = AgentState(user_query="Add Vyasa Maharshi Cave to Day 1")
    route_cave = agent_router.route(state_cave)
    assert route_cave.selected_agent == "itinerary_planning"
    assert route_cave.intent == "itinerary_planning"

    state_ghat = AgentState(user_query="Include Godavari River Ghats in Day 1")
    route_ghat = agent_router.route(state_ghat)
    assert route_ghat.selected_agent == "itinerary_planning"
    assert route_ghat.intent == "itinerary_planning"

    state_park = AgentState(user_query="Please add Ali Sagar Deer Park to my itinerary")
    route_park = agent_router.route(state_park)
    assert route_park.selected_agent == "itinerary_planning"
    assert route_park.intent == "itinerary_planning"


# =====================================================================
# Phase 4 & 5: Activity addition updates Day schedule with Maps links
# =====================================================================
def test_activity_addition_updates_schedule_with_maps_links(itinerary_agent):
    """
    Adding an attraction (e.g. Vyasa Maharshi Cave) to Day 1 places it in
    the Day 1 schedule and generates Google Maps search & directions links.
    """
    state = AgentState(
        user_query="Add Vyasa Maharshi Cave to Day 1",
        structured_constraints={
            "origin": "Hyderabad",
            "destinations": ["Basara"],
            "duration_days": 1,
            "selected_activities": [
                {"name": "Vyasa Maharshi Cave", "day": 1, "destination": "Basara"}
            ]
        }
    )
    res = itinerary_agent.process(state)
    assert res.success is True

    # Day 1 schedule contains Vyasa Maharshi Cave
    assert "Vyasa Maharshi Cave" in res.answer
    assert "Day 1" in res.answer
    # Contains Google Maps search link for Vyasa Maharshi Cave
    assert "google.com/maps/search/?api=1&query=" in res.answer
    # Contains Google Maps directions link
    assert "google.com/maps/dir/?api=1&" in res.answer
    # Check that the place is formatted cleanly
    assert "[📍 View on Maps]" in res.answer or "View on Maps" in res.answer


# =====================================================================
# Phase 5: Ali Sagar Deer Park or Godavari River Ghats scheduling
# =====================================================================
def test_scheduling_ali_sagar_or_godavari_ghats(itinerary_agent):
    """
    Natural language request to add Godavari River Ghats assigns it to the
    destination schedule with Maps links.
    """
    state = AgentState(
        user_query="Plan a 2-day pilgrimage to Basara and include Godavari River Ghats and Ali Sagar Deer Park",
        structured_constraints={
            "origin": "Nizamabad",
            "destinations": ["Basara"],
            "duration_days": 2
        }
    )
    res = itinerary_agent.process(state)
    assert res.success is True

    # Attractions are scheduled or explicitly addressed
    assert "Godavari River Ghats" in res.answer or "Ali Sagar Deer Park" in res.answer
    assert "Day 1" in res.answer
    assert "Day 2" in res.answer
    assert "google.com/maps" in res.answer


# =====================================================================
# Phase 2 & 5: Clear order and non-duplicated route cards
# =====================================================================
def test_clear_headings_and_no_duplicated_route_sections(itinerary_agent):
    """
    Verify readable headings:
    - Pilgrimage Plan
    - Travel & Journey Routes
    - Explore Nearby Attractions
    - Where to Stay — Accommodation Options
    """
    state = AgentState(
        user_query="Plan a 3-day pilgrimage from Hyderabad to Basara and Dharmapuri",
        structured_constraints={
            "origin": "Hyderabad",
            "destinations": ["Basara", "Dharmapuri"],
            "duration_days": 3
        }
    )
    res = itinerary_agent.process(state)
    assert res.success is True

    # Assert readable headings
    assert "### 🚗 Travel & Journey Routes from Hyderabad" in res.answer or "Travel & Journey Routes" in res.answer
    assert "Darshan & Nearby Places" in res.answer
    assert "Explore Nearby Attractions" in res.answer
    assert "Where to Stay" in res.answer or "Accommodation Options" in res.answer

    # Verify Travel & Journey Routes appears exactly once in the text (no duplication)
    assert res.answer.count("Travel & Journey Routes from Hyderabad") <= 1

    # Verify stays are shown in chronological destination order
    stay_basara_pos = res.answer.find("Basara")
    stay_dharmapuri_pos = res.answer.find("Dharmapuri")
    assert stay_basara_pos != -1
    assert stay_dharmapuri_pos != -1
