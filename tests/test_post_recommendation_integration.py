"""
PilgrimAI - Post-Recommendation Integration Test Suite
Validates all test requirements A through H specified in post-recommendation integration bug fix.
"""

import sys
from pathlib import Path
import pytest
from unittest.mock import MagicMock

# Ensure backend directory is in sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState, AgentResponse, AgentRouteDecision
from app.agents.router import AgentRouter
from app.agents.coordinator import MasterAgentCoordinator
from app.agents.response_aggregator import ResponseAggregator
from app.agents.temple_information_agent import TempleInformationAgent
from app.agents.comparison_agent import ComparisonAgent
from app.agents.cross_temple_aggregation_agent import CrossTempleAggregationAgent
from app.agents.itinerary_planning_agent import ItineraryPlanningAgent
from app.agents.live_weather_agent import LiveWeatherAgent
from app.agents.budget_agent import BudgetAgent
from app.agents.live_navigation_agent import LiveNavigationAgent
from app.agents.recommendation_agent import RecommendationAgent


def test_requirement_a_recommendation_live_weather():
    """Requirement A: Temperature-based recommendation using live weather."""
    mock_weather = MagicMock()
    mock_coord_reg = MagicMock()

    class FakeCoord:
        def __init__(self, lat, lon, display_name):
            self.latitude = lat
            self.longitude = lon
            self.display_name = display_name

    mock_coord_reg.get_all_coordinates.return_value = {
        "Yadadri": FakeCoord(17.5898, 78.9482, "Yadadri (Sri Lakshmi Narasimha Swamy)"),
        "Basara": FakeCoord(18.8778, 77.9547, "Basara (Gnana Saraswathi)"),
        "Kaleshwaram": FakeCoord(18.8144, 79.9077, "Kaleshwaram (Mukteshwara)")
    }
    mock_weather.coordinate_registry = mock_coord_reg

    def fake_fetch(lat, lon, key):
        if "17.5898" in key:
            return {"current": {"temperature_2m": 26.0, "weather_code": 0}}, False, "2026-09-26T15:00:00Z"
        elif "18.8778" in key:
            return {"current": {"temperature_2m": 27.5, "weather_code": 1}}, False, "2026-09-26T15:00:00Z"
        else:
            return {"current": {"temperature_2m": 35.0, "weather_code": 0}}, False, "2026-09-26T15:00:00Z"

    mock_weather._fetch_open_meteo.side_effect = fake_fetch

    rec_agent = RecommendationAgent(weather_agent=mock_weather)
    state = AgentState(user_query="Recommend a temple where the temperature is around 25–30°C")
    response = rec_agent.execute(state)

    assert response.success is True
    assert "Yadadri" in response.answer
    assert "26" in response.answer
    assert "Basara" in response.answer
    assert "27.5" in response.answer
    assert "35" not in response.answer
    assert "Kaleshwaram" not in response.answer
    assert "live observations" in response.answer.lower()
    assert response.metadata["matched_temples"] == [
        "Yadadri (Sri Lakshmi Narasimha Swamy)",
        "Basara (Gnana Saraswathi)"
    ]


def test_requirement_b_direct_weather():
    """Requirement B: 'What is the temperature at Yadadri?' routed to LiveWeatherAgent."""
    router = AgentRouter(active_agents={
        "temple_information", "itinerary_planning", "budget", "live_weather",
        "live_navigation", "recommendation"
    })
    decision = router.route("What is the temperature at Yadadri?")
    assert decision.intent == "weather"
    assert decision.selected_agent == "live_weather"


def test_requirement_c_multi_intent_itinerary_and_budget():
    """Requirement C: 'plan a 2 day itinerary to yadadri with budget 5000' routes to multi_intent."""
    router = AgentRouter(active_agents={
        "temple_information", "itinerary_planning", "budget", "live_weather",
        "live_navigation", "recommendation"
    })
    decision = router.route("plan a 2 day itinerary to yadadri with budget 5000")
    assert decision.intent == "multi_intent"


def test_requirement_d_multi_intent_itinerary_budget_weather():
    """Requirement D: 'plan a 2 day itinerary to yadadri under ₹5000 and check the weather'."""
    router = AgentRouter(active_agents={
        "temple_information", "itinerary_planning", "budget", "live_weather",
        "live_navigation", "recommendation"
    })
    decision = router.route("plan a 2 day itinerary to yadadri under ₹5000 and check the weather")
    assert decision.intent == "multi_intent"


def test_requirement_e_existing_recommendation_queries():
    """Requirement E: Existing recommendation queries remain RecommendationAgent."""
    router = AgentRouter(active_agents={
        "temple_information", "itinerary_planning", "budget", "live_weather",
        "live_navigation", "recommendation"
    })
    for q in ["which temple should I visit", "which temple suits me", "Suggest a temple with accommodation."]:
        decision = router.route(q)
        assert decision.intent == "recommendation", f"Failed for {q}"
        assert decision.selected_agent == "recommendation"


def test_requirement_f_existing_navigation():
    """Requirement F: 'How far is Hyderabad from Yadadri?' remains LiveNavigationAgent."""
    router = AgentRouter(active_agents={
        "temple_information", "itinerary_planning", "budget", "live_weather",
        "live_navigation", "recommendation"
    })
    decision = router.route("How far is Hyderabad from Yadadri?")
    assert decision.intent == "live_navigation"
    assert decision.selected_agent == "live_navigation"


def test_requirement_g_existing_temple_information():
    """Requirement G: 'What are Yadadri timings?' remains TempleInformationAgent."""
    router = AgentRouter(active_agents={
        "temple_information", "itinerary_planning", "budget", "live_weather",
        "live_navigation", "recommendation"
    })
    decision = router.route("What are Yadadri timings?")
    assert decision.intent == "temple_information"
    assert decision.selected_agent == "temple_information"


def test_requirement_h_existing_cross_temple_aggregation():
    """Requirement H: 'Which temples are on a river bank?' remains CrossTempleAggregationAgent."""
    router = AgentRouter(active_agents={
        "temple_information", "itinerary_planning", "budget", "live_weather",
        "live_navigation", "cross_temple_aggregation", "recommendation"
    })
    decision = router.route("Which temples are on a river bank?")
    assert decision.intent == "cross_temple_aggregation"
    assert decision.selected_agent == "cross_temple_aggregation"
