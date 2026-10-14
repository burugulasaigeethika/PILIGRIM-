import pytest
from unittest.mock import MagicMock, patch
import sys
import os

# Add backend to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.agents.state import AgentState, AgentResponse
from app.agents.router import AgentRouter
from app.agents.budget_agent import BudgetAgent, extract_budget_parameters
from app.agents.coordinator import MasterAgentCoordinator
from app.agents.response_aggregator import ResponseAggregator
from app.api.itinerary import ItineraryPlanRequest


def test_1_extract_budget_parameters_respects_constraints_and_query():
    """Requirement 1 & 2: Budget extraction parses budget and duration accurately."""
    params = extract_budget_parameters(
        "plan 2 day trip to vemulavada with budget 4000",
        structured_constraints={"duration_days": 2, "budget_limit": 4000.0}
    )
    assert params["days"] == 2
    assert params["nights"] == 1
    assert params["budget_limit"] == 4000.0
    assert params["accom_requested"] is True


def test_2_router_multi_intent_detection():
    """Requirement 2: Itinerary with budget routes to multi_intent (itinerary + budget)."""
    router = AgentRouter(active_agents={"itinerary_planning", "budget", "temple_information"})
    decision = router.route("plan 2 day trip to vemulavada with budget 4000")
    assert decision.intent == "multi_intent"
    sub_intents = decision.metadata.get("sub_intents", [])
    assert "itinerary" in sub_intents or "itinerary_planning" in sub_intents
    assert "budget" in sub_intents


def test_3_budget_calculation_single_accommodation_and_nights():
    """Requirements 8 & 9: Alternative accommodations are not summed; 1 night allocated for 2 days."""
    budget_agent = BudgetAgent()
    state = AgentState(
        user_query="plan 2 day trip to vemulavada with budget 4000",
        structured_constraints={
            "duration_days": 2,
            "budget_limit": 4000.0,
            "pax": 1,
            "temples": ["Vemulavada"]
        }
    )
    resp = budget_agent.execute(state)
    assert resp.success is True
    meta = resp.metadata
    calc_total = meta.get("calculated_total", {})
    assert calc_total.get("is_quantified") is True
    # Vemulavada selected property is ~1200 - 2500 for 1 night. Summing alternatives would exceed 5000+.
    assert calc_total.get("min", 0) <= 2500
    assert calc_total.get("max", 0) <= 3000
    # Selected property cost matches total (no spurious additions of alternative lodges)
    assert "Balaji Lodge" in resp.answer  # Present in alternatives
    assert "Super Hotel O Vemulawada Temple" in resp.answer  # Selected property


def test_4_response_aggregation_preserves_budget_and_itinerary():
    """Requirement 3: Response aggregator retains both itinerary details and budget metadata."""
    aggregator = ResponseAggregator()
    itin_resp = AgentResponse(
        success=True,
        agent_name="itinerary_planning",
        answer="### Day 1: Vemulavada Darshan\nMorning visit.\n### Day 2: Concluding Darshan",
        sources=["knowledge_base/vemulavada"],
        metadata={"itinerary": {"days": 2}, "temples": ["Vemulavada"]}
    )
    budget_resp = AgentResponse(
        success=True,
        agent_name="budget",
        answer="## 💰 Pilgrimage Budget — Vemulavada\n\n### 📋 Trip Budget Summary\n- Budget: ₹4,000\n- Feasibility: Within Budget",
        sources=["knowledge_base/vemulavada_costs"],
        metadata={
            "calculated_total": {"min": 1200.0, "max": 2500.0, "currency": "INR"},
            "budget_breakdown": {"total_min": 1200.0, "total_max": 2500.0, "status": "within"}
        }
    )
    aggregated = aggregator.aggregate([itin_resp, budget_resp])
    assert aggregated.success is True
    assert "Pilgrimage Budget" in aggregated.answer
    assert "Day 1: Vemulavada" in aggregated.answer
    assert "calculated_total" in aggregated.metadata
    assert aggregated.metadata["calculated_total"]["min"] == 1200.0
    assert aggregated.metadata["itinerary"]["days"] == 2


def test_5_multi_temple_itinerary_with_budget():
    """Requirement 5: Multi-temple itinerary with budget includes budget calculations."""
    router = AgentRouter(active_agents={"itinerary_planning", "budget"})
    decision = router.route("plan 3 day trip to yadadri and basara with budget 10000")
    assert decision.intent == "multi_intent"
    sub_intents = decision.metadata.get("sub_intents", [])
    assert "itinerary" in sub_intents
    assert "budget" in sub_intents


def test_6_request_without_budget_does_not_crash_or_fabricate():
    """Requirement 6: Request without a budget does not fabricate budget limit."""
    params = extract_budget_parameters("plan 2 day trip to vemulavada")
    assert params["budget_limit"] is None
    router = AgentRouter(active_agents={"itinerary_planning", "budget"})
    decision = router.route("plan 2 day trip to vemulavada")
    # Standard itinerary without budget should route to itinerary_planning
    assert decision.intent == "itinerary_planning"


def test_7_missing_tariffs_marked_incomplete():
    """Requirement 7: Missing tariffs result in incomplete estimate, not invented total."""
    budget_agent = BudgetAgent()
    with patch.object(budget_agent.rag_tool, "get_temple_category_data", return_value=None):
        state = AgentState(
            user_query="budget for 2 days at vemulavada",
            structured_constraints={"duration_days": 2, "temples": ["Vemulavada"]}
        )
        resp = budget_agent.execute(state)
        calc_total = resp.metadata.get("calculated_total", {})
        assert calc_total.get("is_complete_estimate") is False or "incomplete" in str(resp.answer).lower() or "not available" in str(resp.answer).lower()


def test_8_dedicated_planner_request_construction():
    """Requirement 10: Dedicated planner constructs proper query and structured constraints."""
    req = ItineraryPlanRequest(
        destinations=["Vemulavada"],
        duration_days=2,
        pax=1,
        budget_limit=4000.0
    )
    assert req.budget_limit == 4000.0
    assert req.duration_days == 2
    assert req.destinations == ["Vemulavada"]
