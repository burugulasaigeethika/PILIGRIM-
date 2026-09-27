"""
PilgrimAI — Phase O7 Final Integration & Certification Test Suite

Comprehensive audit and certification tests covering:
1. BaseAgent contract compliance across all 8 specialist agents.
2. Router priority, conflict resolution, and non-stealing behavior.
3. Multi-temple itinerary regression certification (Basara + Vemulavada, Birla Mandir + Ujjaini).
4. Multi-intent pipeline compound queries across factual and capability agents.
5. Conversation memory session isolation, pronoun resolution, and multilingual follow-up.
6. Complete-list retrieval without Top-K truncation (Dharmapuri sevas = 10, Yadadri facilities = 26, Edupayala prasadam = 2).
7. Cross-temple aggregation across all 20 canonical temples (river bank = 11).
8. Comparison agent neutral representation and non-fabrication.
9. Itinerary agent grounded timeline and mandatory live-data disclaimer.
10. LiveWeatherAgent provider isolation and mock behavior.
11. BudgetAgent provenance categorization (VERIFIED, USER_PROVIDED, CALCULATED, ESTIMATE, UNAVAILABLE).
12. LiveNavigationAgent adapter isolation and non-fabrication.
13. VoiceMultilingualAgent intent preservation and non-stealing.
14. RAG boundary audit (zero raw vector DB / sentence transformer imports in specialists).
15. External API firewall audit (all external calls routed through BaseExternalAdapter).
16. ResponseAggregator deterministic merging and conflict preservation.
17. FastAPI /chat end-to-end integration via TestClient.
18. End-to-end smoke queries across the 10 representative scenarios.
19. Anti-hallucination / unknown temple rejection (Atlantis Temple).
20. Security audit: secret sanitization, zero raw audio retention, zero credentials in metadata.
"""

import sys
import os
import json
import pytest
from pathlib import Path
from typing import Dict, Any, List, Optional

# Ensure backend is in sys.path
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
from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState, AgentResponse, ExecutionTrace
from app.agents.coordinator import MasterAgentCoordinator
from app.agents.router import AgentRouter
from app.agents.memory import ConversationMemoryManager
from app.agents.response_aggregator import ResponseAggregator
from app.agents.multi_intent_pipeline import SequentialMultiIntentPipeline

from app.agents.temple_information_agent import TempleInformationAgent
from app.agents.comparison_agent import ComparisonAgent
from app.agents.cross_temple_aggregation_agent import CrossTempleAggregationAgent
from app.agents.itinerary_planning_agent import ItineraryPlanningAgent
from app.agents.live_weather_agent import LiveWeatherAgent
from app.agents.budget_agent import BudgetAgent, CostProvenance
from app.agents.live_navigation_agent import LiveNavigationAgent, NavigationResult
from app.agents.voice_multilingual_agent import (
    VoiceMultilingualAgent,
    ProviderStatus,
    MockSpeechToTextProvider,
    MockTranslationProvider,
    MockTextToSpeechProvider,
    DeterministicLanguageDetector
)
from app.agents.adapters.external_adapter import BaseExternalAdapter
from app.agents.adapters.navigation_adapter import NavigationAdapter
from app.agents.coordinate_registry import TempleCoordinateRegistry


class SyncTestClient:
    """Synchronous test client wrapper around httpx.AsyncClient for FastAPI ASGI app."""
    def __init__(self, asgi_app):
        self.app = asgi_app

    def post(self, url: str, json_data: dict):
        async def _call():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://testserver") as client:
                return await client.post(url, json=json_data)
        return asyncio.run(_call())

    def get(self, url: str):
        async def _call():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://testserver") as client:
                return await client.get(url)
        return asyncio.run(_call())

import asyncio


# =============================================================================
# 1. BaseAgent Contract Compliance Across All 8 Specialists
# =============================================================================

def test_01_all_8_agents_base_agent_contract():
    """Verify all 8 specialist agents inherit from BaseAgent and fulfill the contract."""
    agents = [
        TempleInformationAgent(),
        ComparisonAgent(),
        CrossTempleAggregationAgent(),
        ItineraryPlanningAgent(),
        LiveWeatherAgent(),
        BudgetAgent(),
        LiveNavigationAgent(),
        VoiceMultilingualAgent()
    ]
    expected_names = {
        "temple_information",
        "comparison",
        "cross_temple_aggregation",
        "itinerary_planning",
        "live_weather",
        "budget",
        "live_navigation",
        "voice_multilingual"
    }
    assert len(agents) == 8
    observed_names = {a.name for a in agents}
    assert observed_names == expected_names

    for agent in agents:
        assert isinstance(agent, BaseAgent)
        assert hasattr(agent, "execute")
        assert hasattr(agent, "name")
        assert agent.name in expected_names
        # Validate safe handling of empty state
        state = AgentState(user_query="")
        resp = agent.execute(state)
        assert isinstance(resp, AgentResponse)
        assert resp.agent_name == agent.name


# =============================================================================
# 2. Router Priority & Clean Domain Routing
# =============================================================================

def test_02_router_certification_across_domains():
    """Verify router priority and conflict resolution across all 8 agent domains."""
    router = AgentRouter()
    # Register all 8 agents
    all_agents = [
        "temple_information", "comparison", "cross_temple_aggregation",
        "itinerary_planning", "live_weather", "budget", "live_navigation",
        "voice_multilingual"
    ]
    for name in all_agents:
        router.register_agent(name)

    test_cases = [
        ("What are the timings of Basara?", "temple_information"),
        ("Compare Yadadri and Basara accommodation.", "comparison"),
        ("Which temples are located on a river bank?", "cross_temple_aggregation"),
        ("Plan a 2-day trip to Yadadri.", "itinerary_planning"),
        ("What is the weather at Yadadri?", "live_weather"),
        ("What will a visit to Yadadri cost?", "budget"),
        ("How far is Hyderabad from Yadadri?", "live_navigation"),
        ("Answer in Telugu: What are Yadadri timings?", "voice_multilingual"),
        ("Tell me in Hindi how far Yadadri is from Hyderabad.", "voice_multilingual"),
    ]

    for query, expected_agent in test_cases:
        decision = router.route(query)
        assert decision.selected_agent == expected_agent, f"Query '{query}' expected {expected_agent} but got {decision.selected_agent}"


# =============================================================================
# 3. Multi-Temple Itinerary Regression Protection
# =============================================================================

def test_03_multi_temple_itinerary_regression():
    """Verify multi-temple queries with itinerary intent route to itinerary_planning, not comparison."""
    router = AgentRouter()
    for name in ["temple_information", "comparison", "cross_temple_aggregation", "itinerary_planning"]:
        router.register_agent(name)

    q1 = "Plan an itinerary for Basara and Vemulavada."
    dec1 = router.route(q1)
    assert dec1.selected_agent == "itinerary_planning", f"Expected itinerary_planning for '{q1}', got {dec1.selected_agent}"

    q2 = "Plan a 2-day trip to Birla Mandir and Ujjaini."
    dec2 = router.route(q2)
    assert dec2.selected_agent == "itinerary_planning", f"Expected itinerary_planning for '{q2}', got {dec2.selected_agent}"


# =============================================================================
# 4. Multi-Intent Pipeline Compound Queries
# =============================================================================

def test_04_multi_intent_compound_queries():
    """Verify compound queries combining factual and capability agents decompose accurately."""
    router = AgentRouter()
    for name in ["temple_information", "live_weather", "budget", "itinerary_planning"]:
        router.register_agent(name)

    pipeline = SequentialMultiIntentPipeline(router=router)

    # Weather + Budget
    q1 = "What is the weather at Yadadri and what will the visit cost?"
    sub_tasks = pipeline.decompose_query(q1)
    assert len(sub_tasks) >= 2
    intents = [t.get("intent") for t in sub_tasks]
    target_agents = [t.get("target_agent") for t in sub_tasks]
    assert "weather" in intents or "live_weather" in target_agents
    assert "budget" in intents or "budget" in target_agents

    # Timings + Facilities
    q2 = "What are the timings of Yadadri and what facilities are available?"
    sub_tasks2 = pipeline.decompose_query(q2)
    assert len(sub_tasks2) >= 2


# =============================================================================
# 5. Conversation Memory Session Isolation & Pronoun Resolution
# =============================================================================

def test_05_conversation_memory_session_isolation_and_resolution():
    """Verify pronoun resolution within a session and strict isolation between sessions."""
    mem = ConversationMemoryManager()

    # Session A: Dharmapuri
    mem.add_turn(session_id="sess_A", user_query="What are the timings of Dharmapuri temple?", identified_temples=["Dharmapuri"])
    res_A = mem.resolve_query("sess_A", "What are its sevas?")
    assert "Dharmapuri" in res_A["resolved_query"]

    # Session B: Basara
    mem.add_turn(session_id="sess_B", user_query="What are the timings of Basara temple?", identified_temples=["Basara"])
    res_B = mem.resolve_query("sess_B", "What are its sevas?")
    assert "Basara" in res_B["resolved_query"]
    assert "Dharmapuri" not in res_B["resolved_query"]

    # Multilingual follow-up turn context preservation
    mem.add_turn(
        session_id="sess_multi",
        user_query="What are Yadadri timings?",
        identified_temples=["Yadadri"],
        response_summary="Yadadri temple is open from 4:00 AM to 9:30 PM."
    )
    recent = mem.get_recent_turns("sess_multi", limit=1)
    assert len(recent) == 1
    assert "Yadadri" in recent[0].response_summary


# =============================================================================
# 6. Complete-List Retrieval Without Top-K Truncation
# =============================================================================

def test_06_complete_list_retrieval_integrity():
    """Verify complete list retrieval counts match known dataset entries."""
    from app.agents.tools.rag_tool import RAGTool
    rag_tool = RAGTool()

    # Dharmapuri sevas = 10
    dharmapuri_sevas = rag_tool.get_temple_category_data("Dharmapuri", "sevas")
    assert dharmapuri_sevas is not None
    assert len(dharmapuri_sevas) == 10

    # Yadadri facilities = 26
    yadadri_fac = rag_tool.get_temple_category_data("Yadadri", "facilities")
    assert yadadri_fac is not None
    assert len(yadadri_fac["facilities"]) == 26

    # Edupayala prasadam = 2
    edupayala_prasadam = rag_tool.get_temple_category_data("Edupayal", "prasadam")
    assert edupayala_prasadam is not None
    assert len(edupayala_prasadam) == 2


# =============================================================================
# 7. Cross-Temple Aggregation Across All 20 Canonical Temples
# =============================================================================

def test_07_cross_temple_aggregation_river_bank():
    """Verify river bank aggregation discovers exactly 11 canonical temples."""
    agent = CrossTempleAggregationAgent()
    state = AgentState(user_query="Which temples are on a river bank?")
    resp = agent.execute(state)

    assert resp.success is True
    # Verify exactly 11 river-bank temples discovered
    assert "11" in resp.answer or len(resp.sources) == 11
    # Check that canonical river temples are present
    assert any("dharmapuri" in s.lower() for s in resp.sources)
    assert any("basara" in s.lower() for s in resp.sources)
    assert any("badrachalam" in s.lower() for s in resp.sources)


# =============================================================================
# 8. Comparison Agent Neutrality & Non-Fabrication
# =============================================================================

def test_08_comparison_agent_neutrality():
    """Verify comparison represents both temples without declaring a winner."""
    agent = ComparisonAgent()
    state = AgentState(user_query="Compare Yadadri and Basara accommodation.")
    resp = agent.execute(state)

    assert resp.success is True
    assert "yadadri" in resp.answer.lower()
    assert "basara" in resp.answer.lower()
    # Confirm neutrality (no "winner" or "better" declarations)
    assert "winner" not in resp.answer.lower()
    assert "better temple" not in resp.answer.lower()


# =============================================================================
# 9. Itinerary Agent Grounding & Disclaimer
# =============================================================================

def test_09_itinerary_agent_grounding_and_disclaimer():
    """Verify itinerary generation provides grounded timelines and live-data disclaimer."""
    agent = ItineraryPlanningAgent()
    state = AgentState(user_query="Plan a one-day visit to Yadadri.")
    resp = agent.execute(state)

    assert resp.success is True
    assert "yadadri" in resp.answer.lower()
    # Verify mandatory live-data disclaimer
    assert "disclaimer" in resp.answer.lower() or "subject to change" in resp.answer.lower() or "live" in resp.answer.lower()


# =============================================================================
# 10. LiveWeatherAgent Provider Isolation & Mocking
# =============================================================================

def test_10_weather_agent_provider_isolation():
    """Verify LiveWeatherAgent operates seamlessly with mocked external adapter."""
    mock_weather_data = {
        "latitude": 17.5888,
        "longitude": 78.9388,
        "current": {
            "time": "2026-09-23T10:00:00Z",
            "temperature_2m": 29.5,
            "relative_humidity_2m": 65,
            "precipitation": 0.0,
            "rain": 0.0,
            "weather_code": 1,
            "wind_speed_10m": 12.0
        },
        "daily": {
            "time": ["2026-09-23"],
            "temperature_2m_max": [33.0],
            "temperature_2m_min": [24.0],
            "precipitation_sum": [0.0],
            "precipitation_probability_max": [10],
            "sunrise": ["2026-09-23T06:00"],
            "sunset": ["2026-09-23T18:00"],
            "weather_code": [1]
        }
    }
    class MockResp:
        status_code = 200
        def json(self):
            return mock_weather_data

    mock_adapter = BaseExternalAdapter(name="test_weather")
    mock_adapter.request = lambda method, url, **kwargs: MockResp()

    agent = LiveWeatherAgent(adapter=mock_adapter)
    state = AgentState(user_query="What is the weather at Yadadri?")
    resp = agent.execute(state)

    assert resp.success is True
    assert "29.5" in resp.answer or "Mainly Clear" in resp.answer
    assert resp.metadata.get("provider") == "Open-Meteo"


# =============================================================================
# 11. BudgetAgent Provenance Verification
# =============================================================================

def test_11_budget_agent_provenance_verification():
    """Verify BudgetAgent categorizes prices with strict provenance."""
    agent = BudgetAgent()
    state = AgentState(user_query="What will a visit to Yadadri cost?")
    resp = agent.execute(state)

    assert resp.success is True
    assert "yadadri" in resp.answer.lower()
    # Check provenance presence in metadata
    provenance = resp.metadata.get("provenance", [])
    valid_provenances = {
        CostProvenance.VERIFIED.value,
        CostProvenance.USER_PROVIDED.value,
        CostProvenance.CALCULATED.value,
        CostProvenance.ESTIMATE.value,
        CostProvenance.UNAVAILABLE.value
    }
    for item in provenance:
        assert item.get("provenance") in valid_provenances


# =============================================================================
# 12. LiveNavigationAgent Adapter Isolation
# =============================================================================

def test_12_navigation_agent_adapter_isolation():
    """Verify LiveNavigationAgent operates with mocked NavigationAdapter without network calls."""
    class MockNavTransport:
        def __call__(self, method: str, url: str, **kwargs):
            class MockResp:
                status_code = 200
                text = "{}"
                def json(self):
                    return {
                        "routes": [
                            {
                                "distanceMeters": 62500,
                                "duration": "4500s",
                                "staticDuration": "4500s",
                                "description": "NH 163"
                            }
                        ]
                    }
            return MockResp()

    mock_nav_adapter = NavigationAdapter(api_key="TEST_MOCK_KEY_12345", transport=MockNavTransport())
    agent = LiveNavigationAgent(adapter=mock_nav_adapter)
    state = AgentState(user_query="How far is Hyderabad from Yadadri?")
    resp = agent.execute(state)

    assert resp.success is True
    assert "62.5" in resp.answer or "1 hr 15 min" in resp.answer
    assert resp.metadata.get("distance_km") == 62.5


# =============================================================================
# 13. VoiceMultilingualAgent Non-Stealing & Wrapping
# =============================================================================

def test_13_voice_multilingual_wrapping_and_non_stealing():
    """Verify VoiceMultilingualAgent wraps domain queries and does not steal normal English queries."""
    agent = VoiceMultilingualAgent()
    coord = MasterAgentCoordinator(
        temple_info_agent=TempleInformationAgent(),
        voice_multilingual_agent=agent
    )

    # 1. Non-stealing of standard English domain query
    state_eng = AgentState(user_query="What are Yadadri timings?")
    resp_eng = coord.process(state_eng)
    assert resp_eng.agent_name == "temple_information"

    # 2. Routing of explicit language directive
    state_telugu = AgentState(user_query="Answer in Telugu: What are Yadadri timings?")
    resp_telugu = coord.process(state_telugu)
    assert resp_telugu.agent_name == "voice_multilingual"
    assert "output_language" in resp_telugu.metadata
    assert resp_telugu.metadata["output_language"] == "te"


# =============================================================================
# 14. RAG Boundary Static Audit
# =============================================================================

def test_14_rag_boundary_static_inspection():
    """Verify specialist agents do not directly import raw vector DBs or sentence transformers."""
    agents_dir = backend_dir / "app" / "agents"
    forbidden_tokens = [
        "qdrant_client",
        "LocalQdrantManager",
        "rank_bm25",
        "SentenceTransformer",
        "CrossEncoder"
    ]

    for py_file in agents_dir.glob("*.py"):
        if py_file.name in ["rag_tool.py"]:  # RAGTool is the allowed facade
            continue
        code = py_file.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            assert f"import {token}" not in code, f"Forbidden import '{token}' found in {py_file.name}"
            assert f"from {token}" not in code, f"Forbidden import '{token}' found in {py_file.name}"


# =============================================================================
# 15. External API Firewall Audit
# =============================================================================

def test_15_external_api_firewall_audit():
    """Verify weather and navigation agents access external APIs strictly via BaseExternalAdapter."""
    from app.agents.adapters.external_adapter import BaseExternalAdapter
    from app.agents.adapters.navigation_adapter import NavigationAdapter

    weather_agent = LiveWeatherAgent()
    assert isinstance(weather_agent.adapter, BaseExternalAdapter)

    nav_agent = LiveNavigationAgent()
    assert isinstance(nav_agent.adapter, NavigationAdapter)


# =============================================================================
# 16. ResponseAggregator Deterministic Merging
# =============================================================================

def test_16_response_aggregator_deterministic_merging():
    """Verify ResponseAggregator correctly aggregates multiple agent responses."""
    aggregator = ResponseAggregator()
    resp1 = AgentResponse(
        success=True,
        agent_name="live_weather",
        answer="Yadadri weather: 30°C, Clear sky.",
        sources=["open_meteo"],
        latency_ms=10.0
    )
    resp2 = AgentResponse(
        success=True,
        agent_name="budget",
        answer="Estimated visit cost: ₹500.",
        sources=["yadadri_entry.json"],
        latency_ms=15.0
    )

    aggregated = aggregator.aggregate([resp1, resp2])
    assert aggregated.success is True
    assert "Yadadri weather" in aggregated.answer
    assert "Estimated visit cost" in aggregated.answer
    assert "open_meteo" in aggregated.sources
    assert "yadadri_entry.json" in aggregated.sources


@pytest.fixture(autouse=True)
def setup_mock_navigation():
    """Ensure coordinator's live_navigation agent has a mock adapter for offline certification."""
    coordinator = get_coordinator()
    if "live_navigation" in coordinator.agents:
        class MockNavTransport:
            def __call__(self, method: str, url: str, **kwargs):
                class MockResp:
                    status_code = 200
                    text = "{}"
                    def json(self):
                        return {
                            "routes": [
                                {
                                    "distanceMeters": 62500,
                                    "duration": "4500s",
                                    "staticDuration": "4500s",
                                    "description": "NH 163"
                                }
                            ]
                        }
                return MockResp()
        nav_agent = coordinator.agents["live_navigation"]
        nav_agent.adapter = NavigationAdapter(api_key="TEST_MOCK_KEY_12345", transport=MockNavTransport())


# =============================================================================
# 17. FastAPI /chat End-to-End Integration Across All 8 Agents
# =============================================================================

def test_17_chat_endpoint_full_integration():
    """Verify POST /chat endpoint functions correctly across all 8 specialist agents."""
    client = SyncTestClient(app)

    # 1. Health check
    resp_health = client.get("/health")
    assert resp_health.status_code == 200
    assert resp_health.json()["status"] in ["healthy", "ok"]

    # 2. Verify all 8 specialist agent queries through /chat
    chat_cases = [
        ("What are the timings of Basara Temple?", "temple_information"),
        ("Compare Yadadri and Basara accommodation.", "comparison"),
        ("Which temples are located on a river bank?", "cross_temple_aggregation"),
        ("Plan a 2-day trip to Yadadri.", "itinerary_planning"),
        ("What is the weather at Yadadri?", "live_weather"),
        ("What will a visit to Yadadri cost?", "budget"),
        ("How far is Hyderabad from Yadadri?", "live_navigation"),
        ("Answer in Telugu: What are Yadadri timings?", "voice_multilingual"),
    ]

    for idx, (question, expected_agent) in enumerate(chat_cases):
        req = {"question": question, "session_id": f"test_session_chat_{idx}"}
        resp = client.post("/chat", req)
        assert resp.status_code == 200, f"/chat failed for '{question}': {resp.text}"
        data = resp.json()
        assert "answer" in data
        assert len(data["answer"]) > 0
        assert "sources" in data
        assert "confidence_score" in data
        assert data["session_id"] == f"test_session_chat_{idx}"


# =============================================================================
# 18. End-to-End Smoke Queries (10 Required Scenarios)
# =============================================================================

@pytest.mark.parametrize("query_idx,query,expected_agent", [
    (1, "What are the timings of Basara?", "temple_information"),
    (2, "Compare Srisailam and Bhadrachalam accommodation.", "comparison"),
    (3, "Which temples are on a river bank?", "cross_temple_aggregation"),
    (4, "Plan a one-day visit to Yadadri.", "itinerary_planning"),
    (5, "What is the weather at Yadadri?", "live_weather"),
    (6, "What will a visit to Yadadri cost?", "budget"),
    (7, "How far is Hyderabad from Yadadri?", "live_navigation"),
    (8, "Answer in Telugu: What are Yadadri timings?", "voice_multilingual"),
    (9, "What are Yadadri timings and plan a one-day visit there.", "multi_intent"),
    (10, "Plan an itinerary for Basara and Vemulavada.", "itinerary_planning")
])
def test_18_end_to_end_smoke_queries(query_idx, query, expected_agent):
    """Verify the 10 required end-to-end smoke queries route and execute properly."""
    coordinator = get_coordinator()
    state = AgentState(session_id=f"smoke_test_{query_idx}", user_query=query)
    resp = coordinator.process(state)

    assert resp is not None
    assert len(resp.answer) > 0
    assert resp.success is True

    if expected_agent == "multi_intent":
        assert resp.agent_name in ["aggregator", "multi_intent", "coordinator", "response_aggregator"]
    else:
        assert resp.agent_name == expected_agent, f"Smoke test {query_idx} expected {expected_agent}, got {resp.agent_name}"


# =============================================================================
# 19. Anti-Hallucination & Unknown Temple Rejection
# =============================================================================

def test_19_unknown_temple_rejection():
    """Verify unknown or fictitious temples are rejected without hallucinating facts."""
    coordinator = get_coordinator()
    state = AgentState(user_query="Tell me about Atlantis Temple.")
    resp = coordinator.process(state)

    assert resp.success is False
    assert "don't have verified information" in resp.answer.lower() or "unregistered" in resp.answer.lower() or "not found" in resp.answer.lower() or "covers 20 major" in resp.answer.lower()


# =============================================================================
# 20. Security & Privacy Audit
# =============================================================================

def test_20_security_and_privacy_audit():
    """Verify zero plaintext credentials in metadata, traces, or responses, and zero raw audio retained."""
    coordinator = get_coordinator()
    state = AgentState(user_query="Answer in Telugu: What are Yadadri timings?")
    resp = coordinator.process(state)

    # 1. Zero raw audio bytes in state or response
    assert "audio_bytes" not in resp.metadata
    assert not hasattr(state, "raw_audio") or getattr(state, "raw_audio") is None

    # 2. Check for accidental credentials in metadata or traces
    forbidden_tokens = ["api_key", "password", "secret", "bearer", "authorization"]
    meta_str = json.dumps(resp.metadata, default=str).lower()
    for tok in forbidden_tokens:
        assert tok not in meta_str or "[redacted]" in meta_str

    for trace in state.execution_trace:
        trace_str = json.dumps(trace.metadata, default=str).lower()
        for tok in forbidden_tokens:
            assert tok not in trace_str or "[redacted]" in trace_str
