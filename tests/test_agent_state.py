"""
Phase G - AgentState and ExecutionTrace Certification Tests

Verifies:
1. State initialization: valid default construction.
2. Independent mutable defaults: two states do not share lists/dicts.
3. Session identity: session IDs remain distinct/consistent.
4. Intent storage: detected intents can be added safely.
5. Intermediate results: structured intermediate results can be stored and retrieved.
6. Final response: AgentResponse can be assigned to state.final_response.
7. Active agent lifecycle: active-agent state updates predictably during execution.
8. ExecutionTrace creation: all required trace fields are present and typed.
9. Trace ordering: chronological append order is strictly preserved.
10. Trace status: valid representations ('started', 'completed', 'failed', 'skipped').
11. Trace latency: latency is numeric, non-negative, and enforced.
12. Trace error: failed trace records preserve error information without crashing.
13. Trace metadata: structured metadata is supported and sensitive keys are redacted.
14. No RAG dependency: state.py contains zero direct RAG, database, or LLM imports.
15. Existing BaseAgent compatibility: Phase A BaseAgent lifecycle works seamlessly.
16. Existing Coordinator compatibility: Phase F coordinator end-to-end Yadadri flow works.
17. Determinism: repeated state creation and execution produce consistent, uncorrupted structures.
"""

import sys
from pathlib import Path
import pytest

# Ensure backend is in sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState, AgentResponse, AgentRouteDecision, ExecutionTrace
from app.agents.coordinator import MasterAgentCoordinator


class DummyEchoAgent(BaseAgent):
    """Concrete agent double for testing lifecycle transitions."""

    def __init__(self, name="echo_agent", description="Echoes queries"):
        super().__init__(name=name, description=description)

    def _run(self, state: AgentState) -> AgentResponse:
        return AgentResponse(
            success=True,
            agent_name=self.name,
            answer=f"Echo: {state.user_query}",
            sources=["dummy/source.json"],
            metadata={"query_len": len(state.user_query)}
        )


def test_1_state_initialization():
    """Verify default construction of AgentState."""
    state = AgentState()
    assert state.session_id == "default_session"
    assert state.user_query == ""
    assert state.detected_intents == []
    assert state.active_agent is None
    assert state.intermediate_results == {}
    assert state.final_response is None
    assert state.execution_trace == []


def test_2_independent_mutable_defaults():
    """Verify distinct AgentState instances do not share mutable collections."""
    s1 = AgentState()
    s2 = AgentState()

    s1.detected_intents.append("intent_a")
    s1.intermediate_results["agent_a"] = {"val": 1}
    s1.add_trace(agent_name="agent_a", step_name="step_1")

    assert "intent_a" not in s2.detected_intents
    assert len(s2.detected_intents) == 0
    assert "agent_a" not in s2.intermediate_results
    assert len(s2.intermediate_results) == 0
    assert len(s2.execution_trace) == 0


def test_3_session_identity():
    """Verify custom session IDs remain distinct and consistent."""
    s1 = AgentState(session_id="user_sess_101", user_query="Hello")
    s2 = AgentState(session_id="user_sess_102", user_query="World")

    assert s1.session_id == "user_sess_101"
    assert s2.session_id == "user_sess_102"
    assert s1.session_id != s2.session_id


def test_4_intent_storage():
    """Verify detected intents can be appended safely."""
    state = AgentState(user_query="Compare Yadadri and Basara")
    state.detected_intents.append("comparison")
    state.detected_intents.append("temple_information")

    assert len(state.detected_intents) == 2
    assert state.detected_intents == ["comparison", "temple_information"]


def test_5_intermediate_results():
    """Verify structured intermediate results can be stored, retrieved, and queried via helper."""
    state = AgentState(user_query="What are the timings?")
    resp_obj = AgentResponse(
        success=True,
        agent_name="temple_information",
        answer="Opens at 4:00 AM",
        sources=["yadadri.json"]
    )
    state.intermediate_results["temple_information"] = resp_obj

    # Direct retrieval
    assert "temple_information" in state.intermediate_results
    assert state.intermediate_results["temple_information"].answer == "Opens at 4:00 AM"

    # Helper method retrieval
    retrieved = state.get_intermediate_result("temple_information")
    assert retrieved == resp_obj
    assert state.get_intermediate_result("nonexistent", default=None) is None


def test_6_final_response():
    """Verify AgentResponse can be assigned to state.final_response."""
    state = AgentState(user_query="Test query")
    assert state.final_response is None

    final_resp = AgentResponse(
        success=True,
        agent_name="response_aggregator",
        answer="Synthesized answer",
        sources=["source1.json", "source2.json"],
        metadata={"agent_count": 1}
    )
    state.final_response = final_resp

    assert state.final_response is not None
    assert state.final_response.answer == "Synthesized answer"
    assert state.final_response.success is True
    assert len(state.final_response.sources) == 2


def test_7_active_agent_lifecycle():
    """Verify active_agent state transitions during execution and restores afterwards."""
    agent = DummyEchoAgent()
    state = AgentState(user_query="Test active agent transition", active_agent="coordinator")

    assert state.active_agent == "coordinator"
    response = agent.execute(state)

    # During execution it was "echo_agent", restored to "coordinator" in finally block
    assert state.active_agent == "coordinator"
    assert response.success is True
    assert "echo_agent" in state.intermediate_results


def test_8_execution_trace_creation():
    """Verify all required trace fields exist and hold appropriate types."""
    trace = ExecutionTrace(
        agent_name="test_agent",
        step_name="test_step",
        status="completed",
        latency_ms=12.5,
        error=None,
        metadata={"key": "val"}
    )
    assert trace.agent_name == "test_agent"
    assert trace.step_name == "test_step"
    assert trace.status == "completed"
    assert trace.latency_ms == 12.5
    assert trace.error is None
    assert trace.metadata == {"key": "val"}


def test_9_trace_ordering():
    """Verify chronological append ordering of execution trace entries."""
    state = AgentState(user_query="Test trace order")

    state.add_trace(agent_name="coordinator", step_name="start")
    state.add_trace(agent_name="router", step_name="route")
    state.add_trace(agent_name="specialist", step_name="execute")
    state.add_trace(agent_name="aggregator", step_name="aggregate")
    state.add_trace(agent_name="coordinator", step_name="complete")

    assert len(state.execution_trace) == 5
    steps = [t.step_name for t in state.execution_trace]
    assert steps == ["start", "route", "execute", "aggregate", "complete"]

    # Test filtering helper
    coord_traces = state.get_trace(agent_name="coordinator")
    assert len(coord_traces) == 2
    assert [t.step_name for t in coord_traces] == ["start", "complete"]


def test_10_trace_status():
    """Verify supported execution trace statuses (started, completed, failed, skipped)."""
    valid_statuses = ["started", "completed", "failed", "skipped"]
    state = AgentState()

    for st in valid_statuses:
        t = state.add_trace(agent_name="agent", step_name=f"step_{st}", status=st)
        assert t.status == st

    assert len(state.execution_trace) == 4


def test_11_trace_latency():
    """Verify latency is numeric, non-negative, and enforced."""
    state = AgentState()

    # Valid positive latency
    t1 = state.add_trace(agent_name="agent", step_name="step_1", latency_ms=15.4)
    assert t1.latency_ms == 15.4
    assert t1.latency_ms >= 0.0

    # Negative latency auto-corrected to 0.0
    t2 = state.add_trace(agent_name="agent", step_name="step_2", latency_ms=-5.0)
    assert t2.latency_ms == 0.0

    # Direct model construction with negative latency
    t3 = ExecutionTrace(agent_name="agent", step_name="step_3", latency_ms=-10.0)
    assert t3.latency_ms == 0.0


def test_12_trace_error():
    """Verify failed trace records preserve error information without crashing."""
    state = AgentState()
    trace = state.add_trace(
        agent_name="failing_agent",
        step_name="execute",
        status="failed",
        error="Network timeout occurred during execution"
    )
    assert trace.status == "failed"
    assert trace.error == "Network timeout occurred during execution"


def test_13_trace_metadata_and_sanitization():
    """Verify structured metadata is retained and sensitive keys are redacted."""
    state = AgentState()
    trace = state.add_trace(
        agent_name="agent",
        step_name="step",
        metadata={
            "intent": "factual",
            "temple": "Yadadri",
            "api_key": "secret_abc_123",
            "token": "bearer_xyz_999",
            "long_doc": "x" * 2500
        }
    )
    assert trace.metadata["intent"] == "factual"
    assert trace.metadata["temple"] == "Yadadri"
    assert trace.metadata["api_key"] == "[REDACTED]"
    assert trace.metadata["token"] == "[REDACTED]"
    assert trace.metadata["long_doc"].endswith("... [TRUNCATED]")
    assert len(trace.metadata["long_doc"]) < 2100


def test_14_no_rag_dependency():
    """Verify backend/app/agents/state.py contains zero direct RAG, vector DB, or LLM imports."""
    state_file = root_dir / "backend" / "app" / "agents" / "state.py"
    content = state_file.read_text(encoding="utf-8")

    forbidden = [
        "qdrant_client",
        "rank_bm25",
        "sentence_transformers",
        "LocalQdrantManager",
        "LocalBM25Manager",
        "PilgrimRAGService",
        "KnowledgeRegistry",
        "RAGTool",
        "Ollama"
    ]

    for item in forbidden:
        assert item not in content, f"Forbidden import '{item}' detected in state.py!"


def test_15_existing_base_agent_compatibility():
    """Verify Phase A BaseAgent operates seamlessly with enhanced AgentState."""
    agent = DummyEchoAgent()
    state = AgentState(user_query="Compatibility test")

    res = agent.execute(state)
    assert res.success is True
    assert res.answer == "Echo: Compatibility test"
    assert len(state.execution_trace) == 1
    assert state.execution_trace[0].agent_name == "echo_agent"
    assert state.execution_trace[0].status == "completed"
    assert state.execution_trace[0].latency_ms is not None
    assert state.execution_trace[0].latency_ms >= 0.0


def test_16_existing_coordinator_compatibility():
    """Verify live end-to-end flow: Coordinator -> Router -> Specialist -> RAG -> Aggregator -> state.final_response."""
    coordinator = MasterAgentCoordinator()
    state = AgentState(user_query="What are the timings of Yadadri temple?")

    res = coordinator.process(state)

    assert res.success is True
    assert len(res.answer) > 20
    assert len(res.sources) > 0
    assert state.final_response == res
    assert "route_decision" in state.intermediate_results
    assert "temple_information" in state.intermediate_results
    assert len(state.execution_trace) >= 2


def test_17_repeated_execution_determinism():
    """Verify repeated executions with new states produce consistent, uncorrupted structures."""
    for i in range(3):
        s = AgentState(session_id=f"sess_{i}", user_query="Test determinism")
        s.detected_intents.append("test_intent")
        s.add_trace(agent_name="agent", step_name="step", latency_ms=1.0)

        assert s.session_id == f"sess_{i}"
        assert len(s.detected_intents) == 1
        assert len(s.execution_trace) == 1
        assert s.execution_trace[0].step_name == "step"
