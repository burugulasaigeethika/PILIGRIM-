"""
Tests for EmergencyAgent specialist agent and full system integration.
Validates:
1. EmergencyAgent initialization and lifecycle.
2. AgentRouter emergency intent classification.
3. Temple-specific emergency contact retrieval and scoping.
4. Absence of cross-temple contamination.
5. Absence of fabricated numbers or facilities.
6. Statutory universal helplines fallback.
7. MasterAgentCoordinator registration and routing.
8. SequentialMultiIntentPipeline conjoined queries.
9. ConversationMemoryManager follow-up context resolution.
10. FastAPI /chat endpoint end-to-end integration.
"""

import pytest
import asyncio
from typing import Optional, Dict, Any
from unittest.mock import MagicMock
import httpx

from app.agents.state import AgentState, AgentResponse, AgentRouteDecision
from app.agents.router import AgentRouter
from app.agents.coordinator import MasterAgentCoordinator
from app.agents.emergency_agent import (
    EmergencyAgent,
    UNIVERSAL_HELPLINES,
    TEMPLE_CANONICAL_ALIASES,
    TEMPLE_DISPLAY_NAMES
)
from app.agents.temple_information_agent import TempleInformationAgent
from app.agents.memory import ConversationMemoryManager
from app.agents.response_aggregator import ResponseAggregator
from app.agents.tools.rag_tool import RAGTool
from app.main import app


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


# =============================================================================
# 1. Agent Initialization & Contract Tests
# =============================================================================

def test_emergency_agent_initialization():
    agent = EmergencyAgent()
    assert agent.name == "emergency"
    assert "emergency contacts" in agent.description.lower()
    assert agent.rag_tool is not None


def test_emergency_agent_custom_rag_tool():
    mock_rag = MagicMock()
    agent = EmergencyAgent(rag_tool=mock_rag)
    assert agent.rag_tool is mock_rag


# =============================================================================
# 2. Router Emergency Intent Classification Tests
# =============================================================================

@pytest.mark.parametrize("query,expected_intent,expected_agent", [
    ("What should I do in an emergency at Yadadri?", "emergency", "emergency"),
    ("Give me emergency contacts for Yadadri.", "emergency", "emergency"),
    ("Is there a hospital near Yadadri?", "emergency", "emergency"),
    ("What is the temple emergency help desk contact for Basara?", "emergency", "emergency"),
    ("Give me police and ambulance information for Bhadrachalam.", "emergency", "emergency"),
    ("Who should I contact in case of an emergency at Srisailam?", "emergency", "emergency"),
    ("Where can pilgrims get medical help at Dharmapuri?", "emergency", "emergency"),
    ("What emergency facilities are available at Vemulavada?", "emergency", "emergency"),
    ("I need urgent medical assistance at Medaram.", "emergency", "emergency"),
    ("Give me the temple help desk number for Jogulamba.", "emergency", "emergency"),
    ("What are the helpline numbers in an emergency?", "emergency", "emergency"),
    ("Where is the first aid clinic at Ahobilam?", "emergency", "emergency"),
    ("Police station near Chilkur temple", "emergency", "emergency")
])
def test_emergency_router_classification(query, expected_intent, expected_agent):
    router = AgentRouter(active_agents={"temple_information", "emergency"})
    decision = router.route(query)
    assert decision.intent == expected_intent
    assert decision.selected_agent == expected_agent
    assert decision.confidence >= 0.90


def test_emergency_router_inactive_agent():
    # When emergency is NOT registered in active_agents
    router = AgentRouter(active_agents={"temple_information"})
    decision = router.route("Emergency contacts for Yadadri")
    assert decision.intent == "emergency"
    assert decision.selected_agent == "none"
    assert "not active" in decision.reason


# =============================================================================
# 3. Grounded Retrieval & Temple Scoping Tests (Verified Data)
# =============================================================================

def test_emergency_agent_yadadri_scoping_and_contacts():
    agent = EmergencyAgent()
    state = AgentState(user_query="What are the emergency contacts for Yadadri?")
    response = agent.execute(state)

    assert response.success is True
    assert response.agent_name == "emergency"
    assert "Yadadri" in response.answer

    # Must contain verified Yadagirigutta Police Station phone
    assert "08685-236619" in response.answer
    # Must contain verified Yadagirigutta PHC or GGH Bhongir
    assert ("9949997989" in response.answer or "7702131479" in response.answer or "Primary Health Centre" in response.answer)
    # Must contain statutory helplines
    assert "112" in response.answer
    assert "108" in response.answer
    assert "100" in response.answer

    # Must NOT contain contacts from other temples (e.g., Basara SHO)
    assert "87126 59540" not in response.answer
    assert "Allagadda" not in response.answer

    # Source files verified
    assert any("yadadri/emergency_nos.json" in s for s in response.sources)


def test_emergency_agent_basara_scoping():
    agent = EmergencyAgent()
    state = AgentState(user_query="Give me hospital and police contacts for Basara.")
    response = agent.execute(state)

    assert response.success is True
    assert "Basara" in response.answer
    # Must contain Basara Police SHO
    assert "87126 59540" in response.answer or "Basara Police Station" in response.answer
    # Must contain RGUKT Basar Campus Hospital
    assert "87522 55588" in response.answer or "RGUKT" in response.answer

    # Must NOT contain Yadadri contacts
    assert "08685-236619" not in response.answer


def test_emergency_agent_ahobilam_scoping():
    agent = EmergencyAgent()
    state = AgentState(user_query="Where can I get medical first aid at Ahobilam?")
    response = agent.execute(state)

    assert response.success is True
    assert "Ahobilam" in response.answer
    assert ("First-Aid Post" in response.answer or "Allagadda" in response.answer)
    assert "08685-236619" not in response.answer  # No Yadadri bleed


def test_emergency_agent_chilkur_scoping():
    agent = EmergencyAgent()
    state = AgentState(user_query="Emergency police contact at Chilkur")
    response = agent.execute(state)

    assert response.success is True
    assert "Chilkur" in response.answer
    assert "Moinabad" in response.answer or "2785 2400" in response.answer


# =============================================================================
# 4. No Fabrication & Missing Data Handling
# =============================================================================

def test_emergency_agent_no_fabrication_mock():
    # Mock RAGTool returning empty emergency dictionary
    mock_rag = MagicMock()
    mock_rag.get_temple_category_data.return_value = {}

    agent = EmergencyAgent(rag_tool=mock_rag)
    state = AgentState(user_query="Give me emergency hospital contact for Yadadri")
    response = agent.execute(state)

    assert response.success is True
    # Must state that local contact is not recorded
    assert "No dedicated local hospital recorded" in response.answer or "could not find verified" in response.answer
    # Must NOT invent a random 10-digit number
    import re
    phone_matches = re.findall(r"\b[6-9]\d{9}\b", response.answer)
    assert len(phone_matches) == 0


def test_emergency_agent_universal_helpline_fallback():
    # Query with NO temple specified
    agent = EmergencyAgent()
    state = AgentState(user_query="What number should I call in an emergency?")
    response = agent.execute(state)

    assert response.success is True
    assert "112" in response.answer
    assert "108" in response.answer
    assert "100" in response.answer
    assert "101" in response.answer
    assert "specify your temple" in response.answer.lower()
    assert response.metadata.get("is_universal") is True


def test_emergency_agent_unsupported_temple():
    agent = EmergencyAgent()
    router = AgentRouter(active_agents={"emergency"})
    decision = router.route("Emergency contacts for Kashi Vishwanath temple")
    state = AgentState(user_query="Emergency contacts for Kashi Vishwanath temple")
    state.intermediate_results["route_decision"] = decision

    response = agent.execute(state)
    assert response.success is True
    assert "not have verified emergency records" in response.answer.lower()
    assert "112" in response.answer


# =============================================================================
# 5. Coordinator & Memory Integration Tests
# =============================================================================

def test_coordinator_emergency_agent_dispatch():
    router = AgentRouter()
    aggregator = ResponseAggregator()
    memory = ConversationMemoryManager()
    temple_info = TempleInformationAgent()
    emergency = EmergencyAgent()

    coordinator = MasterAgentCoordinator(
        router=router,
        aggregator=aggregator,
        temple_info_agent=temple_info,
        emergency_agent=emergency,
        memory_manager=memory
    )

    state = AgentState(user_query="What are the emergency contacts for Yadadri?")
    response = coordinator.process(state)

    assert response.success is True
    assert response.agent_name == "emergency"
    assert "08685-236619" in response.answer
    assert "Yadadri" in response.answer


def test_coordinator_memory_emergency_followup():
    router = AgentRouter()
    aggregator = ResponseAggregator()
    memory = ConversationMemoryManager()
    temple_info = TempleInformationAgent()
    emergency = EmergencyAgent()

    coordinator = MasterAgentCoordinator(
        router=router,
        aggregator=aggregator,
        temple_info_agent=temple_info,
        emergency_agent=emergency,
        memory_manager=memory
    )

    session_id = "test_emergency_session_101"

    memory.add_turn(
        session_id=session_id,
        user_query="Tell me about Basara temple",
        resolved_query="Tell me about Basara temple",
        identified_temples=["basara"],
        response_summary="Basara Sri Gnana Saraswathi Temple is located in Nirmal district.",
        metadata={"temple_name": "Basara", "temple_slug": "basara"}
    )

    # Turn 2: Follow-up emergency query with pronoun / no explicit temple
    state2 = AgentState(user_query="What are the emergency hospital contacts here?", session_id=session_id)
    resp2 = coordinator.process(state2)

    assert resp2.success is True
    assert resp2.agent_name == "emergency"
    # Should resolve to Basara from conversational memory
    assert "Basara" in resp2.answer
    assert ("87522 55588" in resp2.answer or "RGUKT" in resp2.answer or "Basar" in resp2.answer)


# =============================================================================
# 6. Multi-Intent Integration Tests
# =============================================================================

def test_multi_intent_pipeline_emergency_and_timings():
    router = AgentRouter()
    aggregator = ResponseAggregator()
    temple_info = TempleInformationAgent()
    # Mock temple_info.execute so it returns cleanly without invoking Ollama
    temple_info.execute = MagicMock(return_value=AgentResponse(
        success=True,
        agent_name="temple_information",
        answer="Yadadri Temple Darshan timings are 4:00 AM to 9:30 PM daily.",
        metadata={"temple_name": "Yadadri", "sources": ["data/temples/yadadri/timings.json"]}
    ))
    emergency = EmergencyAgent()

    coordinator = MasterAgentCoordinator(
        router=router,
        aggregator=aggregator,
        temple_info_agent=temple_info,
        emergency_agent=emergency
    )

    # Conjoined query: timings AND emergency contacts
    state = AgentState(user_query="What are Yadadri timings and what emergency contacts are available?")
    response = coordinator.process(state)

    assert response.success is True
    # Answer should contain information from both specialist executions
    assert "Yadadri" in response.answer
    # Should contain timing information
    assert ("timing" in response.answer.lower() or "darshan" in response.answer.lower() or "am" in response.answer.lower())
    # Should contain emergency information
    assert ("emergency" in response.answer.lower() or "police" in response.answer.lower() or "hospital" in response.answer.lower() or "112" in response.answer)


# =============================================================================
# 7. FastAPI /chat HTTP Endpoint Integration Tests
# =============================================================================

def test_chat_endpoint_emergency_query():
    client = SyncTestClient(app)
    payload = {
        "question": "What is the emergency hospital contact for Yadadri?",
        "session_id": "test_fastapi_emergency_01"
    }
    resp = client.post("/chat", json=payload)
    assert resp.status_code == 200

    data = resp.json()
    assert data["question"] == payload["question"]
    assert data["agent_name"] == "emergency"
    assert "Yadadri" in data["answer"]
    assert len(data["sources"]) > 0
    assert any("emergency_nos.json" in s for s in data["sources"])
    assert data["confidence_score"] >= 0.90
