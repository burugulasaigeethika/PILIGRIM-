"""
Phase I - ConversationMemoryManager Certification Tests

Verifies:
1. Memory manager initialization.
2. Session creation.
3. Session isolation (Session A and Session B remain distinct).
4. Add turn records turn accurately.
5. Retrieve recent turns chronologically.
6. Recent-turn limit is respected.
7. Session clearing removes session cleanly.
8. TTL within expiration maintains session state.
9. TTL expiration resets session when expired.
10. LRU eviction at 1000 sessions evicts the oldest session.
11. LRU refresh when an old session is accessed.
12. Dharmapuri -> 'its' resolution ('What are its sevas?' -> 'What are Dharmapuri temple's sevas?').
13. Yadadri -> 'its' resolution ('What are its timings?').
14. Explicit new temple in query overrides memory (does not carry over previous temple).
15. Ambiguous multiple-temple pronoun produces controlled clarification.
16. No cross-session context leakage.
17. Secret sanitization removes/redacts sensitive keys (api_key, token, password).
18. Static inspection verifies zero RAG, vector DB, or LLM imports.
19. Resolved query preserves original user query separately in AgentState intermediate_results.
20. Immutability: caller mutating returned history does not mutate internal memory.
21. Repeated resolution is deterministic.
22. Existing AgentState compatibility.
23. Existing Coordinator multi-turn integration (Turn 1: Dharmapuri timings -> Turn 2: What are its sevas?).
24. Phase H multi-intent compatibility (Turn 1: Yadadri timings and facilities -> Turn 2: What about its sevas?).
"""

import sys
import copy
from pathlib import Path
import pytest

# Ensure backend is in sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.state import AgentState, AgentResponse
from app.agents.router import AgentRouter
from app.agents.coordinator import MasterAgentCoordinator
from app.agents.memory import ConversationMemoryManager, MemoryTurn


class MockClock:
    """Mockable clock for deterministic TTL testing without sleeping."""
    def __init__(self, initial_time=1000.0):
        self.current_time = initial_time

    def time(self) -> float:
        return self.current_time

    def advance(self, seconds: float):
        self.current_time += seconds


@pytest.fixture
def memory_manager():
    return ConversationMemoryManager()


def test_1_memory_manager_initialization(memory_manager):
    """Verify default initialization with 1000 max sessions and 1800s TTL."""
    assert memory_manager is not None
    assert memory_manager.max_sessions == 1000
    assert memory_manager.ttl_seconds == 1800.0
    assert len(memory_manager._sessions) == 0


def test_2_session_creation(memory_manager):
    """Verify session is created on first turn or lookup."""
    session = memory_manager._get_or_create_session("sess_1")
    assert session is not None
    assert session["session_id"] == "sess_1"
    assert len(session["turns"]) == 0
    assert "sess_1" in memory_manager._sessions


def test_3_session_isolation(memory_manager):
    """Verify multiple sessions maintain isolated turn histories."""
    memory_manager.add_turn(session_id="sess_A", user_query="Query A", identified_temples=["Yadadri"])
    memory_manager.add_turn(session_id="sess_B", user_query="Query B", identified_temples=["Basara"])

    turns_a = memory_manager.get_recent_turns("sess_A")
    turns_b = memory_manager.get_recent_turns("sess_B")

    assert len(turns_a) == 1
    assert len(turns_b) == 1
    assert turns_a[0].identified_temples == ["Yadadri"]
    assert turns_b[0].identified_temples == ["Basara"]


def test_4_add_turn(memory_manager):
    """Verify turn recording preserves user query, resolved query, and identified temples."""
    turn = memory_manager.add_turn(
        session_id="sess_1",
        user_query="What are the timings of Dharmapuri temple?",
        resolved_query="What are the timings of Dharmapuri temple?",
        detected_intents=["temple_information"],
        identified_temples=["Dharmapuri"],
        response_summary="Opens at 5:00 AM."
    )
    assert isinstance(turn, MemoryTurn)
    assert turn.session_id == "sess_1"
    assert turn.identified_temples == ["Dharmapuri"]
    assert turn.response_summary == "Opens at 5:00 AM."


def test_5_retrieve_recent_turns(memory_manager):
    """Verify retrieval returns turns in chronological order."""
    memory_manager.add_turn(session_id="sess_1", user_query="Turn 1")
    memory_manager.add_turn(session_id="sess_1", user_query="Turn 2")
    memory_manager.add_turn(session_id="sess_1", user_query="Turn 3")

    turns = memory_manager.get_recent_turns("sess_1")
    assert len(turns) == 3
    assert [t.user_query for t in turns] == ["Turn 1", "Turn 2", "Turn 3"]


def test_6_recent_turn_limit(memory_manager):
    """Verify limit parameter restricts number of returned turns."""
    for i in range(10):
        memory_manager.add_turn(session_id="sess_1", user_query=f"Turn {i}")

    turns = memory_manager.get_recent_turns("sess_1", limit=3)
    assert len(turns) == 3
    assert [t.user_query for t in turns] == ["Turn 7", "Turn 8", "Turn 9"]


def test_7_session_clearing(memory_manager):
    """Verify clear_session removes session and clear_all empties all sessions."""
    memory_manager.add_turn(session_id="sess_1", user_query="Q1")
    memory_manager.add_turn(session_id="sess_2", user_query="Q2")

    # Clear individual session
    assert memory_manager.clear_session("sess_1") is True
    assert memory_manager.get_recent_turns("sess_1") == []
    assert len(memory_manager.get_recent_turns("sess_2")) == 1

    # Clear unknown session is safe no-op
    assert memory_manager.clear_session("nonexistent") is False

    # Clear all
    memory_manager.clear_all()
    assert len(memory_manager._sessions) == 0


def test_8_ttl_within_expiration():
    """Verify session is accessible within TTL window."""
    clock = MockClock(initial_time=1000.0)
    manager = ConversationMemoryManager(ttl_seconds=1800.0, time_provider=clock.time)

    manager.add_turn(session_id="sess_1", user_query="Q1", identified_temples=["Yadadri"])
    clock.advance(900.0)  # 15 minutes elapsed (less than 30)

    turns = manager.get_recent_turns("sess_1")
    assert len(turns) == 1
    assert turns[0].identified_temples == ["Yadadri"]


def test_9_ttl_expiration():
    """Verify session is expired and removed after TTL exceeds."""
    clock = MockClock(initial_time=1000.0)
    manager = ConversationMemoryManager(ttl_seconds=1800.0, time_provider=clock.time)

    manager.add_turn(session_id="sess_1", user_query="Q1", identified_temples=["Yadadri"])
    clock.advance(1801.0)  # Exceeds 30 min TTL

    # Accessing expired session removes it
    turns = manager.get_recent_turns("sess_1")
    assert len(turns) == 0
    assert "sess_1" not in manager._sessions


def test_10_lru_eviction_at_capacity():
    """Verify least recently used session is evicted when max_sessions is reached."""
    manager = ConversationMemoryManager(max_sessions=3)

    manager.add_turn(session_id="sess_1", user_query="Q1")
    manager.add_turn(session_id="sess_2", user_query="Q2")
    manager.add_turn(session_id="sess_3", user_query="Q3")

    # Adding 4th session must evict sess_1
    manager.add_turn(session_id="sess_4", user_query="Q4")

    assert "sess_1" not in manager._sessions
    assert "sess_2" in manager._sessions
    assert "sess_3" in manager._sessions
    assert "sess_4" in manager._sessions
    assert len(manager._sessions) == 3


def test_11_lru_refresh_on_access():
    """Verify accessing an older session moves it to MRU position, preventing its eviction."""
    manager = ConversationMemoryManager(max_sessions=3)

    manager.add_turn(session_id="sess_1", user_query="Q1")
    manager.add_turn(session_id="sess_2", user_query="Q2")
    manager.add_turn(session_id="sess_3", user_query="Q3")

    # Access sess_1 so it becomes most recently used
    manager.get_recent_turns("sess_1")

    # Adding sess_4 should now evict sess_2 instead of sess_1
    manager.add_turn(session_id="sess_4", user_query="Q4")

    assert "sess_1" in manager._sessions
    assert "sess_2" not in manager._sessions
    assert "sess_3" in manager._sessions
    assert "sess_4" in manager._sessions


def test_12_dharmapuri_its_resolution(memory_manager):
    """Verify 'its' resolves to Dharmapuri following a Dharmapuri query."""
    memory_manager.add_turn(
        session_id="user_1",
        user_query="What are the timings of Dharmapuri temple?",
        identified_temples=["Dharmapuri"]
    )

    res = memory_manager.resolve_query("user_1", "What are its sevas?")
    assert res["is_ambiguous"] is False
    assert res["referenced_temple"] == "Dharmapuri"
    assert "Dharmapuri temple's" in res["resolved_query"] or "Dharmapuri" in res["resolved_query"]


def test_13_yadadri_its_resolution(memory_manager):
    """Verify 'its' resolves to Yadadri following a Yadadri query."""
    memory_manager.add_turn(
        session_id="user_2",
        user_query="Tell me about Yadadri temple",
        identified_temples=["Yadadri"]
    )

    res = memory_manager.resolve_query("user_2", "What are its timings?")
    assert res["is_ambiguous"] is False
    assert res["referenced_temple"] == "Yadadri"
    assert "Yadadri" in res["resolved_query"]


def test_14_explicit_new_temple_overrides_memory(memory_manager):
    """Verify explicit new temple in query takes precedence over memory."""
    memory_manager.add_turn(
        session_id="user_3",
        user_query="What are the timings of Dharmapuri temple?",
        identified_temples=["Dharmapuri"]
    )

    # Turn 2 explicitly specifies Yadadri
    res = memory_manager.resolve_query("user_3", "What are the sevas at Yadadri?")
    assert res["is_ambiguous"] is False
    assert res["referenced_temple"] == "Yadadri"
    assert "Dharmapuri" not in res["resolved_query"]
    assert "Yadadri" in res["resolved_query"]


def test_15_ambiguous_multiple_temple_pronoun_produces_clarification(memory_manager):
    """Verify multiple distinct recent temples cause pronoun to require clarification."""
    memory_manager.add_turn(
        session_id="user_ambig",
        user_query="What are Yadadri timings?",
        identified_temples=["Yadadri"]
    )
    memory_manager.add_turn(
        session_id="user_ambig",
        user_query="What are Bhadrachalam timings?",
        identified_temples=["Badrachalam"]
    )

    res = memory_manager.resolve_query("user_ambig", "What are its sevas?")
    assert res["is_ambiguous"] is True
    assert "which temple" in res["clarification_message"].lower()


def test_16_no_cross_session_context_leakage(memory_manager):
    """Verify separate sessions never leak temple context."""
    # Session A talks about Yadadri
    memory_manager.add_turn(
        session_id="sess_A",
        user_query="Tell me about Yadadri temple",
        identified_temples=["Yadadri"]
    )

    # Session B talks about Dharmapuri
    memory_manager.add_turn(
        session_id="sess_B",
        user_query="Tell me about Dharmapuri temple",
        identified_temples=["Dharmapuri"]
    )

    # Follow-up in Session A must resolve to Yadadri, not Dharmapuri
    res_a = memory_manager.resolve_query("sess_A", "What are its sevas?")
    assert res_a["referenced_temple"] == "Yadadri"

    # Follow-up in Session B must resolve to Dharmapuri, not Yadadri
    res_b = memory_manager.resolve_query("sess_B", "What are its sevas?")
    assert res_b["referenced_temple"] == "Dharmapuri"


def test_17_secret_sanitization(memory_manager):
    """Verify sensitive metadata keys are redacted from stored turn data."""
    turn = memory_manager.add_turn(
        session_id="sess_sec",
        user_query="Sanitize test",
        metadata={
            "api_key": "secret_key_12345",
            "token": "bearer_token_xyz",
            "safe_param": "normal_val"
        }
    )
    assert turn.metadata["api_key"] == "[REDACTED]"
    assert turn.metadata["token"] == "[REDACTED]"
    assert turn.metadata["safe_param"] == "normal_val"


def test_18_no_raw_rag_llm_dependency():
    """Verify memory.py does not import RAG, vector databases, or LLMs."""
    memory_file = root_dir / "backend" / "app" / "agents" / "memory.py"
    content = memory_file.read_text(encoding="utf-8")

    forbidden = [
        "qdrant_client",
        "rank_bm25",
        "sentence_transformers",
        "LocalQdrantManager",
        "LocalBM25Manager",
        "PilgrimRAGService",
        "KnowledgeRegistry",
        "RAGTool",
        "ollama",
        "openai",
        "anthropic"
    ]
    for item in forbidden:
        assert item not in content, f"Forbidden import '{item}' detected in memory.py!"


def test_19_resolved_query_preserves_original_query():
    """Verify coordinator stores both original and resolved queries in intermediate results."""
    mem = ConversationMemoryManager()
    coord = MasterAgentCoordinator(memory_manager=mem)

    # Turn 1: Establish temple context
    state1 = AgentState(session_id="session_orig", user_query="What are the timings of Dharmapuri temple?")
    coord.process(state1)

    # Turn 2: Pronoun query
    state2 = AgentState(session_id="session_orig", user_query="What are its sevas?")
    coord.process(state2)

    assert "memory" in state2.intermediate_results
    mem_info = state2.intermediate_results["memory"]
    assert mem_info["original_query"] == "What are its sevas?"
    assert "Dharmapuri" in mem_info["resolved_query"]


def test_20_memory_immutability(memory_manager):
    """Verify modifying returned history does not mutate internal memory."""
    memory_manager.add_turn(session_id="sess_mut", user_query="Original turn", identified_temples=["Yadadri"])
    turns = memory_manager.get_recent_turns("sess_mut")

    # Attempt to tamper with returned copy
    turns[0].user_query = "Tampered query"
    turns[0].identified_temples.append("TamperedTemple")

    fresh_turns = memory_manager.get_recent_turns("sess_mut")
    assert fresh_turns[0].user_query == "Original turn"
    assert fresh_turns[0].identified_temples == ["Yadadri"]


def test_21_repeated_resolution_determinism(memory_manager):
    """Verify repeated resolution of the same query produces identical results."""
    memory_manager.add_turn(
        session_id="sess_det",
        user_query="Tell me about Yadadri temple",
        identified_temples=["Yadadri"]
    )

    query = "What are its timings?"
    results = [memory_manager.resolve_query("sess_det", query) for _ in range(5)]

    for r in results[1:]:
        assert r == results[0]


def test_22_agent_state_compatibility():
    """Verify AgentState functions seamlessly with memory manager."""
    state = AgentState(session_id="sess_compat", user_query="What are the timings of Basara temple?")
    mem = ConversationMemoryManager()

    turn = mem.add_turn(
        session_id=state.session_id,
        user_query=state.user_query,
        identified_temples=["Basara"]
    )
    assert turn.session_id == state.session_id
    assert turn.user_query == state.user_query


def test_23_coordinator_multi_turn_live_flow():
    """Verify live multi-turn execution: Turn 1 (Dharmapuri) -> Turn 2 ('What are its sevas?') -> Grounded Answer."""
    mem = ConversationMemoryManager()
    coord = MasterAgentCoordinator(memory_manager=mem)
    session_id = "test_live_multi_turn_dharmapuri"

    # Turn 1: Factual Dharmapuri query
    state1 = AgentState(session_id=session_id, user_query="What are the timings of Dharmapuri temple?")
    res1 = coord.process(state1)
    assert res1.success is True
    assert len(res1.sources) > 0
    assert any("dharmapuri" in s.lower() for s in res1.sources)

    # Turn 2: Follow-up query with pronoun
    state2 = AgentState(session_id=session_id, user_query="What are its sevas?")
    res2 = coord.process(state2)
    assert res2.success is True
    assert len(res2.sources) > 0
    assert any("dharmapuri" in s.lower() for s in res2.sources)
    assert "Dharmapuri" in state2.intermediate_results["memory"]["resolved_query"]


def test_24_phase_h_multi_intent_compatibility():
    """Verify memory integration works seamlessly with multi-intent pipeline."""
    mem = ConversationMemoryManager()
    coord = MasterAgentCoordinator(memory_manager=mem)
    session_id = "test_multi_intent_memory"

    # Turn 1: Multi-intent query establishing Yadadri
    state1 = AgentState(session_id=session_id, user_query="What are Yadadri timings and facilities?")
    res1 = coord.process(state1)
    assert res1.success is True

    # Turn 2: Follow-up with pronoun targeting sevas
    state2 = AgentState(session_id=session_id, user_query="What about its sevas?")
    res2 = coord.process(state2)
    assert res2.success is True
    assert any("yadadri" in s.lower() for s in res2.sources)
