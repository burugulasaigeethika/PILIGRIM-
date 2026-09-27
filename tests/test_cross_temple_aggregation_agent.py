"""
PilgrimAI - Phase L: CrossTempleAggregationAgent Test Suite

Validates:
1. BaseAgent inheritance & lifecycle contracts
2. Execution tracing, state tracking, and latency measurement
3. Router dynamic activation and fallback preservation
4. MasterAgentCoordinator dependency injection and dispatch
5. Universal 20-temple coverage without Top-K truncation
6. Three-tier availability classification (CONFIRMED_AVAILABLE vs CONFIRMED_UNAVAILABLE vs INFORMATION_NOT_AVAILABLE)
7. Positive aggregation (river bank = 11, wheelchair, accommodation, annadanam)
8. Negative aggregation (confirmed unavailable vs unrecorded)
9. Source attribution preservation & temple deduplication
10. Empty, whitespace, and unsupported query containment
11. Phase H (multi-intent pipeline) compatibility
12. Phase I (conversation memory) multi-turn compatibility
13. Legacy backward compatibility (aggregate_temples, format_response, detect_aggregation_intent)
14. Strict RAGTool architectural boundary (zero raw DB or direct filesystem imports)
"""

import re
import sys
import pytest
from pathlib import Path
from typing import Dict, Any, List

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState, AgentResponse, ExecutionTrace
from app.agents.cross_temple_aggregation_agent import CrossTempleAggregationAgent
from app.agents.router import AgentRouter
from app.agents.coordinator import MasterAgentCoordinator
from app.agents.temple_information_agent import TempleInformationAgent
from app.agents.tools.rag_tool import RAGTool
from app.agents.multi_intent_pipeline import SequentialMultiIntentPipeline
from app.agents.memory import ConversationMemoryManager
from app.rag.completeness_validator import (
    CONFIRMED_AVAILABLE,
    CONFIRMED_UNAVAILABLE,
    INFORMATION_NOT_AVAILABLE
)

root_dir = Path(__file__).resolve().parent.parent

EXPECTED_RIVER_BANK_TEMPLES = {
    "Ahobilam",
    "Badrachalam",
    "Basara",
    "Dharmapuri",
    "Edupayal",
    "Jogulamba(New)",
    "Kaleshvaram",
    "Medaram",
    "Srisaila",
    "Veera Satyanarayana",
    "Vemulavada"
}


@pytest.fixture
def agent():
    return CrossTempleAggregationAgent()


@pytest.fixture
def coordinator():
    temple_agent = TempleInformationAgent()
    agg_agent = CrossTempleAggregationAgent()
    return MasterAgentCoordinator(temple_info_agent=temple_agent, cross_temple_agent=agg_agent)


# -----------------------------------------------------------------------------
# Test 1: BaseAgent Inheritance
# -----------------------------------------------------------------------------
def test_1_base_agent_inheritance(agent):
    """Verify CrossTempleAggregationAgent inherits from BaseAgent."""
    assert isinstance(agent, BaseAgent)
    assert hasattr(agent, "execute")
    assert hasattr(agent, "_run")


# -----------------------------------------------------------------------------
# Test 2: Agent Name and Description
# -----------------------------------------------------------------------------
def test_2_agent_name_and_description(agent):
    """Verify agent name and description meet contracts."""
    assert agent.name == "cross_temple_aggregation"
    assert "cross-temple" in agent.description.lower() or "aggregation" in agent.description.lower()


# -----------------------------------------------------------------------------
# Test 3: Constructor and Dependency Injection
# -----------------------------------------------------------------------------
def test_3_constructor_dependency_injection():
    """Verify custom RAGTool injection into CrossTempleAggregationAgent."""
    custom_rag = RAGTool()
    agent = CrossTempleAggregationAgent(rag_tool=custom_rag)
    assert agent.rag_tool is custom_rag


# -----------------------------------------------------------------------------
# Test 4: Agent Lifecycle and AgentResponse Contract
# -----------------------------------------------------------------------------
def test_4_agent_lifecycle_and_response_contract(agent):
    """Verify execute(state) executes _run, returns AgentResponse, and updates state."""
    state = AgentState(user_query="Which temples have river bank access?")
    res = agent.execute(state)

    assert isinstance(res, AgentResponse)
    assert res.agent_name == "cross_temple_aggregation"
    assert res.success is True
    assert "cross_temple_aggregation" in state.intermediate_results
    assert res.latency_ms is not None and res.latency_ms >= 0


# -----------------------------------------------------------------------------
# Test 5: ExecutionTrace Recording
# -----------------------------------------------------------------------------
def test_5_execution_trace_recording(agent):
    """Verify execution traces are added to state.execution_trace."""
    state = AgentState(user_query="Which temples have wheelchair facilities?")
    agent.execute(state)

    assert len(state.execution_trace) > 0
    trace = state.execution_trace[-1]
    assert trace.agent_name == "cross_temple_aggregation"
    assert trace.step_name == "execute"
    assert trace.status == "completed"


# -----------------------------------------------------------------------------
# Test 6: Router Registration and Dynamic Activation
# -----------------------------------------------------------------------------
def test_6_router_registration_and_activation():
    """Verify router routes cross_temple_aggregation when registered."""
    router = AgentRouter()

    # Before registration: available is False
    d1 = router.route("List all temples that have river bank")
    assert d1.intent == "cross_temple_aggregation"
    assert d1.selected_agent == "none"
    assert d1.metadata.get("available") is False

    # After registration: selected_agent is cross_temple_aggregation
    router.register_agent("cross_temple_aggregation")
    d2 = router.route("List all temples that have river bank")
    assert d2.intent == "cross_temple_aggregation"
    assert d2.selected_agent == "cross_temple_aggregation"
    assert d2.metadata.get("available") is True


# -----------------------------------------------------------------------------
# Test 7: Router Fallback when Inactive
# -----------------------------------------------------------------------------
def test_7_router_fallback_when_inactive():
    """Verify unregistered router preserves exact Phase D fallback."""
    router = AgentRouter()
    d = router.route("Which temples have accommodation?")
    assert d.intent == "cross_temple_aggregation"
    assert d.selected_agent == "none"
    assert d.metadata.get("available") is False
    assert "not yet implemented" in d.reason


# -----------------------------------------------------------------------------
# Test 8: Coordinator Registration
# -----------------------------------------------------------------------------
def test_8_coordinator_registration(coordinator):
    """Verify coordinator registers cross_temple_agent in self.agents."""
    assert "cross_temple_aggregation" in coordinator.agents
    assert isinstance(coordinator.agents["cross_temple_aggregation"], CrossTempleAggregationAgent)
    assert "cross_temple_aggregation" in coordinator.router.active_agents


# -----------------------------------------------------------------------------
# Test 9: Coordinator Dispatch End-to-End
# -----------------------------------------------------------------------------
def test_9_coordinator_dispatch_end_to_end(coordinator):
    """Verify coordinator routes and executes cross-temple query end-to-end."""
    state = AgentState(user_query="Which temples have river bank access?")
    res = coordinator.process(state)

    assert res.success is True
    assert "river" in res.answer.lower() or "bank" in res.answer.lower()
    assert len(res.sources) > 0


# -----------------------------------------------------------------------------
# Test 10: River Bank Aggregation Ground Truth (11 Temples)
# -----------------------------------------------------------------------------
def test_10_river_bank_aggregation_ground_truth(agent):
    """Verify river bank aggregation matches exact expected 11 temples."""
    state = AgentState(user_query="Which temples have river bank access?")
    res = agent.execute(state)

    assert res.success is True
    assert res.metadata.get("matching_temples_count") == 11
    matching_set = set(res.metadata.get("matching_temples", []))
    assert matching_set == EXPECTED_RIVER_BANK_TEMPLES


# -----------------------------------------------------------------------------
# Test 11: Wheelchair Accessibility Aggregation
# -----------------------------------------------------------------------------
def test_11_wheelchair_accessibility_aggregation(agent):
    """Verify wheelchair accessibility aggregation discovers accessible temples."""
    state = AgentState(user_query="Which temples have wheelchair facilities?")
    res = agent.execute(state)

    assert res.success is True
    assert res.metadata.get("matching_temples_count") > 0
    assert len(res.sources) > 0


# -----------------------------------------------------------------------------
# Test 12: Accommodation Aggregation
# -----------------------------------------------------------------------------
def test_12_accommodation_aggregation(agent):
    """Verify accommodation aggregation evaluates all 20 temples."""
    state = AgentState(user_query="List all temples with accommodation")
    res = agent.execute(state)

    assert res.success is True
    assert res.metadata.get("total_temples_searched") == 20
    assert res.metadata.get("matching_temples_count") > 0


# -----------------------------------------------------------------------------
# Test 13: Annadanam / Prasadam Aggregation
# -----------------------------------------------------------------------------
def test_13_annadanam_prasadam_aggregation(agent):
    """Verify prasadam/annadanam aggregation evaluates temples offering free food."""
    state = AgentState(user_query="Which temples provide annadanam?")
    res = agent.execute(state)

    assert res.success is True
    assert res.metadata.get("matching_temples_count") > 0


# -----------------------------------------------------------------------------
# Test 14: Negative Query Aggregation
# -----------------------------------------------------------------------------
def test_14_negative_query_aggregation(agent):
    """Verify negative queries aggregate confirmed unavailable records without false absence."""
    state = AgentState(user_query="Which temples do not have parking?")
    res = agent.execute(state)

    assert res.success is True
    assert res.metadata.get("condition") == "negative"
    # Even if 0 temples confirm absence, it shouldn't crash or claim unrecorded data as absent
    assert res.metadata.get("total_temples_searched") == 20


# -----------------------------------------------------------------------------
# Test 15: Three-Tier Evidence Classification
# -----------------------------------------------------------------------------
def test_15_three_tier_classification(agent):
    """Verify results distinguish confirmed available, confirmed unavailable, and unrecorded."""
    state = AgentState(user_query="Which temples have river bank access?")
    res = agent.execute(state)

    assert "confirmed_available_count" in res.metadata
    assert "confirmed_unavailable_count" in res.metadata
    assert "information_not_available_count" in res.metadata

    # Sum of the three tiers must equal total temples evaluated (20)
    total = (
        res.metadata["confirmed_available_count"]
        + res.metadata["confirmed_unavailable_count"]
        + res.metadata["information_not_available_count"]
    )
    assert total == 20


# -----------------------------------------------------------------------------
# Test 16: Universal 20-Temple Coverage (No Top-3 Truncation)
# -----------------------------------------------------------------------------
def test_16_universal_20_temple_coverage(agent):
    """Verify aggregation scans all 20 temples and is never truncated to Top-3."""
    state = AgentState(user_query="Which temples have river bank access?")
    res = agent.execute(state)

    assert res.metadata.get("total_temples_searched") == 20
    assert res.metadata.get("matching_temples_count") == 11
    assert len(res.sources) == 11


# -----------------------------------------------------------------------------
# Test 17: Source Attribution Preservation
# -----------------------------------------------------------------------------
def test_17_source_attribution_preservation(agent):
    """Verify every matching temple contributes a valid JSON source path."""
    state = AgentState(user_query="Which temples have river bank access?")
    res = agent.execute(state)

    assert len(res.sources) == 11
    for s in res.sources:
        assert s.endswith(".json")


# -----------------------------------------------------------------------------
# Test 18: Temple Deduplication
# -----------------------------------------------------------------------------
def test_18_temple_deduplication(agent):
    """Verify matching temples list contains zero duplicates."""
    state = AgentState(user_query="Which temples have river bank access?")
    res = agent.execute(state)

    matching = res.metadata.get("matching_temples", [])
    assert len(matching) == len(set(matching))


# -----------------------------------------------------------------------------
# Test 19: Empty Query Handling
# -----------------------------------------------------------------------------
def test_19_empty_query_handling(agent):
    """Verify empty query returns graceful error without crashing."""
    state = AgentState(user_query="")
    res = agent.execute(state)

    assert res.success is False
    assert res.error == "Empty query"
    assert "valid" in res.answer.lower()


# -----------------------------------------------------------------------------
# Test 20: Whitespace Query Handling
# -----------------------------------------------------------------------------
def test_20_whitespace_query_handling(agent):
    """Verify whitespace query returns graceful error without crashing."""
    state = AgentState(user_query="     ")
    res = agent.execute(state)

    assert res.success is False
    assert res.error == "Empty query"


# -----------------------------------------------------------------------------
# Test 21: Unsupported / Unrecognized Category Handling
# -----------------------------------------------------------------------------
def test_21_unsupported_category_handling(agent):
    """Verify query with unrecognized category returns controlled guidance."""
    state = AgentState(user_query="Which temples have flying spaceships and rockets?")
    res = agent.execute(state)

    assert res.success is False
    assert res.error == "Unrecognized aggregation category"
    assert res.metadata.get("clarification_needed") is True


# -----------------------------------------------------------------------------
# Test 22: Multi-Intent Pipeline Compatibility (Phase H)
# -----------------------------------------------------------------------------
def test_22_multi_intent_pipeline_compatibility():
    """Verify multi-intent pipeline decomposes and dispatches cross-temple sub-task."""
    temple_agent = TempleInformationAgent()
    agg_agent = CrossTempleAggregationAgent()
    router = AgentRouter()
    router.register_agent("temple_information")
    router.register_agent("cross_temple_aggregation")

    pipeline = SequentialMultiIntentPipeline(
        router=router,
        agents={
            "temple_information": temple_agent,
            "cross_temple_aggregation": agg_agent
        }
    )

    query = "What are the timings of Yadadri? Which temples have river bank"
    tasks = pipeline.decompose_query(query)

    assert len(tasks) == 2
    assert tasks[0]["intent"] == "temple_information"
    assert tasks[1]["intent"] == "cross_temple_aggregation"
    assert tasks[1]["target_agent"] == "cross_temple_aggregation"
    assert tasks[1]["is_available"] is True


# -----------------------------------------------------------------------------
# Test 23: Conversation Memory Compatibility (Phase I)
# -----------------------------------------------------------------------------
def test_23_conversation_memory_compatibility():
    """Verify global cross-temple query does not inappropriately inherit prior temple scope."""
    memory_manager = ConversationMemoryManager()
    session_id = "test_phase_l_session"

    # Turn 1: Discuss Yadadri
    memory_manager.add_turn(
        session_id=session_id,
        user_query="Tell me about Yadadri temple.",
        identified_temples=["Yadadri"],
        detected_intents=["temple_information"]
    )

    # Turn 2: Global cross-temple query
    turn2_query = "Which temples have river bank access?"
    resolution = memory_manager.resolve_query(session_id=session_id, query=turn2_query)
    resolved_query = resolution["resolved_query"]

    # Must NOT inject Yadadri into a global question
    assert "Yadadri" not in resolved_query
    agent = CrossTempleAggregationAgent()
    state = AgentState(user_query=resolved_query)
    res = agent.execute(state)
    assert res.success is True
    assert res.metadata.get("matching_temples_count") == 11


# -----------------------------------------------------------------------------
# Test 24: Legacy aggregate_temples Method
# -----------------------------------------------------------------------------
def test_24_legacy_aggregate_temples(agent):
    """Verify legacy aggregate_temples method returns identical structured dictionary."""
    res = agent.aggregate_temples("river_bank")
    assert res["matching_temples_count"] == 11
    assert res["total_temples_searched"] == 20
    assert len(res["matches"]) == 11
    assert len(res["sources"]) == 11


# -----------------------------------------------------------------------------
# Test 25: Legacy format_response Method
# -----------------------------------------------------------------------------
def test_25_legacy_format_response(agent):
    """Verify legacy format_response method renders formatted markdown."""
    res = agent.aggregate_temples("river_bank")
    formatted = agent.format_response(res, "Which temples have river bank?")
    assert "river" in formatted.lower() or "bank" in formatted.lower()
    assert "Dharmapuri" in formatted
    assert "Basara" in formatted


# -----------------------------------------------------------------------------
# Test 26: Legacy detect_aggregation_intent Method
# -----------------------------------------------------------------------------
def test_26_legacy_detect_aggregation_intent(agent):
    """Verify legacy detect_aggregation_intent returns expected dictionary."""
    res = agent.detect_aggregation_intent("List all temples with accommodation")
    assert res is not None
    assert res["is_aggregation"] is True
    assert res["property_key"] == "accommodation"


# -----------------------------------------------------------------------------
# Test 27: Strict RAGTool Architectural Boundary (Zero Forbidden Imports)
# -----------------------------------------------------------------------------
def test_27_rag_tool_architectural_boundary():
    """Verify cross_temple_aggregation_agent.py does NOT directly import raw DB or RAG internals."""
    agent_file = root_dir / "backend" / "app" / "agents" / "cross_temple_aggregation_agent.py"
    assert agent_file.exists()
    code = agent_file.read_text(encoding="utf-8")

    forbidden = [
        "qdrant_client",
        "rank_bm25",
        "sentence_transformers",
        "LocalQdrantManager",
        "LocalBM25Manager",
        "CrossEncoder",
        "PilgrimRAGService"
    ]
    for p in forbidden:
        assert p not in code, f"Forbidden import '{p}' found in cross_temple_aggregation_agent.py!"

    assert "BaseAgent" in code
    assert "RAGTool" in code


# -----------------------------------------------------------------------------
# Test 28: Deterministic Repeated Execution
# -----------------------------------------------------------------------------
def test_28_deterministic_repeated_execution(agent):
    """Verify repeated execution produces identical results."""
    state1 = AgentState(user_query="Which temples have river bank access?")
    res1 = agent.execute(state1)

    state2 = AgentState(user_query="Which temples have river bank access?")
    res2 = agent.execute(state2)

    assert res1.metadata["matching_temples"] == res2.metadata["matching_temples"]
    assert res1.metadata["matching_temples_count"] == res2.metadata["matching_temples_count"]
    assert res1.sources == res2.sources
