"""
Phase E - ResponseAggregator Certification Tests

Verifies deterministic response composition against Phase A contracts:
1. Aggregator initializes cleanly without database or model overhead.
2. Single successful response preserves answer, sources, metadata, and agent name.
3. Multiple successful responses are combined in order without fact invention.
4. Source paths from distinct agents are merged cleanly.
5. Duplicate sources are deduplicated preserving first-seen order.
6. Metadata from multiple agents survives into merged metadata payload.
7. Mixed success/failure preserves successful content without fabricating failed content.
8. All-failed inputs produce a controlled unsuccessful AgentResponse with descriptive errors.
9. Empty input list is handled safely without crashing.
10. Duplicate identical responses are deduplicated.
11. Conflicting factual assertions are preserved with explicit conflict notice.
12. Strict dependency boundary (zero database, reranker, or LLM imports).
13. Determinism check (10 repeated runs yield 100% identical outputs).

100% In-memory, deterministic unit tests — zero network or database dependencies.
"""

import sys
from pathlib import Path
import pytest

# Ensure backend is in sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.state import AgentResponse
from app.agents.response_aggregator import ResponseAggregator


@pytest.fixture(scope="module")
def aggregator():
    return ResponseAggregator()


def test_1_aggregator_initialization(aggregator):
    """Verify ResponseAggregator initializes and exposes aggregate() method."""
    assert aggregator is not None
    assert hasattr(aggregator, "aggregate")


def test_2_single_successful_response(aggregator):
    """Verify single successful response is preserved faithfully."""
    r = AgentResponse(
        success=True,
        agent_name="temple_information",
        answer="Yadadri temple is open daily from 4:00 AM to 9:45 PM.",
        sources=["yadadri/timings.json", "yadadri/faq.json"],
        metadata={"temple": "Yadadri", "category": "timings"},
        latency_ms=150.0
    )

    res = aggregator.aggregate([r])

    assert isinstance(res, AgentResponse)
    assert res.success is True
    assert res.answer == r.answer
    assert res.sources == r.sources
    assert res.agent_name == "temple_information"
    assert res.metadata.get("temple") == "Yadadri"
    assert res.error is None


def test_3_multiple_successful_responses(aggregator):
    """Verify multiple successful responses are combined cleanly in order."""
    r1 = AgentResponse(
        success=True,
        agent_name="temple_information",
        answer="Yadadri temple is open daily from 4:00 AM to 9:45 PM.",
        sources=["yadadri/timings.json"]
    )
    r2 = AgentResponse(
        success=True,
        agent_name="travel_information",
        answer="Yadadri can be reached from Hyderabad by TSRTC buses and local trains.",
        sources=["yadadri/travel.json"]
    )

    res = aggregator.aggregate([r1, r2])

    assert res.success is True
    assert r1.answer in res.answer
    assert r2.answer in res.answer
    # Output order preserved
    pos1 = res.answer.find(r1.answer)
    pos2 = res.answer.find(r2.answer)
    assert pos1 < pos2
    assert "yadadri/timings.json" in res.sources
    assert "yadadri/travel.json" in res.sources


def test_4_source_merging(aggregator):
    """Verify sources from distinct agents are combined into a single list."""
    r1 = AgentResponse(success=True, answer="A", sources=["s1.json", "s2.json"])
    r2 = AgentResponse(success=True, answer="B", sources=["s3.json"])

    res = aggregator.aggregate([r1, r2])
    assert res.sources == ["s1.json", "s2.json", "s3.json"]


def test_5_duplicate_source_handling(aggregator):
    """Verify duplicate source paths are deduplicated."""
    r1 = AgentResponse(success=True, answer="A", sources=["shared.json", "unique1.json"])
    r2 = AgentResponse(success=True, answer="B", sources=["shared.json", "unique2.json"])

    res = aggregator.aggregate([r1, r2])
    assert res.sources == ["shared.json", "unique1.json", "unique2.json"]
    assert res.sources.count("shared.json") == 1


def test_6_metadata_merging(aggregator):
    """Verify useful metadata from individual agents survives aggregation."""
    r1 = AgentResponse(
        success=True,
        agent_name="agent_a",
        answer="A",
        metadata={"key_a": 100}
    )
    r2 = AgentResponse(
        success=True,
        agent_name="agent_b",
        answer="B",
        metadata={"key_b": "value_b"}
    )

    res = aggregator.aggregate([r1, r2])
    assert res.metadata["agent_count"] == 2
    assert "agent_a" in res.metadata["agents"]
    assert "agent_b" in res.metadata["agents"]
    assert res.metadata.get("key_a") == 100
    assert res.metadata.get("key_b") == "value_b"


def test_7_one_failed_one_successful(aggregator):
    """Verify partial failure preserves successful output while noting failure."""
    r_ok = AgentResponse(
        success=True,
        agent_name="temple_info",
        answer="Dharmapuri temple is dedicated to Lord Narasimha.",
        sources=["dharmapuri/temple.json"]
    )
    r_fail = AgentResponse(
        success=False,
        agent_name="weather_agent",
        answer="",
        error="Weather service offline"
    )

    res = aggregator.aggregate([r_ok, r_fail])
    assert res.success is True
    assert "Dharmapuri temple" in res.answer
    assert "dharmapuri/temple.json" in res.sources
    assert res.metadata.get("partial_failure") is True
    assert "weather_agent" in res.metadata.get("failed_agents", [])


def test_8_all_responses_failed(aggregator):
    """Verify all-failed responses produce an unsuccessful AgentResponse with details."""
    r1 = AgentResponse(success=False, agent_name="agent_1", error="Timeout")
    r2 = AgentResponse(success=False, agent_name="agent_2", error="Resource not found")

    res = aggregator.aggregate([r1, r2])
    assert res.success is False
    assert res.answer == ""
    assert "agent_1" in res.error
    assert "Timeout" in res.error
    assert "agent_2" in res.error
    assert "Resource not found" in res.error


def test_9_empty_input(aggregator):
    """Verify aggregate([]) returns a safe, controlled failure without raising unhandled errors."""
    res = aggregator.aggregate([])
    assert isinstance(res, AgentResponse)
    assert res.success is False
    assert "No agent responses" in res.error
    assert res.answer == ""


def test_10_duplicate_response(aggregator):
    """Verify identical duplicate responses are deduplicated without repetition."""
    r = AgentResponse(
        success=True,
        agent_name="temple_info",
        answer="Basara temple is situated on the Godavari river bank.",
        sources=["basara/river_bank.json"]
    )

    res = aggregator.aggregate([r, r])
    assert res.success is True
    assert res.answer == r.answer
    assert res.sources == ["basara/river_bank.json"]


def test_11_conflicting_information(aggregator):
    """Verify conflicting factual statements are preserved and clearly flagged without picking a winner."""
    r1 = AgentResponse(
        success=True,
        agent_name="primary_schedule_agent",
        answer="Yadadri temple opens daily at 4:00 AM."
    )
    r2 = AgentResponse(
        success=True,
        agent_name="festival_schedule_agent",
        answer="Yadadri temple opens daily at 5:00 AM."
    )

    res = aggregator.aggregate([r1, r2])
    assert res.success is True
    assert res.metadata.get("has_conflict") is True
    # Both conflicting assertions must be present in the output
    assert "4:00 AM" in res.answer
    assert "5:00 AM" in res.answer
    assert "primary_schedule_agent" in res.answer
    assert "festival_schedule_agent" in res.answer
    assert "differs" in res.answer.lower() or "conflict" in res.answer.lower()


def test_12_no_forbidden_dependencies():
    """Verify response_aggregator.py contains zero imports of databases, models, or RAG internals."""
    file_path = root_dir / "backend" / "app" / "agents" / "response_aggregator.py"
    content = file_path.read_text(encoding="utf-8")

    forbidden = [
        "qdrant_client",
        "rank_bm25",
        "sentence_transformers",
        "PilgrimRAGService",
        "KnowledgeRegistry",
        "RAGTool",
        "Ollama"
    ]

    for item in forbidden:
        assert item not in content, f"Forbidden import '{item}' found in response_aggregator.py!"


def test_13_determinism(aggregator):
    """Verify aggregator outputs are 100% identical across repeated invocations."""
    r1 = AgentResponse(success=True, agent_name="agent_a", answer="Answer A", sources=["s_a.json"])
    r2 = AgentResponse(success=True, agent_name="agent_b", answer="Answer B", sources=["s_b.json"])

    outputs = [aggregator.aggregate([r1, r2]) for _ in range(10)]
    first = outputs[0]

    for o in outputs[1:]:
        assert o.success == first.success
        assert o.answer == first.answer
        assert o.sources == first.sources
        assert o.error == first.error
        assert o.metadata["agent_count"] == first.metadata["agent_count"]
        assert o.metadata["agents"] == first.metadata["agents"]
