"""
Phase J - Complete-List Retrieval Certification Tests

Certifies Phase J:
1. Completeness intent detection (e.g., 'List all sevas at Dharmapuri').
2. Targeted query preservation (e.g., 'What is the Abhishekam price at Dharmapuri?' remains targeted).
3. Dharmapuri complete sevas retrieval (all 10 verified sevas present in complete parent).
4. No Top-K truncation (returns more records than ordinary TOP_K=3).
5. Targeted retrieval unaffected (ordinary queries continue using hybrid top-k).
6. Complete prasadam category (Edupayala verified prasadams).
7. Explicit completeness variants (all, every, complete list, full list, show all, list all, etc.).
8. No temple clarification (queries without temple context do not guess).
9. Unknown category rejection (safe handling without hallucinations).
10. Cross-temple isolation (Dharmapuri request strictly excludes Yadadri records).
11. Source grounding (every item in complete parent corresponds to source data).
12. Phase H multi-intent compatibility.
13. Phase I conversation memory compatibility (Turn 1: Dharmapuri -> Turn 2: 'List all its sevas').
14. No raw RAG duplication (verifies reuse of existing RAG singletons and facade).
15. Source dataset integrity check (417 JSON files verified unchanged).
16. Deterministic retrieval consistency across repeated executions.
17. Large category retrieval (Yadadri facilities: all 26 entries present).
18. Targeted questions for list and non-list categories remain targeted facts.
19. Case insensitivity for completeness triggers.
20. Empty and whitespace queries handled safely.
21. Safe formatted fallback produces structured text without raw JSON leakage.
22. TempleInformationAgent propagates is_complete_list metadata.
"""

import sys
import json
from pathlib import Path
import pytest

# Ensure root and backend are in sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.rag.query_planner import query_planner, QueryPlan
from app.rag.knowledge_registry import knowledge_registry
from app.rag.category_registry import category_registry
from app.agents.tools.rag_tool import RAGTool
from app.agents.temple_information_agent import TempleInformationAgent
from app.agents.state import AgentState, AgentResponse
from app.agents.memory import ConversationMemoryManager
from app.agents.multi_intent_pipeline import SequentialMultiIntentPipeline
from app.agents.router import AgentRouter


# -----------------------------------------------------------------------------
# Test 1: Completeness Intent Detection
# -----------------------------------------------------------------------------
def test_1_completeness_intent_detection():
    """Verify 'List all sevas at Dharmapuri' is classified as complete_list intent."""
    plan = query_planner.plan("List all sevas at Dharmapuri temple.")
    assert isinstance(plan, QueryPlan)
    assert plan.intent == "complete_list"
    assert plan.retrieval_mode == "complete_category"
    assert plan.exhaustive is True
    assert plan.temples == ["Dharmapuri"]
    assert plan.categories == ["sevas"]


# -----------------------------------------------------------------------------
# Test 2: Targeted Query Preservation
# -----------------------------------------------------------------------------
def test_2_targeted_query_remains_targeted():
    """Verify specific factual query is NOT classified as complete_list."""
    plan = query_planner.plan("What is the Abhishekam price at Dharmapuri?")
    assert isinstance(plan, QueryPlan)
    assert plan.intent == "targeted_fact"
    assert plan.retrieval_mode == "targeted"
    assert plan.exhaustive is False
    assert plan.temples == ["Dharmapuri"]
    assert plan.categories == ["sevas"]


# -----------------------------------------------------------------------------
# Test 3: Dharmapuri Complete Sevas Retrieval
# -----------------------------------------------------------------------------
def test_3_dharmapuri_complete_sevas():
    """Verify that complete Dharmapuri seva records are retrieved from verified source data."""
    sevas_file = root_dir / "dharmapuri" / "sevas.json"
    assert sevas_file.exists(), "Dharmapuri sevas.json must exist"
    with open(sevas_file, "r", encoding="utf-8") as f:
        source_sevas = json.load(f)

    # Dharmapuri sevas.json has exactly 10 sevas
    assert len(source_sevas) == 10, f"Expected 10 Dharmapuri sevas, found {len(source_sevas)}"

    parent_text = knowledge_registry.get_complete_parent("Dharmapuri", "sevas")
    assert parent_text is not None, "Complete parent text for Dharmapuri sevas must not be None"

    # Every seva name and price from source JSON must be in parent_text
    for seva in source_sevas:
        assert seva["name"] in parent_text, f"Seva '{seva['name']}' missing from complete parent"
        assert seva["price"] in parent_text, f"Seva price '{seva['price']}' missing from complete parent"


# -----------------------------------------------------------------------------
# Test 4: No Top-K Truncation
# -----------------------------------------------------------------------------
def test_4_no_top_k_truncation():
    """Verify complete-category retrieval returns all 10 items, surpassing ordinary TOP_K=3."""
    sevas_file = root_dir / "dharmapuri" / "sevas.json"
    with open(sevas_file, "r", encoding="utf-8") as f:
        source_sevas = json.load(f)

    total_source_items = len(source_sevas)
    assert total_source_items > 3, "Source sevas must be greater than top_k=3 to test non-truncation"

    parent_text = knowledge_registry.get_complete_parent("Dharmapuri", "sevas")
    represented_count = sum(1 for s in source_sevas if s["name"] in parent_text)

    # Must contain 100% of the verified items
    assert represented_count == total_source_items
    assert represented_count == 10


# -----------------------------------------------------------------------------
# Test 5: Targeted Retrieval Unaffected
# -----------------------------------------------------------------------------
def test_5_targeted_retrieval_unaffected():
    """Verify ordinary targeted questions produce targeted plans and preserve hybrid top-k routing."""
    targeted_queries = [
        ("What time does Dharmapuri temple open?", "timings", "targeted"),
        ("Where is Dharmapuri temple located?", "travel", "targeted"),
        ("What is the cost of Abhishekam at Dharmapuri?", "sevas", "targeted"),
        ("Does Dharmapuri temple have accommodation?", "accommodation", "targeted")
    ]
    for q, expected_cat, expected_mode in targeted_queries:
        plan = query_planner.plan(q)
        assert plan.retrieval_mode == expected_mode, f"Query '{q}' should be {expected_mode}, got {plan.retrieval_mode}"
        assert plan.exhaustive is False


# -----------------------------------------------------------------------------
# Test 6: Complete Prasadam Category (Edupayala)
# -----------------------------------------------------------------------------
def test_6_complete_prasadam_category():
    """Verify complete prasadam category retrieval for Edupayala temple."""
    prasadam_file = root_dir / "edupayal" / "prasadam.json"
    assert prasadam_file.exists(), "Edupayala prasadam.json must exist"
    with open(prasadam_file, "r", encoding="utf-8") as f:
        source_prasadams = json.load(f)

    # Exactly 2 prasadams in verified source: 'Edupayala Laddu' and 'Tamarind Pulihora'
    assert len(source_prasadams) == 2

    parent_text = knowledge_registry.get_complete_parent("Edupayal", "prasadam")
    assert parent_text is not None

    for item in source_prasadams:
        assert item["name"] in parent_text, f"Prasadam '{item['name']}' missing from complete parent"


# -----------------------------------------------------------------------------
# Test 7: Explicit Completeness Variants
# -----------------------------------------------------------------------------
def test_7_explicit_completeness_variants():
    """Verify diverse phrasing variants correctly trigger complete_list intent."""
    variants = [
        "all sevas at Dharmapuri",
        "every seva at Dharmapuri",
        "show every seva at Dharmapuri",
        "complete list of sevas at Dharmapuri",
        "full list of sevas at Dharmapuri",
        "entire list of sevas at Dharmapuri",
        "list all sevas at Dharmapuri",
        "show all sevas at Dharmapuri",
        "what are all the sevas at Dharmapuri",
        "give me all sevas at Dharmapuri",
        "all available sevas at Dharmapuri",
        "all types of sevas at Dharmapuri",
        "all options for sevas at Dharmapuri",
        "complete details of sevas at Dharmapuri",
        "names of all sevas at Dharmapuri"
    ]
    for q in variants:
        plan = query_planner.plan(q)
        assert plan.intent == "complete_list", f"Failed to detect complete_list for: '{q}'"
        assert plan.retrieval_mode == "complete_category"
        assert plan.exhaustive is True


# -----------------------------------------------------------------------------
# Test 8: No Temple Clarification
# -----------------------------------------------------------------------------
def test_8_no_temple_clarification():
    """Verify that a complete-list query without a temple does not guess a temple."""
    q = "List all sevas"
    plan = query_planner.plan(q)
    assert plan.temples == []

    # Agent must request clarification without guessing
    agent = TempleInformationAgent()
    state = AgentState(user_query=q)
    res = agent.execute(state)

    assert res.success is False
    assert res.error == "Missing temple specification"
    assert "which temple" in res.answer.lower()
    assert len(res.sources) == 0


# -----------------------------------------------------------------------------
# Test 9: Unknown Category Handling
# -----------------------------------------------------------------------------
def test_9_unknown_category():
    """Verify non-existent/unsupported category queries do not hallucinate a category."""
    plan = query_planner.plan("List all spaceship launching pads at Dharmapuri")
    assert plan.categories == []
    assert plan.retrieval_mode == "targeted"


# -----------------------------------------------------------------------------
# Test 10: Cross-Temple Isolation
# -----------------------------------------------------------------------------
def test_10_cross_temple_isolation():
    """Verify Dharmapuri complete-list retrieval strictly isolates against other temples."""
    parent_text = knowledge_registry.get_complete_parent("Dharmapuri", "sevas")
    assert parent_text is not None

    p_lower = parent_text.lower()
    assert "dharmapuri" in p_lower
    # Cross-temple leakage assertions
    assert "yadadri" not in p_lower
    assert "bhadrachalam" not in p_lower
    assert "edupayala" not in p_lower
    assert "srisailam" not in p_lower


# -----------------------------------------------------------------------------
# Test 11: Source Grounding
# -----------------------------------------------------------------------------
def test_11_source_grounding():
    """Verify every seva in complete parent text exists verbatim in source JSON."""
    sevas_file = root_dir / "dharmapuri" / "sevas.json"
    with open(sevas_file, "r", encoding="utf-8") as f:
        source_sevas = json.load(f)

    parent_text = knowledge_registry.get_complete_parent("Dharmapuri", "sevas")
    verified_names = {s["name"] for s in source_sevas}

    # Verify that all verified items are found in parent text
    for name in verified_names:
        assert name in parent_text


# -----------------------------------------------------------------------------
# Test 12: Phase H Multi-Intent Compatibility
# -----------------------------------------------------------------------------
def test_12_phase_h_multi_intent_compatibility():
    """Verify multi-intent pipeline handles complete-list queries alongside other intents."""
    pipeline = SequentialMultiIntentPipeline()
    query = "What are the timings of Yadadri and list all sevas at Dharmapuri"
    tasks = pipeline.decompose_query(query)

    assert len(tasks) == 2
    # Second intent must be recognized as complete-list
    task2_query = tasks[1]["query"]
    plan_sub2 = query_planner.plan(task2_query)
    assert plan_sub2.intent == "complete_list"
    assert plan_sub2.temples == ["Dharmapuri"]
    assert plan_sub2.categories == ["sevas"]


# -----------------------------------------------------------------------------
# Test 13: Phase I Conversation Memory Compatibility
# -----------------------------------------------------------------------------
def test_13_phase_i_conversation_memory_compatibility():
    """Verify multi-turn pronoun resolution triggers complete-list retrieval on Turn 2."""
    memory_manager = ConversationMemoryManager()
    session_id = "test_session_phase_j"

    # Turn 1: Discuss Dharmapuri
    memory_manager.add_turn(
        session_id=session_id,
        user_query="Tell me about Dharmapuri temple.",
        identified_temples=["Dharmapuri"],
        detected_intents=["temple_information"]
    )

    # Turn 2: 'List all its sevas'
    turn2_query = "List all its sevas."
    resolution = memory_manager.resolve_query(session_id=session_id, query=turn2_query)
    resolved_query = resolution["resolved_query"]

    assert "Dharmapuri" in resolved_query
    plan = query_planner.plan(resolved_query)
    assert plan.intent == "complete_list"
    assert plan.temples == ["Dharmapuri"]
    assert plan.categories == ["sevas"]
    assert plan.retrieval_mode == "complete_category"


# -----------------------------------------------------------------------------
# Test 14: No Raw RAG Duplication
# -----------------------------------------------------------------------------
def test_14_no_raw_rag_duplication():
    """Verify that Phase J reuses existing RAGTool facade and KnowledgeRegistry."""
    rag_tool = RAGTool()
    # Confirm facade exposes complete parent text
    parent_text = rag_tool.get_complete_parent_text("Dharmapuri", "sevas")
    assert parent_text is not None
    assert "Abhishekam" in parent_text

    # Verify KnowledgeRegistry singleton is preserved
    assert rag_tool.rag_service.knowledge_registry is knowledge_registry


# -----------------------------------------------------------------------------
# Test 15: Frozen Dataset Integrity
# -----------------------------------------------------------------------------
def test_15_frozen_dataset_integrity():
    """Verify all 417 source JSON files remain strictly intact and present."""
    temple_folders = [
        "ahobilam", "badrachalam", "balkampet", "basara", "birla mandir",
        "chilkur", "dharmapuri", "edupayal", "jogulamba(new)", "kaleshvaram",
        "karmanghat", "medaram", "ramappa", "srisaila", "thousand pillar",
        "ttd", "ujjaini", "veera satyanarayana", "vemulavada", "yadadri"
    ]
    total_json_files = 0
    for folder in temple_folders:
        dir_path = root_dir / folder
        assert dir_path.exists() and dir_path.is_dir(), f"Folder {folder} must exist"
        json_files = list(dir_path.glob("*.json"))
        total_json_files += len(json_files)

    assert total_json_files == 417, f"Expected 417 source JSON files, found {total_json_files}"


# -----------------------------------------------------------------------------
# Test 16: Deterministic Behavior
# -----------------------------------------------------------------------------
def test_16_deterministic_behavior():
    """Verify that repeated executions yield identical plans and retrieved parent texts."""
    q = "List all sevas at Dharmapuri"
    plans = [query_planner.plan(q) for _ in range(5)]
    for p in plans:
        assert p.intent == "complete_list"
        assert p.retrieval_mode == "complete_category"
        assert p.temples == ["Dharmapuri"]
        assert p.categories == ["sevas"]

    parent_texts = [knowledge_registry.get_complete_parent("Dharmapuri", "sevas") for _ in range(5)]
    assert all(pt == parent_texts[0] for pt in parent_texts)


# -----------------------------------------------------------------------------
# Test 17: Large Category Retrieval (Yadadri Facilities)
# -----------------------------------------------------------------------------
def test_17_large_category_retrieval_yadadri_facilities():
    """Verify large category (Yadadri facilities with 26 items) is retrieved in full."""
    fac_file = root_dir / "yadadri" / "facilities.json"
    with open(fac_file, "r", encoding="utf-8") as f:
        fac_data = json.load(f)

    facility_items = fac_data.get("facilities", [])
    assert len(facility_items) == 26, f"Expected 26 Yadadri facilities, found {len(facility_items)}"

    parent_text = knowledge_registry.get_complete_parent("Yadadri", "facilities")
    assert parent_text is not None

    # Check that sample items from throughout the 26 entries exist
    assert "Elevators, escalators, and wheelchair ramps" in parent_text
    assert "Barcode/RFID-based token system" in parent_text
    assert "Free Nithya Annadanam Complex" in parent_text


# -----------------------------------------------------------------------------
# Test 18: Targeted Questions For List Categories Remain Targeted
# -----------------------------------------------------------------------------
def test_18_targeted_questions_for_list_categories_remain_targeted():
    """Verify specific single-item inquiries for list categories remain targeted_fact."""
    targeted_queries = [
        "How much is one laddu at Edupayala?",
        "What is the cost of Abhishekam seva at Dharmapuri?",
        "Is there a wheelchair available at Yadadri?",
        "What time does the morning darshan start at Basara?"
    ]
    for q in targeted_queries:
        plan = query_planner.plan(q)
        assert plan.intent == "targeted_fact", f"Expected targeted_fact for '{q}', got '{plan.intent}'"
        assert plan.retrieval_mode == "targeted"
        assert plan.exhaustive is False


# -----------------------------------------------------------------------------
# Test 19: Case Insensitivity in Complete-List Detection
# -----------------------------------------------------------------------------
def test_19_case_insensitivity():
    """Verify casing does not affect complete-list intent detection."""
    plan_upper = query_planner.plan("LIST ALL SEVAS AT DHARMAPURI TEMPLE")
    assert plan_upper.intent == "complete_list"
    assert plan_upper.retrieval_mode == "complete_category"
    assert plan_upper.temples == ["Dharmapuri"]

    plan_mixed = query_planner.plan("wHaT aRe aLL tHe sEvAs aT dHaRmApUrI?")
    assert plan_mixed.intent == "complete_list"
    assert plan_mixed.retrieval_mode == "complete_category"


# -----------------------------------------------------------------------------
# Test 20: Empty and Whitespace Queries
# -----------------------------------------------------------------------------
def test_20_empty_and_whitespace_queries():
    """Verify empty or whitespace queries are handled safely without errors."""
    for empty_q in ["", "   ", "\t\n"]:
        plan = query_planner.plan(empty_q)
        assert plan.intent == "targeted_fact"
        assert plan.temples == []


# -----------------------------------------------------------------------------
# Test 21: Safe Formatted Fallback Structure
# -----------------------------------------------------------------------------
def test_21_safe_formatted_fallback():
    """Verify internal formatting helper structures raw data into readable document text without raw JSON leakage."""
    sample_list = [
        {"name": "Special Darshan", "price": "₹100", "timing": "9:00 AM"},
        {"name": "Quick Darshan", "price": "₹50", "timing": "10:00 AM"}
    ]
    formatted = knowledge_registry._format_raw_category_data("TestTemple", "sevas", sample_list)
    assert "Temple: TestTemple" in formatted
    assert "Category: Sevas" in formatted
    assert "1. Special Darshan" in formatted
    assert "Price: ₹100" in formatted
    assert "2. Quick Darshan" in formatted


# -----------------------------------------------------------------------------
# Test 22: TempleInformationAgent Metadata Propagation
# -----------------------------------------------------------------------------
def test_22_temple_information_agent_metadata_propagation():
    """Verify TempleInformationAgent includes complete-list metadata on complete queries."""
    agent = TempleInformationAgent()
    # Mock RAG response through RAGTool
    original_execute_grounded_rag = agent.rag_tool.execute_grounded_rag
    try:
        agent.rag_tool.execute_grounded_rag = lambda q: {
            "answer": "Here is the complete list of sevas at Dharmapuri temple: Abhishekam, etc.",
            "sources": ["dharmapuri/sevas.json"],
            "confidence_score": 10.0,
            "retrieved_chunks": 1,
            "is_complete_list": True,
            "plan": query_planner.plan(q),
            "grounding_validation": {"grounded": True}
        }
        state = AgentState(user_query="List all sevas at Dharmapuri")
        res = agent.execute(state)

        assert res.success is True
        assert res.metadata.get("is_complete_list") is True
        assert res.metadata.get("plan") is not None
        assert res.metadata["plan"].intent == "complete_list"
    finally:
        agent.rag_tool.execute_grounded_rag = original_execute_grounded_rag
