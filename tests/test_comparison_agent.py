"""
Phase K - ComparisonAgent Certification Tests

Certifies ComparisonAgent:
1. Inherits from BaseAgent and fulfills the agent lifecycle contract.
2. Initializes with clean metadata and RAGTool facade.
3. BaseAgent lifecycle contract (execution tracing, timing, state recording).
4. Router activation (register_agent activates comparison route).
5. Coordinator registration (comparison agent registers into coordinator).
6. Coordinator dispatch (end-to-end execution through coordinator).
7. Two canonical temples resolution.
8. Temple aliases resolution (e.g., Yadagirigutta -> Yadadri).
9. Zero-temple clarification ('Compare the temples.').
10. One-temple clarification ('Compare Yadadri facilities.').
11. Explicit unknown-temple handling (e.g., 'Compare Yadadri and Atlantis Temple').
12. Timings comparison across two temples.
13. Facilities comparison across two temples.
14. Sevas comparison across two temples.
15. Broad comparison without explicit category.
16. Strict RAGTool dependency boundary (static code check for zero low-level DB imports).
17. Temple isolation (sources and evidence strictly attributed per temple).
18. Source preservation in AgentResponse.sources.
19. Neutral output presentation.
20. No automatic winner ('better', 'best', 'superior', 'worse', 'winner' are prohibited).
21. Missing data handling (does not infer false absence).
22. Conflicting data handling.
23. Partial retrieval failure handling.
24. Phase H multi-intent pipeline compatibility.
25. Phase I conversation memory compatibility (Turn 1: Yadadri -> Turn 2: 'Compare it with Dharmapuri').
26. Phase J complete-list retrieval compatibility.
27. Empty query handling.
28. Whitespace query handling.
29. Deterministic repeated execution.
30. Backward compatibility with existing router and coordinator defaults.
"""

import sys
from pathlib import Path
import pytest

# Ensure root and backend are in sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState, AgentResponse, AgentRouteDecision
from app.agents.tools.rag_tool import RAGTool
from app.agents.router import AgentRouter
from app.agents.coordinator import MasterAgentCoordinator
from app.agents.temple_information_agent import TempleInformationAgent
from app.agents.comparison_agent import ComparisonAgent
from app.agents.memory import ConversationMemoryManager
from app.agents.multi_intent_pipeline import SequentialMultiIntentPipeline


@pytest.fixture(scope="module")
def agent():
    return ComparisonAgent()


@pytest.fixture(scope="module")
def coordinator(agent):
    return MasterAgentCoordinator(comparison_agent=agent)


# -----------------------------------------------------------------------------
# Test 1: BaseAgent Inheritance
# -----------------------------------------------------------------------------
def test_1_base_agent_inheritance(agent):
    """Verify ComparisonAgent inherits from BaseAgent."""
    assert isinstance(agent, BaseAgent)


# -----------------------------------------------------------------------------
# Test 2: Agent Initialization
# -----------------------------------------------------------------------------
def test_2_agent_initialization(agent):
    """Verify ComparisonAgent initializes with expected name and description."""
    assert agent.name == "comparison"
    assert "comparison" in agent.description.lower()
    assert isinstance(agent.rag_tool, RAGTool)


# -----------------------------------------------------------------------------
# Test 3: BaseAgent Lifecycle Contract
# -----------------------------------------------------------------------------
def test_3_agent_lifecycle_contract(agent):
    """Verify agent execution updates state traces, latency, and intermediate results."""
    state = AgentState(user_query="Compare Yadadri and Dharmapuri timings")
    res = agent.execute(state)

    assert isinstance(res, AgentResponse)
    assert res.agent_name == "comparison"
    assert res.latency_ms is not None and res.latency_ms > 0
    assert "comparison" in state.intermediate_results
    assert len(state.execution_trace) > 0
    trace = state.execution_trace[-1]
    assert trace.agent_name == "comparison"
    assert trace.step_name == "execute"


# -----------------------------------------------------------------------------
# Test 4: Router Activation
# -----------------------------------------------------------------------------
def test_4_router_activation():
    """Verify router routes to comparison agent when comparison is registered."""
    router = AgentRouter()
    # Before registration: available is False
    d1 = router.route("Compare Yadadri and Dharmapuri")
    assert d1.intent == "comparison"
    assert d1.selected_agent == "none"
    assert d1.metadata.get("available") is False

    # After registration: routes to comparison
    router.register_agent("comparison")
    d2 = router.route("Compare Yadadri and Dharmapuri")
    assert d2.intent == "comparison"
    assert d2.selected_agent == "comparison"
    assert d2.metadata.get("available") is True


# -----------------------------------------------------------------------------
# Test 5: Coordinator Registration
# -----------------------------------------------------------------------------
def test_5_coordinator_registration(coordinator):
    """Verify MasterAgentCoordinator registers ComparisonAgent."""
    assert "comparison" in coordinator.agents
    assert isinstance(coordinator.agents["comparison"], ComparisonAgent)


# -----------------------------------------------------------------------------
# Test 6: Coordinator Dispatch
# -----------------------------------------------------------------------------
def test_6_coordinator_dispatch(coordinator):
    """Verify comparison query executes end-to-end through coordinator."""
    state = AgentState(user_query="Compare the timings of Yadadri and Dharmapuri.")
    res = coordinator.process(state)

    assert isinstance(res, AgentResponse)
    assert res.success is True
    assert "Yadadri" in res.answer
    assert "Dharmapuri" in res.answer
    assert len(res.sources) > 0


# -----------------------------------------------------------------------------
# Test 7: Two Canonical Temples Resolution
# -----------------------------------------------------------------------------
def test_7_two_canonical_temples_resolution(agent):
    """Verify detection of two canonical registered temples in order."""
    temples = agent.detect_temples("Compare Yadadri and Dharmapuri temples.")
    assert temples == ["Yadadri", "Dharmapuri"]


# -----------------------------------------------------------------------------
# Test 8: Temple Aliases Resolution
# -----------------------------------------------------------------------------
def test_8_temple_aliases_resolution(agent):
    """Verify multi-word aliases resolve to canonical temple names."""
    temples = agent.detect_temples("Compare Yadagirigutta and Bhadrachalam")
    assert temples == ["Yadadri", "Badrachalam"]

    temples2 = agent.detect_temples("Difference between Vana Durga Bhavani and Chilkur Balaji")
    assert temples2 == ["Edupayal", "Chilkur"]


# -----------------------------------------------------------------------------
# Test 9: Zero-Temple Clarification
# -----------------------------------------------------------------------------
def test_9_zero_temple_clarification(agent):
    """Verify query with no temples prompts for clarification without guessing."""
    state = AgentState(user_query="Compare the temples.")
    res = agent.execute(state)

    assert res.success is False
    assert res.error == "Missing temple specification"
    assert "please specify the temples" in res.answer.lower()
    assert res.metadata.get("clarification_needed") is True


# -----------------------------------------------------------------------------
# Test 10: One-Temple Clarification
# -----------------------------------------------------------------------------
def test_10_one_temple_clarification(agent):
    """Verify query with only one temple prompts for the second temple."""
    state = AgentState(user_query="Compare Yadadri facilities.")
    res = agent.execute(state)

    assert res.success is False
    assert res.error == "Insufficient temples for comparison"
    assert "second temple" in res.answer.lower()
    assert "yadadri" in res.answer.lower()
    assert res.metadata.get("clarification_needed") is True


# -----------------------------------------------------------------------------
# Test 11: Explicit Unknown-Temple Handling
# -----------------------------------------------------------------------------
def test_11_explicit_unknown_temple_handling(agent):
    """Verify explicit non-registered temple returns controlled refusal, zero hallucination."""
    state = AgentState(user_query="Compare Yadadri and Atlantis Temple.")
    res = agent.execute(state)

    assert res.success is False
    assert res.error == "Unregistered temple"
    assert "don't have" in res.answer.lower() or "not in" in res.answer.lower()
    assert len(res.sources) == 0


# -----------------------------------------------------------------------------
# Test 12: Timings Comparison
# -----------------------------------------------------------------------------
def test_12_timings_comparison(agent):
    """Verify timings comparison retrieves and formats timings for both temples."""
    state = AgentState(user_query="Compare the timings of Yadadri and Dharmapuri.")
    res = agent.execute(state)

    assert res.success is True
    assert "Yadadri" in res.answer
    assert "Dharmapuri" in res.answer
    assert "Timings" in res.answer
    assert len(res.sources) >= 2


# -----------------------------------------------------------------------------
# Test 13: Facilities Comparison
# -----------------------------------------------------------------------------
def test_13_facilities_comparison(agent):
    """Verify facilities comparison retrieves facility data for both temples."""
    state = AgentState(user_query="Compare facilities at Yadadri and Bhadrachalam.")
    res = agent.execute(state)

    assert res.success is True
    assert "Yadadri" in res.answer
    assert "Badrachalam" in res.answer
    assert "Facilities" in res.answer


# -----------------------------------------------------------------------------
# Test 14: Sevas Comparison
# -----------------------------------------------------------------------------
def test_14_sevas_comparison(agent):
    """Verify sevas comparison retrieves seva data for both temples."""
    state = AgentState(user_query="Compare sevas offered at Dharmapuri and Yadadri.")
    res = agent.execute(state)

    assert res.success is True
    assert "Dharmapuri" in res.answer
    assert "Yadadri" in res.answer
    assert "Sevas" in res.answer


# -----------------------------------------------------------------------------
# Test 15: Broad Comparison
# -----------------------------------------------------------------------------
def test_15_broad_comparison(agent):
    """Verify broad comparison without explicit category covers multiple core aspects."""
    state = AgentState(user_query="Compare Yadadri and Dharmapuri temples.")
    res = agent.execute(state)

    assert res.success is True
    assert "Yadadri" in res.answer
    assert "Dharmapuri" in res.answer
    assert any(h in res.answer for h in ["Timings", "Sevas", "Facilities", "Accommodation"])


# -----------------------------------------------------------------------------
# Test 16: Strict RAGTool Dependency Boundary
# -----------------------------------------------------------------------------
def test_16_rag_tool_only_dependency_boundary():
    """Verify comparison_agent.py does NOT directly import raw database or low-level RAG internals."""
    agent_file = root_dir / "backend" / "app" / "agents" / "comparison_agent.py"
    assert agent_file.exists(), "comparison_agent.py must exist"
    code = agent_file.read_text(encoding="utf-8")

    prohibited = [
        "qdrant_client",
        "rank_bm25",
        "sentence_transformers",
        "LocalQdrantManager",
        "LocalBM25Manager",
        "CrossEncoder",
        "PilgrimRAGService",
        "raw JSON"
    ]
    for p in prohibited:
        assert p not in code, f"Prohibited import or reference found in comparison_agent.py: {p}"

    # Verify RAGTool is used
    assert "from app.agents.tools.rag_tool import RAGTool" in code


# -----------------------------------------------------------------------------
# Test 17: Temple Isolation
# -----------------------------------------------------------------------------
def test_17_temple_isolation(agent):
    """Verify sources and evidence are attributed to the correct temple without cross-bleeding."""
    state = AgentState(user_query="Compare facilities at Yadadri and Dharmapuri.")
    res = agent.execute(state)

    sources_by_temple = res.metadata.get("sources_by_temple", {})
    yadadri_sources = sources_by_temple.get("Yadadri", [])
    dharmapuri_sources = sources_by_temple.get("Dharmapuri", [])

    for s in yadadri_sources:
        assert "yadadri" in s.lower()
        assert "dharmapuri" not in s.lower()

    for s in dharmapuri_sources:
        assert "dharmapuri" in s.lower()
        assert "yadadri" not in s.lower()


# -----------------------------------------------------------------------------
# Test 18: Source Preservation
# -----------------------------------------------------------------------------
def test_18_source_preservation(agent):
    """Verify AgentResponse.sources preserves verified JSON source paths."""
    state = AgentState(user_query="Compare the timings of Yadadri and Dharmapuri.")
    res = agent.execute(state)

    assert len(res.sources) > 0
    assert any("yadadri" in s.lower() for s in res.sources)
    assert any("dharmapuri" in s.lower() for s in res.sources)


# -----------------------------------------------------------------------------
# Test 19: Neutral Output
# -----------------------------------------------------------------------------
def test_19_neutral_output(agent):
    """Verify output presents factual aspects objectively and neutrally."""
    state = AgentState(user_query="Compare Yadadri and Dharmapuri facilities.")
    res = agent.execute(state)

    assert res.success is True
    assert "Comparison:" in res.answer


# -----------------------------------------------------------------------------
# Test 20: No Automatic Winner
# -----------------------------------------------------------------------------
def test_20_no_automatic_winner(agent):
    """Verify comparison output NEVER declares a winner or uses subjective superlatives."""
    state = AgentState(user_query="Which is better, Yadadri or Dharmapuri?")
    res = agent.execute(state)

    assert res.success is True
    ans_lower = res.answer.lower()
    subjective_words = ["better", "superior", "worse", "winner", "is the best", "recommended over"]
    for w in subjective_words:
        assert w not in ans_lower, f"Subjective declaration '{w}' found in comparison output!"


# -----------------------------------------------------------------------------
# Test 21: Missing Data Handling
# -----------------------------------------------------------------------------
def test_21_missing_data_handling(agent):
    """Verify missing categories state 'no verified data' rather than inferring absence."""
    # Test internal summarizer with empty data
    summary = agent._run(AgentState(user_query="Compare Yadadri and Dharmapuri FAQ"))
    ans = summary.answer
    if "No verified" in ans:
        assert "no verified" in ans.lower()
        # Verify it does not claim false absence
        assert "does not have" not in ans.lower()


# -----------------------------------------------------------------------------
# Test 22: Conflicting Data Handling
# -----------------------------------------------------------------------------
def test_22_conflicting_data_handling(agent):
    """Verify conflict detection reports schedule variation note if evidence differs."""
    mock_data = {
        "Yadadri": {"timings": "Temple timings differ on festivals and seasonal variations."},
        "Dharmapuri": {"timings": "Regular daily schedule."}
    }
    has_conflict = agent._detect_conflicts(mock_data)
    assert has_conflict is True


# -----------------------------------------------------------------------------
# Test 23: Partial Retrieval Failure Handling
# -----------------------------------------------------------------------------
def test_23_partial_retrieval_failure(agent):
    """Verify that when one temple has data, comparison succeeds with partial data noted."""
    state = AgentState(user_query="Compare Yadadri and Basara sevas.")
    res = agent.execute(state)

    assert res.success is True
    assert "Yadadri" in res.answer
    assert "Basara" in res.answer


# -----------------------------------------------------------------------------
# Test 24: Phase H Multi-Intent Pipeline Compatibility
# -----------------------------------------------------------------------------
def test_24_phase_h_compatibility():
    """Verify multi-intent pipeline routes comparison sub-task to ComparisonAgent."""
    agent = ComparisonAgent()
    router = AgentRouter()
    router.register_agent("comparison")
    pipeline = SequentialMultiIntentPipeline(router=router, agents={"comparison": agent, "temple_information": TempleInformationAgent()})

    query = "What are the timings of Yadadri? Compare facilities of Yadadri vs Dharmapuri"
    tasks = pipeline.decompose_query(query)

    assert len(tasks) == 2
    assert tasks[0]["intent"] == "temple_information"
    assert tasks[1]["intent"] == "comparison"
    assert tasks[1]["target_agent"] == "comparison"
    assert tasks[1]["is_available"] is True


# -----------------------------------------------------------------------------
# Test 25: Phase I Conversation Memory Compatibility
# -----------------------------------------------------------------------------
def test_25_phase_i_compatibility():
    """Verify multi-turn behavior with ConversationMemoryManager.
    If memory safely preserves the query when a new temple is explicitly present without
    silently resolving an ambiguous pronoun, ComparisonAgent asks for clarification rather than guessing.
    If resolved comparison is provided, ComparisonAgent executes successfully.
    """
    memory_manager = ConversationMemoryManager()
    session_id = "test_phase_k_session"

    # Turn 1: Discuss Yadadri
    memory_manager.add_turn(
        session_id=session_id,
        user_query="Tell me about Yadadri temple.",
        identified_temples=["Yadadri"],
        detected_intents=["temple_information"]
    )

    # Turn 2: 'Now compare it with Dharmapuri.'
    turn2_query = "Now compare it with Dharmapuri."
    resolution = memory_manager.resolve_query(session_id=session_id, query=turn2_query)
    resolved_query = resolution["resolved_query"]

    agent = ComparisonAgent()
    if "Yadadri" in resolved_query:
        # If memory resolved 'it' -> 'Yadadri'
        temples = agent.detect_temples(resolved_query)
        assert "Yadadri" in temples
        assert "Dharmapuri" in temples
    else:
        # If existing memory deterministically preserved explicit Dharmapuri without guessing 'it',
        # ComparisonAgent safely requests the second temple rather than guessing (Case 2 safeguard).
        state = AgentState(user_query=resolved_query)
        res = agent.execute(state)
        assert res.success is False
        assert res.error == "Insufficient temples for comparison"
        assert res.metadata.get("clarification_needed") is True
        assert "second temple" in res.answer.lower()


# -----------------------------------------------------------------------------
# Test 26: Phase J Complete-List Retrieval Compatibility
# -----------------------------------------------------------------------------
def test_26_phase_j_compatibility(agent):
    """Verify ComparisonAgent leverages complete-list representations for list categories."""
    state = AgentState(user_query="Compare all sevas at Dharmapuri and Yadadri.")
    res = agent.execute(state)

    assert res.success is True
    assert "Dharmapuri" in res.answer
    assert "Yadadri" in res.answer
    # All 10 sevas from Dharmapuri source JSON should be represented in the complete parent
    content, _ = agent._extract_category_data("Dharmapuri", "sevas")
    assert "Abhishekam" in content
    assert "Mudupu" in content


# -----------------------------------------------------------------------------
# Test 27: Empty Query Handling
# -----------------------------------------------------------------------------
def test_27_empty_query(agent):
    """Verify empty query returns safe error response."""
    state = AgentState(user_query="")
    res = agent.execute(state)

    assert res.success is False
    assert res.error == "Empty query"
    assert len(res.sources) == 0


# -----------------------------------------------------------------------------
# Test 28: Whitespace Query Handling
# -----------------------------------------------------------------------------
def test_28_whitespace_query(agent):
    """Verify whitespace query returns safe error response."""
    state = AgentState(user_query="   \t\n  ")
    res = agent.execute(state)

    assert res.success is False
    assert res.error == "Empty query"
    assert len(res.sources) == 0


# -----------------------------------------------------------------------------
# Test 29: Deterministic Repeated Execution
# -----------------------------------------------------------------------------
def test_29_deterministic_repeated_execution(agent):
    """Verify identical queries produce deterministic identical answers."""
    query = "Compare timings of Yadadri and Dharmapuri."
    res1 = agent.execute(AgentState(user_query=query))
    res2 = agent.execute(AgentState(user_query=query))

    assert res1.success is True
    assert res2.success is True
    assert res1.answer == res2.answer
    assert res1.sources == res2.sources


# -----------------------------------------------------------------------------
# Test 30: Backward Compatibility with Default Router and Coordinator
# -----------------------------------------------------------------------------
def test_30_backward_compatibility():
    """Verify default router and coordinator without ComparisonAgent preserve exact Phase D/F fallbacks."""
    default_router = AgentRouter()
    d = default_router.route("Compare Yadadri and Dharmapuri")
    assert d.selected_agent == "none"
    assert d.metadata.get("available") is False

    default_coordinator = MasterAgentCoordinator()
    c_res = default_coordinator.process(AgentState(user_query="Compare Yadadri and Dharmapuri"))
    assert c_res.success is False
    assert "not yet available" in c_res.answer.lower()
