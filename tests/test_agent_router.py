"""
Phase D - AgentRouter Certification Tests

Verifies deterministic routing against Phase A contracts:
1. Router initializes cleanly.
2. Yadadri factual query routes to TempleInformationAgent.
3. Dharmapuri factual query routes to TempleInformationAgent.
4. Case normalization yields identical routing decisions.
5. Explicit unsupported temple (Golden Temple) triggers unsupported rejection.
6. Ambiguous query lacking temple name triggers clarification.
7. Out-of-scope non-temple query triggers unsupported decision.
8. Empty / whitespace queries are handled safely.
9. Comparison intent is recognized without calling nonexistent ComparisonAgent.
10. Itinerary intent is recognized without calling nonexistent ItineraryPlanningAgent.
11. Multi-intent query triggers multi-intent handling without premature single-agent execution.
12. Determinism check (10 repeated runs yield 100% identical decisions).
13. Strict dependency boundary (zero raw database, reranker, or embedding imports).

Fast, deterministic in-memory tests — zero model / database dependencies.
"""

import sys
from pathlib import Path
import pytest

# Ensure backend is in sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.state import AgentRouteDecision
from app.agents.router import AgentRouter


@pytest.fixture(scope="module")
def router():
    return AgentRouter()


def test_1_router_initialization(router):
    """Verify AgentRouter initializes and exposes route() method."""
    assert router is not None
    assert hasattr(router, "route")


def test_2_yadadri_factual_routing(router):
    """Verify factual query for Yadadri routes to temple_information agent."""
    decision = router.route("What are the timings of Yadadri temple?")

    assert isinstance(decision, AgentRouteDecision)
    assert decision.selected_agent == "temple_information"
    assert decision.intent == "temple_information"
    assert decision.confidence >= 0.90
    assert decision.metadata.get("detected_temple") == "Yadadri"
    assert decision.metadata.get("available") is True


def test_3_dharmapuri_factual_routing(router):
    """Verify factual query for Dharmapuri routes to temple_information agent."""
    decision = router.route("What sevas are available at Dharmapuri temple?")

    assert isinstance(decision, AgentRouteDecision)
    assert decision.selected_agent == "temple_information"
    assert decision.intent == "temple_information"
    assert decision.metadata.get("detected_temple") == "Dharmapuri"
    assert "dharmapuri" in decision.reason.lower()


def test_4_case_normalization(router):
    """Verify case variations produce identical routing decisions."""
    d1 = router.route("WHAT ARE THE TIMINGS OF YADADRI TEMPLE?")
    d2 = router.route("what are the timings of yadadri temple")

    assert d1.selected_agent == d2.selected_agent == "temple_information"
    assert d1.intent == d2.intent == "temple_information"
    assert d1.confidence == d2.confidence
    assert d1.metadata.get("detected_temple") == d2.metadata.get("detected_temple") == "Yadadri"


def test_5_explicit_unsupported_temple(router):
    """Verify explicitly named unsupported temple triggers unsupported intent and not temple_information."""
    decision = router.route("What are the timings of Golden Temple in Amritsar?")

    assert isinstance(decision, AgentRouteDecision)
    assert decision.selected_agent != "temple_information"
    assert decision.selected_agent == "none"
    assert decision.intent == "unsupported"
    assert "golden temple" in decision.reason.lower() or "not in" in decision.reason.lower()


def test_6_ambiguous_temple_query(router):
    """Verify temple query lacking temple name triggers clarification and no random temple selection."""
    decision = router.route("What are the temple timings?")

    assert isinstance(decision, AgentRouteDecision)
    assert decision.selected_agent != "temple_information"
    assert decision.selected_agent == "none"
    assert decision.intent == "clarification"
    assert "not identify" in decision.reason.lower() or "specific" in decision.reason.lower()
    assert decision.metadata.get("clarification_needed") is True


def test_7_non_temple_query(router):
    """Verify out-of-scope non-temple query triggers unsupported decision."""
    decision = router.route("What is the weather tomorrow?")

    assert isinstance(decision, AgentRouteDecision)
    assert decision.selected_agent != "temple_information"
    assert decision.selected_agent == "none"
    assert decision.intent == "unsupported"
    assert "outside the scope" in decision.reason.lower()


def test_8_empty_query(router):
    """Verify empty and whitespace queries return clean unsupported decisions."""
    d1 = router.route("")
    d2 = router.route("     ")

    assert d1.selected_agent == "none"
    assert d2.selected_agent == "none"
    assert d1.intent == "unsupported"
    assert d2.intent == "unsupported"
    assert "empty" in d1.reason.lower()


def test_9_future_comparison_intent(router):
    """Verify comparison intent is recognized without attempting to call nonexistent ComparisonAgent."""
    decision = router.route("Compare Yadadri and Dharmapuri temples.")

    assert isinstance(decision, AgentRouteDecision)
    assert decision.intent == "comparison"
    assert decision.selected_agent == "none"
    assert "not yet implemented" in decision.reason.lower()
    assert decision.metadata.get("target_agent") == "ComparisonAgent"
    assert decision.metadata.get("available") is False


def test_10_future_itinerary_intent(router):
    """Verify itinerary planning intent is recognized without attempting to call nonexistent ItineraryPlanningAgent."""
    decision = router.route("Plan a trip to Yadadri temple.")

    assert isinstance(decision, AgentRouteDecision)
    assert decision.intent == "itinerary_planning"
    assert decision.selected_agent == "none"
    assert "not yet implemented" in decision.reason.lower()
    assert decision.metadata.get("target_agent") == "ItineraryPlanningAgent"
    assert decision.metadata.get("available") is False


def test_11_multi_intent_detection(router):
    """Verify conjoined multi-intent query triggers multi_intent decision without premature execution."""
    decision = router.route("What are Yadadri temple timings and how can I reach it?")

    assert isinstance(decision, AgentRouteDecision)
    assert decision.intent == "multi_intent"
    assert decision.selected_agent == "none"
    assert "multiple" in decision.reason.lower() or "multi-intent" in decision.reason.lower()
    assert "timings" in decision.metadata.get("sub_intents", [])
    assert "travel" in decision.metadata.get("sub_intents", [])


def test_12_determinism(router):
    """Verify router produces 100% identical outputs over repeated invocations."""
    query = "What are the timings of Yadadri temple?"
    results = [router.route(query) for _ in range(10)]

    first = results[0]
    for r in results[1:]:
        assert r.selected_agent == first.selected_agent
        assert r.intent == first.intent
        assert r.confidence == first.confidence
        assert r.reason == first.reason
        assert r.metadata == first.metadata


def test_13_no_forbidden_dependencies():
    """Verify router.py does not import low-level database drivers, models, or PilgrimRAGService."""
    router_file = root_dir / "backend" / "app" / "agents" / "router.py"
    content = router_file.read_text(encoding="utf-8")

    forbidden = [
        "qdrant_client",
        "rank_bm25",
        "sentence_transformers",
        "LocalQdrantManager",
        "LocalBM25Manager",
        "PilgrimRAGService"
    ]

    for item in forbidden:
        assert item not in content, f"Forbidden import '{item}' detected in router.py!"
