"""
PilgrimAI - Phase P Multi-Agent Integration Correction Regression Tests

Covers:
A. Budget constraint propagation (duration_days=2, budget_limit=5000, Yadadri)
B. Accommodation budget constraint propagation (accommodation_required=True)
C. Cross-temple weather threshold ("Which temples currently have temperatures above 27°C?")
D. Multi-temple current weather ("What are the current temperatures at Yadadri, Basara, Bhadrachalam and Vemulavada?")
E. Recommendation regression ("Recommend a temple where the temperature is around 25–30°C")
F. Static comparison regression ("Compare Yadadri and Basara accommodation.")
G. Static cross-temple aggregation regression ("Which temples are on a river bank?")
H. Temple information regression ("What are Yadadri temple timings?")
I. Navigation regression ("How far is Hyderabad from Yadadri?")
J. Emergency regression ("What emergency services are available at Yadadri?")
"""

import sys
from pathlib import Path
import pytest

# Ensure backend directory is in sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.state import AgentState
from app.agents.coordinator import MasterAgentCoordinator
from app.agents.router import AgentRouter
from app.agents.response_aggregator import ResponseAggregator
from app.agents.temple_information_agent import TempleInformationAgent
from app.agents.comparison_agent import ComparisonAgent
from app.agents.cross_temple_aggregation_agent import CrossTempleAggregationAgent
from app.agents.itinerary_planning_agent import ItineraryPlanningAgent
from app.agents.live_weather_agent import LiveWeatherAgent
from app.agents.budget_agent import BudgetAgent, extract_budget_parameters
from app.agents.live_navigation_agent import LiveNavigationAgent
from app.agents.emergency_agent import EmergencyAgent
from app.agents.recommendation_agent import RecommendationAgent


@pytest.fixture
def coordinator():
    router = AgentRouter()
    aggregator = ResponseAggregator()
    temple_info = TempleInformationAgent()
    comparison = ComparisonAgent()
    cross_temple = CrossTempleAggregationAgent()
    itinerary = ItineraryPlanningAgent()
    weather = LiveWeatherAgent()
    budget = BudgetAgent()
    navigation = LiveNavigationAgent()
    emergency = EmergencyAgent()
    recommendation = RecommendationAgent(weather_agent=weather)

    return MasterAgentCoordinator(
        router=router,
        aggregator=aggregator,
        temple_info_agent=temple_info,
        comparison_agent=comparison,
        cross_temple_agent=cross_temple,
        itinerary_agent=itinerary,
        live_weather_agent=weather,
        budget_agent=budget,
        live_navigation_agent=navigation,
        emergency_agent=emergency,
        recommendation_agent=recommendation
    )


# Test A: Budget Constraint Propagation
def test_budget_constraint_propagation(coordinator):
    query = "Plan a 2 day itinerary to Yadadri with a budget of ₹5000"
    state = AgentState(user_query=query, session_id="test_p_a")
    resp = coordinator.process(state)

    assert resp.success is True
    # Verify global structured constraints
    assert state.structured_constraints.get("duration_days") == 2
    assert state.structured_constraints.get("budget_limit") == 5000.0
    assert any(t.lower() == "yadadri" for t in state.structured_constraints.get("temples", []))

    # Check multi_intent intermediate execution
    mi_data = state.intermediate_results.get("multi_intent", {})
    assert mi_data.get("task_count", 0) >= 2

    intents = [t["intent"] for t in mi_data.get("tasks", [])]
    assert "itinerary_planning" in intents
    assert "budget" in intents

    # Verify BudgetAgent received duration=2 and budget_limit=5000
    assert "Duration: 2 day(s)" in resp.answer
    assert "User Budget Limit" in resp.answer or "5,000" in resp.answer
    assert resp.agent_name == "response_aggregator"


# Test B: Accommodation Budget Constraint Propagation
def test_accommodation_budget_constraint_propagation(coordinator):
    query = "Plan a 2 day trip to Yadadri under ₹5000 including accommodation"
    state = AgentState(user_query=query, session_id="test_p_b")
    resp = coordinator.process(state)

    assert resp.success is True
    assert state.structured_constraints.get("duration_days") == 2
    assert state.structured_constraints.get("budget_limit") == 5000.0
    assert state.structured_constraints.get("accommodation_required") is True

    # Check answer reflects 2 days and accommodation
    assert "Duration: 2 day(s)" in resp.answer
    assert "User Budget Limit" in resp.answer or "5,000" in resp.answer


# Test C: Cross-temple Weather Threshold Routing & Execution
def test_cross_temple_weather_threshold(coordinator):
    query = "Which temples currently have temperatures above 27°C?"
    state = AgentState(user_query=query, session_id="test_p_c")

    # Routing assertion
    route_decision = coordinator.router.route(query)
    assert route_decision.selected_agent == "live_weather"
    assert route_decision.intent == "weather"
    assert route_decision.selected_agent != "comparison"
    assert route_decision.selected_agent != "cross_temple_aggregation"

    # Execution assertion
    resp = coordinator.process(state)
    assert resp.success is True
    assert resp.agent_name == "live_weather"
    assert "Live Weather Filter" in resp.answer
    assert "above 27°C" in resp.answer
    assert resp.metadata.get("query_type") == "cross_temple_threshold"


# Test D: Multi-temple Current Weather Routing & Execution
def test_multi_temple_current_weather(coordinator):
    query = "What are the current temperatures at Yadadri, Basara, Bhadrachalam and Vemulavada?"
    state = AgentState(user_query=query, session_id="test_p_d")

    # Routing assertion
    route_decision = coordinator.router.route(query)
    assert route_decision.selected_agent == "live_weather"
    assert route_decision.intent == "weather"
    assert route_decision.selected_agent != "comparison"
    assert len(route_decision.metadata.get("detected_temples", [])) == 4

    # Execution assertion
    resp = coordinator.process(state)
    assert resp.success is True
    assert resp.agent_name == "live_weather"
    assert "Live Weather Report" in resp.answer
    assert resp.metadata.get("query_type") == "multi_temple_weather"
    assert len(resp.metadata.get("temples", [])) == 4


# Test E: Recommendation with Weather Regression
def test_recommendation_with_weather_regression(coordinator):
    query = "Recommend a temple where the temperature is around 25–30°C"
    state = AgentState(user_query=query, session_id="test_p_e")

    route_decision = coordinator.router.route(query)
    assert route_decision.selected_agent == "recommendation"
    assert route_decision.intent == "recommendation"

    resp = coordinator.process(state)
    assert resp.success is True
    assert resp.agent_name == "recommendation"
    assert "Live Weather Recommendations" in resp.answer or "Live Weather Recommendation" in resp.answer


# Test F: Static Comparison Regression
def test_static_comparison_regression(coordinator):
    query = "Compare Yadadri and Basara accommodation."
    state = AgentState(user_query=query, session_id="test_p_f")

    route_decision = coordinator.router.route(query)
    assert route_decision.selected_agent == "comparison"
    assert route_decision.intent == "comparison"

    resp = coordinator.process(state)
    assert resp.success is True
    assert resp.agent_name == "comparison"


# Test G: Static Cross-Temple Aggregation Regression
def test_static_cross_temple_aggregation_regression(coordinator):
    query = "Which temples are on a river bank?"
    state = AgentState(user_query=query, session_id="test_p_g")

    route_decision = coordinator.router.route(query)
    assert route_decision.selected_agent == "cross_temple_aggregation"
    assert route_decision.intent == "cross_temple_aggregation"

    resp = coordinator.process(state)
    assert resp.success is True
    assert resp.agent_name == "cross_temple_aggregation"


# Test H: Temple Information Grounding
def test_temple_information_grounding(coordinator):
    query = "What are Yadadri temple timings?"
    state = AgentState(user_query=query, session_id="test_p_h")

    route_decision = coordinator.router.route(query)
    assert route_decision.selected_agent == "temple_information"
    assert route_decision.intent == "temple_information"


# Test I: Navigation Regression
def test_navigation_regression(coordinator):
    query = "How far is Hyderabad from Yadadri?"
    state = AgentState(user_query=query, session_id="test_p_i")

    route_decision = coordinator.router.route(query)
    assert route_decision.selected_agent == "live_navigation"
    assert route_decision.intent == "live_navigation"


# Test J: Emergency Regression
def test_emergency_regression(coordinator):
    query = "What emergency services are available at Yadadri?"
    state = AgentState(user_query=query, session_id="test_p_j")

    route_decision = coordinator.router.route(query)
    assert route_decision.selected_agent == "emergency"
    assert route_decision.intent == "emergency"
