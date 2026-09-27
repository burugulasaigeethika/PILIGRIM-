"""
PilgrimAI - Tests for RecommendationAgent and System Integration.

Validates:
1. RecommendationAgent initialization and contract.
2. Basic open recommendation queries (neutral, balanced, no subjective 'best').
3. RAG-backed criteria recommendations (accommodation, wheelchair/accessibility).
4. Safe handling of missing or unrecorded information.
5. Absolute zero fabrication (no made-up prices, ratings, crowd levels, or weather).
6. Router classification for recommendation queries and inactive state handling.
7. MasterAgentCoordinator registration and routing.
8. AgentResponse data contract compatibility.
9. Multi-intent pipeline preservation and compatibility.
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
from app.agents.recommendation_agent import (
    RecommendationAgent,
    THEMATIC_TEMPLE_MAP
)
from app.agents.temple_information_agent import TempleInformationAgent
from app.agents.response_aggregator import ResponseAggregator
from app.agents.tools.rag_tool import RAGTool
from app.rag.completeness_validator import (
    CONFIRMED_AVAILABLE,
    CONFIRMED_UNAVAILABLE,
    INFORMATION_NOT_AVAILABLE
)


# =============================================================================
# 1. Initialization and Contract Tests
# =============================================================================

def test_recommendation_agent_initialization():
    agent = RecommendationAgent()
    assert agent.name == "recommendation"
    assert "grounded" in agent.description.lower() or "recommend" in agent.description.lower()
    assert agent.rag_tool is not None


def test_recommendation_agent_custom_rag_tool():
    mock_rag = MagicMock()
    mock_weather = MagicMock()
    agent = RecommendationAgent(rag_tool=mock_rag, weather_agent=mock_weather)
    assert agent.rag_tool is mock_rag
    assert agent.weather_agent is mock_weather


# =============================================================================
# 2. Basic Open Recommendation Query (Neutral, No Subjective "Best")
# =============================================================================

def test_recommendation_agent_open_recommendation():
    agent = RecommendationAgent()
    state = AgentState(user_query="Which temple should I visit?")
    response = agent.execute(state)

    assert response.success is True
    assert response.agent_name == "recommendation"
    assert len(response.answer) > 50
    # Must not claim any single temple is objectively superior or 'the best'
    assert "is the best temple" not in response.answer.lower()
    assert "number one" not in response.answer.lower()
    # Must offer categories/themes to help user choose
    assert "deity" in response.answer.lower() or "pilgrimage" in response.answer.lower() or "preference" in response.answer.lower()
    assert response.metadata.get("recommendation_type") == "open_guidance"


# =============================================================================
# 3. RAG-Backed Facility Recommendations (Verified Accommodation & Accessibility)
# =============================================================================

def test_recommendation_agent_accommodation():
    agent = RecommendationAgent()
    state = AgentState(user_query="Suggest a temple with accommodation.")
    response = agent.execute(state)

    assert response.success is True
    assert response.agent_name == "recommendation"
    # Accommodation should recommend temples with confirmed accommodation
    assert len(response.sources) > 0
    # Verified temples known to have cottages/rooms
    assert any(temple in response.answer for temple in ["Yadadri", "Srisailam", "Vemulawada", "Basara", "Bhadrachalam"])
    assert "accommodation" in response.metadata.get("matched_criteria", [])


def test_recommendation_agent_accessibility():
    agent = RecommendationAgent()
    state = AgentState(user_query="Which temple has facilities for accessibility?")
    response = agent.execute(state)

    assert response.success is True
    assert response.agent_name == "recommendation"
    assert ("wheelchair" in response.answer.lower() or "ramp" in response.answer.lower() or "accessibility" in response.answer.lower())
    assert "accessibility" in response.metadata.get("matched_criteria", [])


# =============================================================================
# 4. Safe Handling of Missing Information
# =============================================================================

def test_recommendation_agent_missing_information_safe():
    mock_rag = MagicMock()
    # Return empty / unrecorded for facilities
    mock_rag.get_temple_category_data.return_value = {}
    mock_rag.get_registered_temples.return_value = ["Yadadri", "Basara"]
    agent = RecommendationAgent(rag_tool=mock_rag)

    state = AgentState(user_query="Suggest a temple with helipad facility.")
    response = agent.execute(state)

    assert response.success is True
    assert response.agent_name == "recommendation"
    # Safe handling: either explains lack of verified matches or provides grounded response without failing
    assert len(response.answer) > 0


# =============================================================================
# 5. Zero Fabrication (No Invented Prices, Ratings, Reviews, or Weather)
# =============================================================================

def test_recommendation_agent_no_fabrication():
    agent = RecommendationAgent()
    state = AgentState(user_query="Suggest the most highly rated 5 star temple with cheap luxury suites.")
    response = agent.execute(state)

    assert response.success is True
    # Must not claim 5-star ratings or invent star reviews
    assert "5-star" not in response.answer
    assert "5 star rating" not in response.answer.lower()
    assert "rated 4." not in response.answer.lower()
    assert "star hotel" not in response.answer.lower()


def test_recommendation_agent_weather_filter_without_fabrication():
    mock_weather = MagicMock()
    # Return mock weather for Yadadri: 28C (matches 25-30C)
    mock_weather.get_weather.side_effect = lambda t: (
        {"temperature": 28.0, "condition": "Partly Cloudy", "city": "Yadagirigutta"}
        if t == "Yadadri"
        else {"temperature": 38.0, "condition": "Hot", "city": "Khammam"}
    )

    agent = RecommendationAgent(weather_agent=mock_weather)
    state = AgentState(user_query="Recommend a temple where the temperature is around 25-30°C.")
    response = agent.execute(state)

    assert response.success is True
    assert "Yadadri" in response.answer
    assert "28" in response.answer


def test_recommendation_agent_weather_unavailable_safe():
    mock_weather = MagicMock()
    mock_weather.get_weather.return_value = None  # Live API unavailable

    agent = RecommendationAgent(weather_agent=mock_weather)
    state = AgentState(user_query="Recommend a temple where the temperature is around 25-30°C.")
    response = agent.execute(state)

    assert response.success is True
    # Must state live weather is unavailable and not fabricate temperatures
    assert "live weather" in response.answer.lower() or "temperature data is currently unavailable" in response.answer.lower()


# =============================================================================
# 6. Router Classification Tests
# =============================================================================

@pytest.mark.parametrize("query", [
    "Suggest a temple with accommodation.",
    "Which temple should I visit?",
    "Suggest temples suitable for my requirements.",
    "Which temple has the facilities I need?",
    "Recommend a temple based on these requirements.",
    "Where should I go?",
    "Which temple suits me?",
    "Recommend a temple where the temperature is around 25-30°C."
])
def test_recommendation_router_classification(query):
    router = AgentRouter(active_agents={"temple_information", "recommendation"})
    decision = router.route(query)
    assert decision.intent == "recommendation"
    assert decision.selected_agent == "recommendation"
    assert decision.confidence >= 0.90


def test_recommendation_router_inactive_agent():
    router = AgentRouter(active_agents={"temple_information"})
    decision = router.route("Suggest a temple with accommodation.")
    assert decision.intent == "recommendation"
    assert decision.selected_agent == "none"
    assert "not active" in decision.reason


# =============================================================================
# 7. MasterAgentCoordinator Registration and Execution
# =============================================================================

def test_coordinator_recommendation_registration():
    router = AgentRouter()
    aggregator = ResponseAggregator()
    temple_info = TempleInformationAgent()
    recommendation = RecommendationAgent()

    coordinator = MasterAgentCoordinator(
        router=router,
        aggregator=aggregator,
        temple_info_agent=temple_info,
        recommendation_agent=recommendation
    )

    assert "recommendation" in coordinator.agents
    assert coordinator.agents["recommendation"] is recommendation
    assert "recommendation" in coordinator.router.active_agents

    state = AgentState(user_query="Suggest a temple with accommodation.")
    response = coordinator.process(state)

    assert response.success is True
    assert response.agent_name == "recommendation"
    assert len(response.sources) > 0


# =============================================================================
# 8. AgentResponse Structure Compatibility
# =============================================================================

def test_recommendation_response_structure_compatibility():
    agent = RecommendationAgent()
    state = AgentState(user_query="Suggest a temple with parking.")
    response = agent.execute(state)

    assert isinstance(response, AgentResponse)
    assert isinstance(response.success, bool)
    assert isinstance(response.agent_name, str)
    assert isinstance(response.answer, str)
    assert isinstance(response.sources, list)
    assert isinstance(response.metadata, dict)
    assert response.latency_ms is not None and response.latency_ms >= 0.0


# =============================================================================
# 9. Multi-Intent Compatibility Verification
# =============================================================================

def test_existing_multi_intent_queries_preserved():
    router = AgentRouter(active_agents={
        "temple_information", "itinerary_planning", "budget", "live_weather",
        "live_navigation", "emergency", "recommendation"
    })

    # Test 1: Plan trip + budget + weather (all existing intents must route to multi_intent)
    decision1 = router.route("Plan a 2-day trip to Yadadri under ₹5000 and check the weather.")
    assert decision1.intent == "multi_intent"

    # Test 2: Plan trip + budget + route
    decision2 = router.route("Plan a 2-day trip to Yadadri under ₹5000, check the weather, and tell me the route from Hyderabad.")
    assert decision2.intent == "multi_intent"

    # Test 3: Plan trip + weather
    decision3 = router.route("Plan a visit to Yadadri and check the weather forecast.")
    assert decision3.intent == "multi_intent"


def test_conjoined_recommendation_routes_to_multi_intent():
    router = AgentRouter(active_agents={
        "temple_information", "live_weather", "recommendation"
    })
    # Conjoined recommendation + weather should be detected by multi-intent
    decision = router.route("Suggest a temple with accommodation and check the weather.")
    assert decision.intent == "multi_intent"


# =============================================================================
# 10. Bug 1 & Bug 2 Specific Regressions
# =============================================================================

def test_weather_based_recommendation_with_mock():
    """Bug 1: Recommend a temple where the temperature is around 25–30°C."""
    mock_weather_agent = MagicMock()
    mock_coord_reg = MagicMock()
    
    class FakeCoord:
        def __init__(self, lat, lon, display_name):
            self.latitude = lat
            self.longitude = lon
            self.display_name = display_name
            
    mock_coord_reg.get_all_coordinates.return_value = {
        "Yadadri": FakeCoord(17.5898, 78.9482, "Yadadri (Sri Lakshmi Narasimha Swamy)"),
        "Basara": FakeCoord(18.8778, 77.9547, "Basara (Gnana Saraswathi)"),
        "Warangal": FakeCoord(17.9784, 79.6000, "Thousand Pillar Temple")
    }
    mock_weather_agent.coordinate_registry = mock_coord_reg
    
    # Mock open-meteo responses: Yadadri 26°C (in range), Basara 28°C (in range), Warangal 35°C (out of range)
    def fake_fetch(lat, lon, key):
        if "17.5898" in key:
            return {"current": {"temperature_2m": 26.0, "weather_code": 0}}, False, "2026-09-26T15:00:00Z"
        elif "18.8778" in key:
            return {"current": {"temperature_2m": 28.0, "weather_code": 1}}, False, "2026-09-26T15:00:00Z"
        else:
            return {"current": {"temperature_2m": 35.0, "weather_code": 0}}, False, "2026-09-26T15:00:00Z"
            
    mock_weather_agent._fetch_open_meteo.side_effect = fake_fetch
    
    agent = RecommendationAgent(weather_agent=mock_weather_agent)
    state = AgentState(user_query="Recommend a temple where the temperature is around 25–30°C")
    resp = agent.execute(state)
    
    assert resp.success is True
    assert "Yadadri" in resp.answer
    assert "Basara" in resp.answer
    assert "35" not in resp.answer
    assert "26" in resp.answer
    assert "28" in resp.answer
    assert resp.metadata["matched_temples"] == [
        "Yadadri (Sri Lakshmi Narasimha Swamy)",
        "Basara (Gnana Saraswathi)"
    ]


def test_multi_intent_itinerary_and_budget_variants():
    """Bug 2: Verify all 5 query variants route to multi_intent and decompose correctly."""
    from app.agents.multi_intent_pipeline import SequentialMultiIntentPipeline
    
    router = AgentRouter(active_agents={
        "temple_information", "itinerary_planning", "budget", "live_weather",
        "live_navigation", "emergency", "recommendation"
    })
    pipeline = SequentialMultiIntentPipeline(router=router)
    
    queries_2_tasks = [
        "plan a 2 day itinerary to yadadri with budget 5000",
        "plan a 2 day trip to yadadri under 5000",
        "plan a 2 day itinerary to yadadri under a budget of 5000",
        "plan a 2 day trip to yadadri with a budget of ₹5000",
    ]
    
    for q in queries_2_tasks:
        decision = router.route(q)
        assert decision.intent == "multi_intent", f"Failed router intent for: {q}"
        
        tasks = pipeline.decompose_query(q)
        assert len(tasks) == 2, f"Failed task count for: {q}. Got tasks: {tasks}"
        assert tasks[0]["intent"] == "itinerary_planning", f"Task 0 failed for: {q}"
        assert tasks[1]["intent"] == "budget", f"Task 1 failed for: {q}"
        
    q5 = "plan a 2 day itinerary to yadadri under ₹5000 and check the weather"
    decision5 = router.route(q5)
    assert decision5.intent == "multi_intent"
    tasks5 = pipeline.decompose_query(q5)
    assert len(tasks5) == 3, f"Expected 3 tasks, got: {tasks5}"
    assert tasks5[0]["intent"] == "itinerary_planning"
    assert tasks5[1]["intent"] == "budget"
    assert tasks5[2]["intent"] == "weather"
    assert tasks5[2]["target_agent"] in ["live_weather", "LiveWeatherAgent"]
