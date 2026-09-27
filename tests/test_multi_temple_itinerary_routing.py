"""
Phase N Post-Certification Regression Tests:
Multi-Temple Itinerary vs Comparison Routing Precedence

Verifies:
1. Multi-temple itinerary routes to ItineraryPlanningAgent.
2. Multi-day multi-temple itinerary routes to ItineraryPlanningAgent.
3. Explicit comparison is preserved and routes to ComparisonAgent.
4. Specific category comparison (accommodation) routes to ComparisonAgent.
5. Implicit multi-temple comparison fallback (no comparison or itinerary keyword) routes to ComparisonAgent.
6. Non-standard spelling variant (itenary) behavior follows existing patterns.
7. Single-temple itinerary routing is preserved.
8. Multi-intent compound query (itinerary + food) routes to multi_intent.
"""

import sys
from pathlib import Path
import pytest

# Ensure backend directory is in sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.router import AgentRouter
from app.agents.state import AgentRouteDecision


@pytest.fixture(scope="module")
def active_router():
    """Router with all certified specialist agents registered as active."""
    return AgentRouter(
        active_agents={
            "temple_information",
            "comparison",
            "cross_temple_aggregation",
            "itinerary_planning"
        }
    )


def test_1_multi_temple_itinerary_routing(active_router):
    """Verify that a multi-temple itinerary query routes to ItineraryPlanningAgent."""
    decision = active_router.route("Plan an itinerary for Basara and Vemulawada.")

    assert isinstance(decision, AgentRouteDecision)
    assert decision.intent == "itinerary_planning"
    assert decision.selected_agent == "itinerary_planning"
    assert set(decision.metadata.get("detected_temples", [])) == {"Basara", "Vemulavada"}


def test_2_multi_day_itinerary_routing(active_router):
    """Verify that a multi-day, multi-temple itinerary query routes to ItineraryPlanningAgent."""
    decision = active_router.route("Plan a 2-day itinerary for Birla Mandir and Ujjaini.")

    assert isinstance(decision, AgentRouteDecision)
    assert decision.intent == "itinerary_planning"
    assert decision.selected_agent == "itinerary_planning"
    assert set(decision.metadata.get("detected_temples", [])) == {"Birla Mandir", "Ujjaini"}


def test_3_explicit_comparison_preserved(active_router):
    """Verify that explicit comparison query routes to ComparisonAgent."""
    decision = active_router.route("Compare Basara and Vemulawada.")

    assert isinstance(decision, AgentRouteDecision)
    assert decision.intent == "comparison"
    assert decision.selected_agent == "comparison"


def test_4_accommodation_comparison_preserved(active_router):
    """Verify that category-specific comparison query routes to ComparisonAgent."""
    decision = active_router.route("Compare accommodation between Srisailam and Bhadrachalam.")

    assert isinstance(decision, AgentRouteDecision)
    assert decision.intent == "comparison"
    assert decision.selected_agent == "comparison"


def test_5_implicit_multi_temple_comparison_fallback(active_router):
    """Verify that 2+ temples without comparison or itinerary keywords falls back to ComparisonAgent."""
    decision = active_router.route("Basara and Vemulawada facilities")

    assert isinstance(decision, AgentRouteDecision)
    assert decision.intent == "comparison"
    assert decision.selected_agent == "comparison"
    assert set(decision.metadata.get("detected_temples", [])) == {"Basara", "Vemulavada"}


def test_6_itinerary_spelling_variant(active_router):
    """
    Verify behavior for non-standard spelling variant 'itenary'.
    Since 'itenary' is not in existing _itinerary_patterns, the router
    safely falls back to comparison rather than crashing or guessing.
    """
    decision = active_router.route("itenary of 2 days to visit Birla Mandir and Ujjaini")

    assert isinstance(decision, AgentRouteDecision)
    # Existing pattern set does not include misspelling 'itenary', so 2 temples fall back to comparison
    assert decision.intent == "comparison"
    assert decision.selected_agent == "comparison"


def test_7_single_temple_itinerary_regression(active_router):
    """Verify single-temple itinerary query continues routing to ItineraryPlanningAgent."""
    decision = active_router.route("Plan a one-day visit to Yadadri.")

    assert isinstance(decision, AgentRouteDecision)
    assert decision.intent == "itinerary_planning"
    assert decision.selected_agent == "itinerary_planning"
    assert decision.metadata.get("detected_temples") == ["Yadadri"]


def test_8_multi_intent_itinerary_with_food(active_router):
    """Verify compound query (itinerary + prasadam/food) routes to multi_intent."""
    decision = active_router.route("Plan a 2-day pilgrimage covering Basara and Vemulawada including food.")

    assert isinstance(decision, AgentRouteDecision)
    assert decision.intent == "multi_intent"
    assert decision.selected_agent == "none"
    sub_intents = decision.metadata.get("sub_intents", [])
    assert "itinerary" in sub_intents
    assert "prasadam" in sub_intents
