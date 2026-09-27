"""
Phase C - TempleInformationAgent Certification Tests

Certifies the TempleInformationAgent against BaseAgent contracts and RAGTool facade:
1. Agent initializes cleanly and inherits from BaseAgent.
2. Factual Yadadri query returns successful, grounded response.
3. Temple identity resolution detects canonical temples accurately and case-insensitively.
4. Temple isolation guarantees non-target temple sources are never included.
5. Unknown temples (e.g., Golden Temple) are rejected with clear clarification, zero hallucination.
6. Empty queries are handled safely without exceptions.
7. Ambiguous queries without temple names request clarification without guessing.
8. Verified RAG sources are properly propagated into AgentResponse.sources.
9. Source code strictly observes the RAGTool dependency boundary (zero raw DB imports).
10. Full BaseAgent lifecycle (timing, tracing, state tracking, intermediate caching) verified.

Integration tests against live local indices — zero data mutation.
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
from app.agents.state import AgentState, AgentResponse
from app.agents.tools.rag_tool import RAGTool
from app.agents.temple_information_agent import TempleInformationAgent


@pytest.fixture(scope="module")
def agent():
    return TempleInformationAgent()


def test_1_agent_initialization(agent):
    """Verify TempleInformationAgent inherits from BaseAgent and has correct identity."""
    assert isinstance(agent, BaseAgent)
    assert agent.name == "temple_information"
    assert "factual" in agent.description.lower()
    assert isinstance(agent.rag_tool, RAGTool)


def test_2_yadadri_factual_query(agent):
    """Verify factual query execution produces successful AgentResponse with answer and sources."""
    state = AgentState(user_query="What are the timings of Yadadri temple?")
    res = agent.execute(state)

    assert isinstance(res, AgentResponse)
    assert res.success is True
    assert res.agent_name == "temple_information"
    assert len(res.answer) > 20
    assert "4:00" in res.answer or "timings" in res.answer.lower() or "open" in res.answer.lower()
    assert len(res.sources) > 0


def test_3_temple_identity_resolution(agent):
    """Verify temple identity is accurately detected from various query phrasings and casings."""
    assert agent.detect_temple("what are the timings of yadadri temple?") == "Yadadri"
    assert agent.detect_temple("Tell me about BASARA temple history") == "Basara"
    assert agent.detect_temple("Where is Bhadrachalam temple located?") == "Badrachalam"
    assert agent.detect_temple("What sevas are performed at Dharmapuri?") == "Dharmapuri"
    assert agent.detect_temple("Darshan schedule for Srisailam") == "Srisaila"


def test_4_temple_isolation(agent):
    """Verify responses and sources for a specific temple do not bleed into other temples."""
    state = AgentState(user_query="What are the timings of Yadadri temple?")
    res = agent.execute(state)

    assert res.success is True
    assert len(res.sources) > 0
    # Every source must belong strictly to Yadadri
    for src in res.sources:
        assert "yadadri" in src.lower(), f"Isolation breach: Source '{src}' does not belong to Yadadri!"
        assert "dharmapuri" not in src.lower()
        assert "chilkur" not in src.lower()
        assert "basara" not in src.lower()


def test_5_unknown_temple_rejection(agent):
    """Verify queries for temples outside the 20 registered temples are cleanly refused."""
    state = AgentState(user_query="What are the timings of Golden Temple in Amritsar?")
    res = agent.execute(state)

    assert res.success is False
    assert res.error == "Unregistered temple"
    assert "don't have" in res.answer.lower() or "knowledge base" in res.answer.lower() or "20 major" in res.answer.lower()
    # Confirm no hallucinated timings or fabricated sources
    assert len(res.sources) == 0


def test_6_empty_query_handling(agent):
    """Verify empty or whitespace queries return clean error responses."""
    state = AgentState(user_query="    ")
    res = agent.execute(state)

    assert res.success is False
    assert res.error == "Empty query"
    assert "valid" in res.answer.lower()
    assert len(res.sources) == 0


def test_7_no_temple_identified_requests_clarification(agent):
    """Verify temple queries lacking a specific temple ask for clarification without guessing."""
    state = AgentState(user_query="What are the temple timings?")
    res = agent.execute(state)

    assert res.success is False
    assert res.error == "Missing temple specification"
    assert "which temple" in res.answer.lower()
    assert len(res.sources) == 0


def test_8_source_propagation(agent):
    """Verify RAGTool source filenames are preserved in AgentResponse."""
    state = AgentState(user_query="What are the timings of Yadadri temple?")
    res = agent.execute(state)

    assert len(res.sources) > 0
    assert any(".json" in src for src in res.sources)
    assert res.metadata.get("temple") == "Yadadri"
    assert res.metadata.get("confidence_score", -999) > -3.0


def test_9_rag_tool_only_dependency_boundary():
    """Verify TempleInformationAgent source does NOT import low-level DB drivers or RAG internals directly."""
    agent_file = root_dir / "backend" / "app" / "agents" / "temple_information_agent.py"
    content = agent_file.read_text(encoding="utf-8")

    prohibited_imports = [
        "qdrant_client",
        "rank_bm25",
        "sentence_transformers",
        "LocalQdrantManager",
        "LocalBM25Manager",
        "PilgrimRAGService",
        "KnowledgeRegistry"
    ]

    for item in prohibited_imports:
        assert item not in content, f"Dependency boundary violation: '{item}' imported directly into TempleInformationAgent!"


def test_10_base_agent_lifecycle(agent):
    """Verify BaseAgent execution lifecycle properly records trace, timing, and intermediate state."""
    state = AgentState(user_query="What are the timings of Yadadri temple?")
    assert len(state.execution_trace) == 0
    assert "temple_information" not in state.intermediate_results

    res = agent.execute(state)

    # Verify execution trace recorded
    assert len(state.execution_trace) == 1
    trace = state.execution_trace[0]
    assert trace.agent_name == "temple_information"
    assert trace.step_name == "execute"
    assert trace.status == "completed"
    assert trace.latency_ms is not None
    assert trace.latency_ms > 0

    # Verify intermediate result populated in state
    assert "temple_information" in state.intermediate_results
    assert state.intermediate_results["temple_information"] == res
    assert res.latency_ms is not None
    assert res.latency_ms > 0
