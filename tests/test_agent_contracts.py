"""
Phase A Contract Certification Tests

Verifies:
1. BaseAgent is an abstract class and cannot be instantiated directly.
2. Concrete dummy agents can inherit and implement BaseAgent.
3. Successful execution lifecycle produces standardized AgentResponse.
4. Execution trace is recorded in AgentState with accurate step name and status.
5. Execution timing (latency_ms) is measured and recorded.
6. Unhandled exceptions in specialist agents are gracefully captured without crashing.
7. AgentState can be instantiated with default and custom values.
8. AgentRouteDecision can be instantiated and validated.
9. AgentResponse can be instantiated and validated.
10. Active agent state transitions properly during and after execution.

100% Deterministic — Zero RAG, Vector DB, or LLM dependencies.
"""

import sys
import time
import pytest
from pathlib import Path

# Ensure backend is in sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState, AgentResponse, AgentRouteDecision, ExecutionTrace


class DummyEchoAgent(BaseAgent):
    """Minimal concrete implementation of BaseAgent for testing."""

    def __init__(self, name="DummyEcho", description="Echoes queries for test"):
        super().__init__(name=name, description=description)

    def _run(self, state: AgentState) -> AgentResponse:
        # Simulate slight processing time
        time.sleep(0.005)
        return AgentResponse(
            success=True,
            agent_name=self.name,
            answer=f"Processed: {state.user_query}",
            sources=["dummy/source.json"],
            metadata={"processed_chars": len(state.user_query)}
        )


class DummyFailingAgent(BaseAgent):
    """Concrete agent that deliberately raises an unexpected exception."""

    def __init__(self, name="DummyFailing", description="Fails intentionally"):
        super().__init__(name=name, description=description)

    def _run(self, state: AgentState) -> AgentResponse:
        raise ValueError("Simulated unexpected specialist agent failure")


def test_1_base_agent_is_abstract():
    """Verify BaseAgent cannot be directly instantiated."""
    with pytest.raises(TypeError) as excinfo:
        BaseAgent(name="AbstractAgent", description="Should fail")  # type: ignore
    assert "abstract" in str(excinfo.value).lower()


def test_2_dummy_agent_inheritance():
    """Verify a concrete specialist can properly inherit from BaseAgent."""
    agent = DummyEchoAgent()
    assert agent.name == "DummyEcho"
    assert agent.description == "Echoes queries for test"
    assert isinstance(agent, BaseAgent)


def test_3_and_4_successful_execution_and_response():
    """Verify execution lifecycle produces standardized AgentResponse."""
    agent = DummyEchoAgent()
    state = AgentState(user_query="Tell me about temple history")

    response = agent.execute(state)

    assert isinstance(response, AgentResponse)
    assert response.success is True
    assert response.agent_name == "DummyEcho"
    assert response.answer == "Processed: Tell me about temple history"
    assert response.sources == ["dummy/source.json"]
    assert response.metadata.get("processed_chars") == len("Tell me about temple history")
    assert response.error is None


def test_5_execution_trace_recorded():
    """Verify that execute() appends a structured ExecutionTrace into AgentState."""
    agent = DummyEchoAgent()
    state = AgentState(user_query="Test trace recording")

    assert len(state.execution_trace) == 0
    agent.execute(state)

    assert len(state.execution_trace) == 1
    trace = state.execution_trace[0]
    assert isinstance(trace, ExecutionTrace)
    assert trace.agent_name == "DummyEcho"
    assert trace.step_name == "execute"
    assert trace.status == "completed"
    assert trace.error is None
    assert trace.metadata.get("processed_chars") == len("Test trace recording")


def test_6_execution_timing_recorded():
    """Verify execution latency is measured and recorded in milliseconds."""
    agent = DummyEchoAgent()
    state = AgentState(user_query="Latency test")

    response = agent.execute(state)

    assert response.latency_ms is not None
    assert response.latency_ms > 0.0
    trace = state.execution_trace[0]
    assert trace.latency_ms is not None
    assert trace.latency_ms > 0.0


def test_7_agent_error_captured_consistently():
    """Verify that unhandled exceptions in agent logic are safely caught and formatted."""
    agent = DummyFailingAgent()
    state = AgentState(user_query="Trigger error")

    response = agent.execute(state)

    assert isinstance(response, AgentResponse)
    assert response.success is False
    assert response.agent_name == "DummyFailing"
    assert response.error is not None
    assert "ValueError" in response.error
    assert "Simulated unexpected specialist agent failure" in response.error

    # Verify trace shows failure
    assert len(state.execution_trace) == 1
    trace = state.execution_trace[0]
    assert trace.status == "failed"
    assert trace.error is not None
    assert "ValueError" in trace.error


def test_8_agent_state_creation():
    """Verify AgentState initialization with defaults and custom attributes."""
    # Defaults
    s1 = AgentState()
    assert s1.session_id == "default_session"
    assert s1.user_query == ""
    assert s1.detected_intents == []
    assert s1.active_agent is None
    assert s1.intermediate_results == {}
    assert s1.final_response is None
    assert s1.execution_trace == []

    # Custom attributes & trace helper
    s2 = AgentState(session_id="session_123", user_query="What are the sevas?")
    assert s2.session_id == "session_123"
    assert s2.user_query == "What are the sevas?"

    s2.add_trace(agent_name="Planner", step_name="detect_intent", status="completed")
    assert len(s2.execution_trace) == 1
    assert s2.execution_trace[0].agent_name == "Planner"


def test_9_agent_route_decision_creation():
    """Verify AgentRouteDecision data contract instantiation and fields."""
    decision = AgentRouteDecision(
        selected_agent="TempleInformationAgent",
        intent="targeted_fact",
        confidence=0.95,
        reason="Query asks for single-temple timings",
        metadata={"temple": "Yadadri", "category": "timings"}
    )
    assert decision.selected_agent == "TempleInformationAgent"
    assert decision.intent == "targeted_fact"
    assert decision.confidence == 0.95
    assert decision.reason == "Query asks for single-temple timings"
    assert decision.metadata["temple"] == "Yadadri"


def test_10_agent_response_creation():
    """Verify AgentResponse creation and dictionary serialization."""
    res = AgentResponse(
        success=True,
        agent_name="ComparisonAgent",
        answer="Comparison between Yadadri and Basara",
        sources=["yadadri/temple.json", "basara/temple.json"],
        metadata={"temples": ["Yadadri", "Basara"]},
        latency_ms=12.4
    )
    assert res.success is True
    assert len(res.sources) == 2
    assert res.metadata["temples"] == ["Yadadri", "Basara"]

    dumped = res.model_dump()
    assert dumped["agent_name"] == "ComparisonAgent"
    assert dumped["success"] is True


def test_11_active_agent_lifecycle_transition():
    """Verify active_agent in AgentState is set during execution and restored afterwards."""
    agent = DummyEchoAgent()
    state = AgentState(user_query="State transition test", active_agent="Coordinator")

    assert state.active_agent == "Coordinator"
    agent.execute(state)
    assert state.active_agent == "Coordinator"  # Restored after execution
    assert "DummyEcho" in state.intermediate_results
