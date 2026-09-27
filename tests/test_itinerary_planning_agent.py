"""
PilgrimAI - Phase M: ItineraryPlanningAgent Test Suite

Validates:
1. BaseAgent inheritance & lifecycle contracts
2. Agent name and description
3. RAGTool constructor dependency injection
4. Agent lifecycle & AgentResponse contract
5. Execution trace, state tracking, and latency measurement
6. Router dynamic registration & active routing
7. Router inactive fallback preservation
8. Coordinator constructor registration
9. Coordinator end-to-end dispatch & aggregation
10. Single-temple one-day itinerary generation
11. Multi-temple two-day itinerary generation
12. Timing-aware scheduling (temple hours & darshan windows)
13. Seva-aware planning (morning/special seva integration)
14. Annadanam/prasadam integration where verified
15. Accommodation guidance as static options without live booking claims
16. Mandatory deterministic Live-Data Disclaimer presence
17. Zero fabricated travel durations or route distances
18. Source attribution preservation (grounded JSON sources)
19. Unknown/unregistered temple controlled containment
20. Zero-temple clarification request
21. Empty query containment
22. Whitespace query containment
23. Multi-intent pipeline compatibility (Phase H)
24. Conversation memory multi-turn pronoun resolution compatibility (Phase I)
25. Complete-list / registry alignment compatibility (Phase J)
26. Strict RAGTool architectural boundary (AST / forbidden imports check)
27. Deterministic repeated execution consistency
"""

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
from app.agents.itinerary_planning_agent import ItineraryPlanningAgent, LIVE_DATA_DISCLAIMER
from app.agents.router import AgentRouter
from app.agents.coordinator import MasterAgentCoordinator
from app.agents.temple_information_agent import TempleInformationAgent
from app.agents.tools.rag_tool import RAGTool
from app.agents.multi_intent_pipeline import SequentialMultiIntentPipeline
from app.agents.memory import ConversationMemoryManager


@pytest.fixture
def agent():
    return ItineraryPlanningAgent()


@pytest.fixture
def coordinator():
    temple_agent = TempleInformationAgent()
    itinerary_agent = ItineraryPlanningAgent()
    return MasterAgentCoordinator(
        temple_info_agent=temple_agent,
        itinerary_agent=itinerary_agent
    )


# -----------------------------------------------------------------------------
# Test 1: BaseAgent Inheritance
# -----------------------------------------------------------------------------
def test_1_base_agent_inheritance(agent):
    """Verify ItineraryPlanningAgent inherits from BaseAgent with standard hooks."""
    assert isinstance(agent, BaseAgent)
    assert hasattr(agent, "execute")
    assert hasattr(agent, "_run")


# -----------------------------------------------------------------------------
# Test 2: Agent Name and Description
# -----------------------------------------------------------------------------
def test_2_agent_name_and_description(agent):
    """Verify agent name is itinerary_planning and description matches contract."""
    assert agent.name == "itinerary_planning"
    assert "itinerary" in agent.description.lower() or "planning" in agent.description.lower()


# -----------------------------------------------------------------------------
# Test 3: RAGTool Dependency Injection
# -----------------------------------------------------------------------------
def test_3_constructor_dependency_injection():
    """Verify custom RAGTool injection into ItineraryPlanningAgent."""
    custom_rag = RAGTool()
    custom_agent = ItineraryPlanningAgent(rag_tool=custom_rag)
    assert custom_agent.rag_tool is custom_rag


# -----------------------------------------------------------------------------
# Test 4: Agent Lifecycle & AgentResponse Contract
# -----------------------------------------------------------------------------
def test_4_agent_lifecycle_and_response(agent):
    """Verify agent.execute produces a compliant AgentResponse with valid metadata."""
    state = AgentState(user_query="Plan a one-day visit to Yadadri")
    resp = agent.execute(state)

    assert isinstance(resp, AgentResponse)
    assert resp.success is True
    assert resp.agent_name == "itinerary_planning"
    assert resp.latency_ms > 0.0
    assert len(resp.sources) > 0
    assert "itinerary" in resp.metadata
    assert resp.metadata["temples"] == ["Yadadri"]


# -----------------------------------------------------------------------------
# Test 5: Execution Trace
# -----------------------------------------------------------------------------
def test_5_execution_trace(agent):
    """Verify state.execution_trace records agent execution steps and timing."""
    state = AgentState(user_query="Plan a visit to Yadadri")
    resp = agent.execute(state)

    assert len(state.execution_trace) >= 1
    trace = state.execution_trace[-1]
    assert isinstance(trace, ExecutionTrace)
    assert trace.agent_name == "itinerary_planning"
    assert trace.status == "completed"
    assert trace.latency_ms > 0.0


# -----------------------------------------------------------------------------
# Test 6: Router Registration
# -----------------------------------------------------------------------------
def test_6_router_registration():
    """Verify AgentRouter routes itinerary planning intent to itinerary_planning agent when registered."""
    router = AgentRouter()
    router.register_agent("itinerary_planning")

    decision = router.route("Plan a one-day visit to Yadadri")
    assert decision.intent == "itinerary_planning"
    assert decision.selected_agent == "itinerary_planning"
    assert decision.metadata.get("available") is True
    assert decision.confidence >= 0.85


# -----------------------------------------------------------------------------
# Test 7: Router Inactive Fallback
# -----------------------------------------------------------------------------
def test_7_router_inactive_fallback():
    """Verify AgentRouter returns selected_agent='none' and available=False when agent is not active."""
    router = AgentRouter(active_agents={"temple_information"})

    decision = router.route("Plan a one-day tour to Yadadri")
    assert decision.intent == "itinerary_planning"
    assert decision.selected_agent == "none"
    assert decision.metadata.get("available") is False
    assert "not yet implemented" in decision.reason.lower()


# -----------------------------------------------------------------------------
# Test 8: Coordinator Registration
# -----------------------------------------------------------------------------
def test_8_coordinator_registration():
    """Verify MasterAgentCoordinator accepts and registers itinerary_agent in agents map and router."""
    itinerary_agent = ItineraryPlanningAgent()
    coord = MasterAgentCoordinator(itinerary_agent=itinerary_agent)

    assert "itinerary_planning" in coord.agents
    assert coord.agents["itinerary_planning"] is itinerary_agent
    assert "itinerary_planning" in coord.router.active_agents


# -----------------------------------------------------------------------------
# Test 9: Coordinator Dispatch & Aggregation
# -----------------------------------------------------------------------------
def test_9_coordinator_dispatch(coordinator):
    """Verify coordinator dispatches an itinerary query to ItineraryPlanningAgent and aggregates the result."""
    state = AgentState(user_query="Plan a one-day trip to Yadadri")
    final_resp = coordinator.process(state)

    assert final_resp.success is True
    assert "Yadadri" in final_resp.answer
    assert final_resp.agent_name in ["itinerary_planning", "response_aggregator", "aggregator"]
    assert any(t.agent_name == "itinerary_planning" for t in state.execution_trace)


# -----------------------------------------------------------------------------
# Test 10: Single-Temple One-Day Itinerary
# -----------------------------------------------------------------------------
def test_10_single_temple_one_day_itinerary(agent):
    """Verify grounded single-temple one-day itinerary structure and Fact vs Suggestion separation."""
    state = AgentState(user_query="Plan a one-day visit to Yadadri")
    resp = agent.execute(state)

    assert resp.success is True
    assert "Yadadri" in resp.answer
    assert "Verified Temple Information:" in resp.answer or "Verified" in resp.answer
    assert "Suggested Visit Plan:" in resp.answer or "Plan" in resp.answer
    assert LIVE_DATA_DISCLAIMER in resp.answer


# -----------------------------------------------------------------------------
# Test 11: Multi-Temple Two-Day Itinerary
# -----------------------------------------------------------------------------
def test_11_multi_temple_two_day_itinerary(agent):
    """Verify grounded multi-temple two-day itinerary covers both temples across separate days."""
    state = AgentState(user_query="Plan a 2-day pilgrimage to Yadadri and Dharmapuri")
    resp = agent.execute(state)

    assert resp.success is True
    assert "Yadadri" in resp.answer
    assert "Dharmapuri" in resp.answer
    assert "Day 1" in resp.answer
    assert "Day 2" in resp.answer
    assert set(resp.metadata["temples"]) == {"Yadadri", "Dharmapuri"}


# -----------------------------------------------------------------------------
# Test 12: Timing-Aware Planning
# -----------------------------------------------------------------------------
def test_12_timing_aware_planning(agent):
    """Verify itinerary incorporates actual verified opening/darshan hours from timings.json."""
    state = AgentState(user_query="Plan a one-day visit to Yadadri")
    resp = agent.execute(state)

    assert resp.success is True
    # Yadadri temple hours typically open early (e.g. 4:00 AM)
    assert any(term in resp.answer for term in ["4:00 AM", "Morning Darshan", "Opening", "timings"])


# -----------------------------------------------------------------------------
# Test 13: Seva-Aware Planning
# -----------------------------------------------------------------------------
def test_13_seva_aware_planning(agent):
    """Verify query specifying morning seva incorporates verified seva details."""
    state = AgentState(user_query="Plan my visit to Dharmapuri around morning seva")
    resp = agent.execute(state)

    assert resp.success is True
    assert "Dharmapuri" in resp.answer
    # Should include verified sevas or seva section
    assert "Seva" in resp.answer or "seva" in resp.answer.lower()
    assert any("sevas.json" in s for s in resp.sources)


# -----------------------------------------------------------------------------
# Test 14: Annadanam / Prasadam Integration
# -----------------------------------------------------------------------------
def test_14_annadanam_prasadam_integration(agent):
    """Verify Annadanam/prasadam information is integrated into afternoon schedule when verified."""
    state = AgentState(user_query="Plan a one-day visit to Edupayal with prasadam")
    resp = agent.execute(state)

    assert resp.success is True
    assert "Edupayal" in resp.answer
    assert any(term in resp.answer.lower() for term in ["prasadam", "annadanam", "meal", "food"])


# -----------------------------------------------------------------------------
# Test 15: Accommodation Guidance
# -----------------------------------------------------------------------------
def test_15_accommodation_guidance(agent):
    """Verify accommodation is presented as verified static options without live booking claims."""
    state = AgentState(user_query="Plan a 2-day trip to Yadadri with night stay and accommodation")
    resp = agent.execute(state)

    assert resp.success is True
    assert "Accommodation" in resp.answer or "accommodation" in resp.answer.lower()
    # Must NOT claim dynamic room availability
    assert "rooms are currently available" not in resp.answer.lower()
    assert "booking confirmed" not in resp.answer.lower()


# -----------------------------------------------------------------------------
# Test 16: Live-Data Disclaimer
# -----------------------------------------------------------------------------
def test_16_live_data_disclaimer(agent):
    """Verify every generated itinerary contains the deterministic live-data limitation disclaimer."""
    state = AgentState(user_query="Plan a visit to Basara")
    resp = agent.execute(state)

    assert resp.success is True
    assert LIVE_DATA_DISCLAIMER in resp.answer
    assert "live road conditions" in resp.answer.lower()
    assert "live weather forecasts" in resp.answer.lower()


# -----------------------------------------------------------------------------
# Test 17: No Fabricated Travel Durations
# -----------------------------------------------------------------------------
def test_17_no_fabricated_travel_durations(agent):
    """Verify the agent does not fabricate arbitrary driving times or routes between temples."""
    state = AgentState(user_query="Plan a 2-day trip to Yadadri and Dharmapuri")
    resp = agent.execute(state)

    assert resp.success is True
    # Should NOT have fabricated phrases like "takes 2 hours 15 minutes to drive"
    answer_lower = resp.answer.lower()
    assert "takes 2 hours" not in answer_lower
    assert "takes 3 hours" not in answer_lower
    assert "takes 1 hour 45 minutes" not in answer_lower
    # Verified static notes are acceptable, fabricated dynamic duration is not
    assert "real-time travel durations" in answer_lower or "live-data limitation" in answer_lower


# -----------------------------------------------------------------------------
# Test 18: Source Attribution
# -----------------------------------------------------------------------------
def test_18_source_attribution(agent):
    """Verify response sources point to grounded temple JSON files."""
    state = AgentState(user_query="Plan a visit to Yadadri")
    resp = agent.execute(state)

    assert len(resp.sources) > 0
    for src in resp.sources:
        assert src.endswith(".json")
        assert "/" in src


# -----------------------------------------------------------------------------
# Test 19: Unknown Temple
# -----------------------------------------------------------------------------
def test_19_unknown_temple(agent):
    """Verify unknown temple produces controlled containment indicating lack of verified data."""
    state = AgentState(user_query="Plan a trip to Atlantis Temple")
    resp = agent.execute(state)

    assert resp.success is False
    assert "Atlantis" in resp.answer or "unregistered" in resp.answer.lower() or "not have verified" in resp.answer.lower()
    assert len(resp.sources) == 0


# -----------------------------------------------------------------------------
# Test 20: Zero-Temple Clarification
# -----------------------------------------------------------------------------
def test_20_zero_temple_clarification(agent):
    """Verify generic itinerary query with zero temples prompts for clarification without hallucination."""
    state = AgentState(user_query="Plan a pilgrimage itinerary for me")
    resp = agent.execute(state)

    assert resp.success is False
    assert "which temple" in resp.answer.lower()
    assert len(resp.sources) == 0


# -----------------------------------------------------------------------------
# Test 21: Empty Query
# -----------------------------------------------------------------------------
def test_21_empty_query(agent):
    """Verify empty query returns controlled error response without crashing."""
    state = AgentState(user_query="")
    resp = agent.execute(state)

    assert resp.success is False
    assert resp.error is not None
    assert "empty" in resp.answer.lower() or "please provide" in resp.answer.lower()


# -----------------------------------------------------------------------------
# Test 22: Whitespace Query
# -----------------------------------------------------------------------------
def test_22_whitespace_query(agent):
    """Verify whitespace-only query returns controlled error response safely."""
    state = AgentState(user_query="    ")
    resp = agent.execute(state)

    assert resp.success is False
    assert resp.error is not None


# -----------------------------------------------------------------------------
# Test 23: Multi-Intent Pipeline Compatibility (Phase H)
# -----------------------------------------------------------------------------
def test_23_multi_intent_compatibility():
    """Verify compound query executes TempleInformationAgent and ItineraryPlanningAgent sequentially."""
    router = AgentRouter()
    router.register_agent("temple_information")
    router.register_agent("itinerary_planning")

    temple_agent = TempleInformationAgent()
    itinerary_agent = ItineraryPlanningAgent()
    coord = MasterAgentCoordinator(
        router=router,
        temple_info_agent=temple_agent,
        itinerary_agent=itinerary_agent
    )

    query = "What are the timings of Yadadri and plan a one-day visit there"
    state = AgentState(user_query=query)
    resp = coord.process(state)

    assert resp.success is True
    # Answer should contain information from both agents or aggregated response
    assert "Yadadri" in resp.answer


# -----------------------------------------------------------------------------
# Test 24: Conversation Memory Compatibility (Phase I)
# -----------------------------------------------------------------------------
def test_24_conversation_memory_compatibility():
    """Verify multi-turn memory resolves temple pronouns before dispatching to itinerary agent."""
    memory_mgr = ConversationMemoryManager()
    temple_agent = TempleInformationAgent()
    itinerary_agent = ItineraryPlanningAgent()
    coord = MasterAgentCoordinator(
        temple_info_agent=temple_agent,
        itinerary_agent=itinerary_agent,
        memory_manager=memory_mgr
    )

    # Turn 1: Mention Yadadri
    state_t1 = AgentState(user_query="Tell me about Yadadri temple", session_id="test_sess_itin")
    resp_t1 = coord.process(state_t1)
    assert resp_t1.success is True

    # Turn 2: Refer with pronoun "it" or "there" for itinerary planning
    state_t2 = AgentState(user_query="Plan a one-day visit there", session_id="test_sess_itin")
    resp_t2 = coord.process(state_t2)

    assert resp_t2.success is True
    assert "Yadadri" in resp_t2.answer


# -----------------------------------------------------------------------------
# Test 25: Complete-List / Registry Alignment Compatibility (Phase J)
# -----------------------------------------------------------------------------
def test_25_complete_list_registry_alignment(agent):
    """Verify ItineraryPlanningAgent detects all 20 canonical registered temples."""
    rag_tool = RAGTool()
    registered = rag_tool.get_registered_temples()
    assert len(registered) == 20

    for temple in registered:
        detected = agent._detect_temples(f"Plan a visit to {temple}")
        assert temple in detected or any(temple.lower() in t.lower() for t in detected), f"Failed to detect registered temple: {temple}"


# -----------------------------------------------------------------------------
# Test 26: Strict RAGTool Architectural Boundary (AST / Forbidden Imports)
# -----------------------------------------------------------------------------
def test_26_strict_rag_boundary():
    """Verify itinerary_planning_agent.py does NOT directly import raw DB or RAG internals."""
    agent_file = root_dir / "backend" / "app" / "agents" / "itinerary_planning_agent.py"
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
        assert p not in code, f"Forbidden import '{p}' found in itinerary_planning_agent.py!"

    # Ensure no direct open/json.load calls to read raw JSON files
    assert "open(" not in code
    assert "json.load" not in code

    assert "BaseAgent" in code
    assert "RAGTool" in code


# -----------------------------------------------------------------------------
# Test 27: Deterministic Repeated Execution
# -----------------------------------------------------------------------------
def test_27_deterministic_repeated_execution(agent):
    """Verify repeated execution with same inputs produces identical structured answers and sources."""
    query = "Plan a one-day visit to Yadadri"
    state1 = AgentState(user_query=query)
    resp1 = agent.execute(state1)

    state2 = AgentState(user_query=query)
    resp2 = agent.execute(state2)

    assert resp1.answer == resp2.answer
    assert resp1.sources == resp2.sources
    assert resp1.metadata == resp2.metadata
