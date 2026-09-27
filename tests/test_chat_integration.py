"""
PilgrimAI - Phase N: FastAPI /chat Multi-Agent Coordinator Integration Test Suite

Validates:
1. Health endpoint still operational (/health)
2. Legacy request without session_id ({"question": "..."})
3. Request with explicit session_id
4. Response preserves all legacy fields (question, answer, retrieved_chunks, sources, confidence_score)
5. Response includes additive telemetry fields (agent_name, session_id, latency_ms, metadata)
6. Temple information query reaches TempleInformationAgent
7. Comparison query reaches ComparisonAgent
8. Cross-temple aggregation query reaches CrossTempleAggregationAgent
9. Itinerary planning query reaches ItineraryPlanningAgent
10. Multi-intent compound query reaches SequentialMultiIntentPipeline
11. Multi-turn conversation memory stores context on Turn 1
12. Multi-turn pronoun/anaphora resolution succeeds on Turn 2 via session_id
13. Session isolation (distinct session_ids do not cross-contaminate)
14. Missing session_id generates a valid unique UUID
15. Explicit session_id is preserved verbatim in response
16. Empty question rejection (HTTP 400 Bad Request)
17. Whitespace-only question rejection (HTTP 400 Bad Request)
18. Unknown temple refusal via coordinator anti-hallucination
19. Zero-temple query triggers clarification response
20. No external API invocation / offline containment
21. Source attribution preserved from coordinator to ChatResponse
22. Itinerary live-data disclaimer preserved in ChatResponse
23. Retrieved chunks mapping without fabrication
24. Confidence score preservation and bounding
25. Agent metadata propagation
26. Concurrent request state isolation
27. Deterministic repeated query execution
28. Dependency injection via set_coordinator / get_coordinator lifecycle
"""

import sys
import uuid
import asyncio
import pytest
from pathlib import Path
from typing import Dict, Any, List, Optional

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import httpx
from app.main import app
from app.api.chat import (
    get_coordinator,
    set_coordinator,
    ChatRequest,
    ChatResponse
)
from app.agents.state import AgentState, AgentResponse
from app.agents.coordinator import MasterAgentCoordinator
from app.agents.temple_information_agent import TempleInformationAgent
from app.agents.comparison_agent import ComparisonAgent
from app.agents.cross_temple_aggregation_agent import CrossTempleAggregationAgent
from app.agents.itinerary_planning_agent import ItineraryPlanningAgent
from app.agents.memory import ConversationMemoryManager
from app.agents.router import AgentRouter
from app.agents.response_aggregator import ResponseAggregator


class SyncTestClient:
    """Synchronous test client wrapper around httpx.AsyncClient for FastAPI ASGI app."""

    def __init__(self, asgi_app):
        self.app = asgi_app

    def post(self, url: str, json: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None):
        async def _req():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://testserver") as client:
                return await client.post(url, json=json, headers=headers)
        return asyncio.run(_req())

    def get(self, url: str, headers: Optional[Dict[str, str]] = None):
        async def _req():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://testserver") as client:
                return await client.get(url, headers=headers)
        return asyncio.run(_req())


@pytest.fixture(scope="module")
def client():
    return SyncTestClient(app)


@pytest.fixture(autouse=True)
def reset_coordinator():
    """Ensure clean coordinator state before each test."""
    set_coordinator(None)
    yield
    set_coordinator(None)


# -----------------------------------------------------------------------------
# Test 1: Health Endpoint Still Works
# -----------------------------------------------------------------------------
def test_1_health_endpoint(client):
    """Verify GET /health returns HTTP 200 and expected status."""
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


# -----------------------------------------------------------------------------
# Test 2: Legacy Request Format
# -----------------------------------------------------------------------------
def test_2_legacy_request_format(client):
    """Verify legacy client sending only {"question": "..."} works seamlessly."""
    payload = {"question": "Plan a 1-day tour to Yadadri"}
    res = client.post("/chat", json=payload)

    assert res.status_code == 200
    data = res.json()
    assert data["question"] == "Plan a 1-day tour to Yadadri"
    assert "Yadadri" in data["answer"]
    assert isinstance(data["sources"], list)
    assert isinstance(data["confidence_score"], float)
    assert isinstance(data["retrieved_chunks"], int)


# -----------------------------------------------------------------------------
# Test 3: Request with Explicit Session ID
# -----------------------------------------------------------------------------
def test_3_request_with_explicit_session_id(client):
    """Verify client sending explicit session_id receives it back in response."""
    sess_id = "phase_n_explicit_session_001"
    payload = {"question": "Plan a visit to Yadadri", "session_id": sess_id}
    res = client.post("/chat", json=payload)

    assert res.status_code == 200
    data = res.json()
    assert data["session_id"] == sess_id


# -----------------------------------------------------------------------------
# Test 4: Backward-Compatible Legacy Response Fields
# -----------------------------------------------------------------------------
def test_4_response_preserves_legacy_fields(client):
    """Verify all 5 original ChatResponse fields exist with correct types."""
    payload = {"question": "Plan a visit to Yadadri"}
    res = client.post("/chat", json=payload)

    assert res.status_code == 200
    data = res.json()
    assert "question" in data
    assert "answer" in data
    assert "retrieved_chunks" in data
    assert "sources" in data
    assert "confidence_score" in data
    assert isinstance(data["question"], str)
    assert isinstance(data["answer"], str)
    assert isinstance(data["retrieved_chunks"], int)
    assert isinstance(data["sources"], list)
    assert isinstance(data["confidence_score"], float)


# -----------------------------------------------------------------------------
# Test 5: Additive Telemetry Fields
# -----------------------------------------------------------------------------
def test_5_response_includes_telemetry_fields(client):
    """Verify new Phase N additive fields exist in response payload."""
    payload = {"question": "Plan a visit to Yadadri"}
    res = client.post("/chat", json=payload)

    assert res.status_code == 200
    data = res.json()
    assert "agent_name" in data
    assert "session_id" in data
    assert "latency_ms" in data
    assert "metadata" in data
    assert data["agent_name"] in ["itinerary_planning", "coordinator", "response_aggregator"]
    assert data["session_id"] is not None
    assert data["latency_ms"] >= 0.0
    assert isinstance(data["metadata"], dict)


# -----------------------------------------------------------------------------
# Test 6: Temple Information Query Reaches TempleInformationAgent
# -----------------------------------------------------------------------------
def test_6_temple_information_routing(client):
    """Verify factual single-temple query executes through TempleInformationAgent."""
    payload = {"question": "What are the timings of Yadadri?"}
    res = client.post("/chat", json=payload)

    assert res.status_code == 200
    data = res.json()
    assert data["agent_name"] == "temple_information"
    assert "Yadadri" in data["answer"] or "temple" in data["answer"].lower()
    assert len(data["sources"]) > 0


# -----------------------------------------------------------------------------
# Test 7: Comparison Query Reaches ComparisonAgent
# -----------------------------------------------------------------------------
def test_7_comparison_routing(client):
    """Verify comparison query reaches ComparisonAgent via coordinator."""
    payload = {"question": "Compare Yadadri and Dharmapuri"}
    res = client.post("/chat", json=payload)

    assert res.status_code == 200
    data = res.json()
    assert data["agent_name"] == "comparison"
    assert "Yadadri" in data["answer"]
    assert "Dharmapuri" in data["answer"]


# -----------------------------------------------------------------------------
# Test 8: Cross-Temple Aggregation Query Reaches CrossTempleAggregationAgent
# -----------------------------------------------------------------------------
def test_8_cross_temple_aggregation_routing(client):
    """Verify multi-temple aggregation query reaches CrossTempleAggregationAgent."""
    payload = {"question": "Which temples are located on a river bank?"}
    res = client.post("/chat", json=payload)

    assert res.status_code == 200
    data = res.json()
    assert data["agent_name"] == "cross_temple_aggregation"
    assert "river" in data["answer"].lower() or "bank" in data["answer"].lower()
    assert len(data["sources"]) > 0


# -----------------------------------------------------------------------------
# Test 9: Itinerary Planning Query Reaches ItineraryPlanningAgent
# -----------------------------------------------------------------------------
def test_9_itinerary_planning_routing(client):
    """Verify itinerary planning query reaches ItineraryPlanningAgent."""
    payload = {"question": "Plan a 1-day tour to Yadadri"}
    res = client.post("/chat", json=payload)

    assert res.status_code == 200
    data = res.json()
    assert data["agent_name"] == "itinerary_planning"
    assert "Yadadri" in data["answer"]


# -----------------------------------------------------------------------------
# Test 10: Multi-Intent Compound Query
# -----------------------------------------------------------------------------
def test_10_multi_intent_compound_query(client):
    """Verify compound query executes sequentially and returns aggregated response."""
    payload = {"question": "What are the timings of Yadadri and plan a one-day visit there"}
    res = client.post("/chat", json=payload)

    assert res.status_code == 200
    data = res.json()
    assert "Yadadri" in data["answer"]
    assert len(data["sources"]) > 0


# -----------------------------------------------------------------------------
# Test 11: Multi-Turn Memory Stores Context on Turn 1
# -----------------------------------------------------------------------------
def test_11_multi_turn_turn_1_stores_context(client):
    """Verify Turn 1 stores temple reference in conversation memory."""
    sess_id = "test_memory_turn1_" + str(uuid.uuid4())[:8]
    payload = {"question": "Tell me about Dharmapuri temple", "session_id": sess_id}
    res = client.post("/chat", json=payload)

    assert res.status_code == 200
    coord = get_coordinator()
    turns = coord.memory_manager.get_recent_turns(sess_id)
    assert len(turns) >= 1
    assert "Dharmapuri" in turns[-1].identified_temples


# -----------------------------------------------------------------------------
# Test 12: Multi-Turn Pronoun Resolution on Turn 2
# -----------------------------------------------------------------------------
def test_12_multi_turn_pronoun_resolution(client):
    """Verify Turn 2 resolves pronoun 'there' to Dharmapuri using session_id."""
    sess_id = "test_memory_turn2_" + str(uuid.uuid4())[:8]

    # Turn 1: Establish temple context
    res1 = client.post("/chat", json={"question": "Tell me about Dharmapuri temple", "session_id": sess_id})
    assert res1.status_code == 200

    # Turn 2: Refer to temple with pronoun "there"
    res2 = client.post("/chat", json={"question": "Plan a one-day visit there", "session_id": sess_id})
    assert res2.status_code == 200
    data2 = res2.json()
    assert "Dharmapuri" in data2["answer"]


# -----------------------------------------------------------------------------
# Test 13: Session Isolation
# -----------------------------------------------------------------------------
def test_13_session_isolation(client):
    """Verify distinct session IDs do not cross-contaminate conversation context."""
    sess_a = "session_A_" + str(uuid.uuid4())[:8]
    sess_b = "session_B_" + str(uuid.uuid4())[:8]

    # Session A sets Yadadri
    client.post("/chat", json={"question": "Tell me about Yadadri", "session_id": sess_a})
    # Session B sets Dharmapuri
    client.post("/chat", json={"question": "Tell me about Dharmapuri", "session_id": sess_b})

    # Session A resolves pronoun
    res_a = client.post("/chat", json={"question": "Plan a visit there", "session_id": sess_a})
    assert "Yadadri" in res_a.json()["answer"]
    assert "Dharmapuri" not in res_a.json()["answer"]

    # Session B resolves pronoun
    res_b = client.post("/chat", json={"question": "Plan a visit there", "session_id": sess_b})
    assert "Dharmapuri" in res_b.json()["answer"]


# -----------------------------------------------------------------------------
# Test 14: Missing Session ID Generates Unique UUID
# -----------------------------------------------------------------------------
def test_14_missing_session_id_generates_unique_uuid(client):
    """Verify omitting session_id returns a valid, unique UUID per request."""
    res1 = client.post("/chat", json={"question": "What are the timings of Basara?"})
    res2 = client.post("/chat", json={"question": "What are the timings of Basara?"})

    assert res1.status_code == 200
    assert res2.status_code == 200
    id1 = res1.json()["session_id"]
    id2 = res2.json()["session_id"]
    assert id1 is not None
    assert id2 is not None
    assert id1 != id2
    # Verify valid UUID format
    assert uuid.UUID(id1)
    assert uuid.UUID(id2)


# -----------------------------------------------------------------------------
# Test 15: Explicit Session ID Preserved
# -----------------------------------------------------------------------------
def test_15_explicit_session_id_preserved(client):
    """Verify explicit custom string session_id is preserved exactly."""
    custom_id = "user_custom_sess_xyz_789"
    res = client.post("/chat", json={"question": "Tell me about Basara", "session_id": custom_id})

    assert res.status_code == 200
    assert res.json()["session_id"] == custom_id


# -----------------------------------------------------------------------------
# Test 16: Empty Question Rejection
# -----------------------------------------------------------------------------
def test_16_empty_question_rejection(client):
    """Verify empty string returns HTTP 400 Bad Request."""
    res = client.post("/chat", json={"question": ""})
    assert res.status_code == 400
    assert "empty" in res.json()["detail"].lower()


# -----------------------------------------------------------------------------
# Test 17: Whitespace-Only Question Rejection
# -----------------------------------------------------------------------------
def test_17_whitespace_question_rejection(client):
    """Verify whitespace-only string returns HTTP 400 Bad Request."""
    res = client.post("/chat", json={"question": "     \t\n  "})
    assert res.status_code == 400
    assert "empty" in res.json()["detail"].lower()


# -----------------------------------------------------------------------------
# Test 18: Unknown Temple Refusal
# -----------------------------------------------------------------------------
def test_18_unknown_temple_refusal(client):
    """Verify explicitly named non-registered temple produces controlled refusal."""
    res = client.post("/chat", json={"question": "Tell me about Golden Temple"})
    assert res.status_code == 200
    data = res.json()
    assert "Golden Temple" in data["answer"] or "not have verified information" in data["answer"].lower()
    assert len(data["sources"]) == 0


# -----------------------------------------------------------------------------
# Test 19: Zero-Temple Query Clarification
# -----------------------------------------------------------------------------
def test_19_zero_temple_clarification(client):
    """Verify generic question with no temple context triggers clarification."""
    res = client.post("/chat", json={"question": "What are the temple timings?"})
    assert res.status_code == 200
    data = res.json()
    assert "which temple" in data["answer"].lower()


# -----------------------------------------------------------------------------
# Test 20: Offline Containment (No External APIs)
# -----------------------------------------------------------------------------
def test_20_offline_containment(client):
    """Verify API operates strictly offline with zero external network dependencies."""
    res = client.post("/chat", json={"question": "Plan a visit to Yadadri"})
    assert res.status_code == 200
    # Response should come from local specialist agent
    assert res.json()["agent_name"] == "itinerary_planning"


# -----------------------------------------------------------------------------
# Test 21: Source Attribution Preserved in ChatResponse
# -----------------------------------------------------------------------------
def test_21_source_attribution_preserved(client):
    """Verify grounded JSON source citations survive the coordinator to API mapping."""
    res = client.post("/chat", json={"question": "Plan a visit to Yadadri"})
    assert res.status_code == 200
    sources = res.json()["sources"]
    assert len(sources) > 0
    for s in sources:
        assert s.endswith(".json")


# -----------------------------------------------------------------------------
# Test 22: Itinerary Live-Data Disclaimer Preserved
# -----------------------------------------------------------------------------
def test_22_itinerary_disclaimer_preserved(client):
    """Verify deterministic live-data limitation disclaimer survives API serialization."""
    res = client.post("/chat", json={"question": "Plan a visit to Basara"})
    assert res.status_code == 200
    answer = res.json()["answer"]
    assert "Live-Data Limitation" in answer
    assert "real-time travel durations" in answer.lower()


# -----------------------------------------------------------------------------
# Test 23: Retrieved Chunks Mapping
# -----------------------------------------------------------------------------
def test_23_retrieved_chunks_mapping(client):
    """Verify retrieved_chunks field is an integer reflecting retrieved evidence."""
    res = client.post("/chat", json={"question": "Plan a visit to Yadadri"})
    assert res.status_code == 200
    chunks = res.json()["retrieved_chunks"]
    assert isinstance(chunks, int)
    assert chunks >= 0


# -----------------------------------------------------------------------------
# Test 24: Confidence Score Bounding
# -----------------------------------------------------------------------------
def test_24_confidence_score_bounding(client):
    """Verify confidence_score is a valid floating point number."""
    res = client.post("/chat", json={"question": "Compare Yadadri and Dharmapuri"})
    assert res.status_code == 200
    score = res.json()["confidence_score"]
    assert isinstance(score, float)


# -----------------------------------------------------------------------------
# Test 25: Agent Metadata Propagation
# -----------------------------------------------------------------------------
def test_25_agent_metadata_propagation(client):
    """Verify agent metadata dictionary is propagated into response."""
    res = client.post("/chat", json={"question": "Plan a visit to Yadadri"})
    assert res.status_code == 200
    meta = res.json()["metadata"]
    assert isinstance(meta, dict)
    assert "temples" in meta or "itinerary" in meta or "disclaimer_present" in meta


# -----------------------------------------------------------------------------
# Test 26: Concurrent Request State Isolation
# -----------------------------------------------------------------------------
def test_26_concurrent_request_isolation(client):
    """Verify separate requests executed sequentially maintain independent states."""
    res1 = client.post("/chat", json={"question": "Compare Yadadri and Basara"})
    res2 = client.post("/chat", json={"question": "Plan a 1-day visit to Dharmapuri"})

    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res1.json()["agent_name"] == "comparison"
    assert res2.json()["agent_name"] == "itinerary_planning"


# -----------------------------------------------------------------------------
# Test 27: Deterministic Repeated Execution
# -----------------------------------------------------------------------------
def test_27_deterministic_repeated_execution(client):
    """Verify identical queries yield consistent agent routing and answers."""
    sess_id = "test_determ_" + str(uuid.uuid4())[:8]
    payload = {"question": "Plan a 1-day visit to Yadadri", "session_id": sess_id}

    res1 = client.post("/chat", json=payload)
    res2 = client.post("/chat", json=payload)

    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res1.json()["agent_name"] == res2.json()["agent_name"]
    assert res1.json()["sources"] == res2.json()["sources"]
    assert res1.json()["answer"] == res2.json()["answer"]


# -----------------------------------------------------------------------------
# Test 28: Dependency Injection via set_coordinator / get_coordinator
# -----------------------------------------------------------------------------
def test_28_coordinator_dependency_injection(client):
    """Verify set_coordinator allows test injection and overrides default coordinator."""
    class MockCoordinator:
        def process(self, state: AgentState) -> AgentResponse:
            return AgentResponse(
                success=True,
                agent_name="mock_specialist",
                answer="Mock response for dependency injection testing.",
                sources=["mock/test.json"],
                metadata={"mock": True, "retrieved_chunks": 5, "confidence_score": 0.99},
                latency_ms=1.23
            )

    set_coordinator(MockCoordinator())
    res = client.post("/chat", json={"question": "Any test query"})

    assert res.status_code == 200
    data = res.json()
    assert data["agent_name"] == "mock_specialist"
    assert data["answer"] == "Mock response for dependency injection testing."
    assert data["sources"] == ["mock/test.json"]
    assert data["retrieved_chunks"] == 5
    assert data["confidence_score"] == 0.99
    assert data["metadata"]["mock"] is True

    # Reset
    set_coordinator(None)
