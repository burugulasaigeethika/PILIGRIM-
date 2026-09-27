import sys
import json
import pytest
from pathlib import Path

# Setup path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.cross_temple_aggregation_agent import CrossTempleAggregationAgent
from app.rag.chat import PilgrimRAGService

# Test fixture defining expected baseline set for the current 20-temple dataset
EXPECTED_RIVER_BANK_TEMPLES = {
    "Ahobilam",
    "Badrachalam",
    "Basara",
    "Dharmapuri",
    "Edupayal",
    "Jogulamba(New)",
    "Kaleshvaram",
    "Medaram",
    "Srisaila",
    "Veera Satyanarayana",
    "Vemulavada"
}

@pytest.fixture(scope="module")
def agent():
    return CrossTempleAggregationAgent()

@pytest.fixture(scope="module")
def rag_service():
    return PilgrimRAGService()

# -----------------------------------------------------------------------------
# 1. Intent Detection Tests
# -----------------------------------------------------------------------------

def test_intent_detection_cross_temple_queries(agent):
    """Verify that multi-temple queries are identified as cross-temple aggregation."""
    queries = [
        "List all the temples that have river bank",
        "Which temples have a river?",
        "What temples have parking?",
        "Which temples offer Annadanam?",
        "List all temples with accommodation",
        "Which temples provide prasadam?",
        "Show me all temples that have restaurants"
    ]
    for q in queries:
        intent = agent.detect_aggregation_intent(q)
        assert intent is not None, f"Expected aggregation intent for query: '{q}'"
        assert intent["is_aggregation"] is True

def test_specific_temple_query_not_aggregation(agent, rag_service):
    """Verify that specific-temple queries are NOT classified as aggregation."""
    specific_queries = [
        "Does Dharmapuri have a river bank?",
        "What are the river facilities at Dharmapuri?",
        "What is the price of Abhishekam in Dharmapuri?",
        "What are the sevas in Dharmapuri?",
        "Tell me about Basara temple timings"
    ]
    for q in specific_queries:
        # Check temple detection
        detected_temple = rag_service._detect_temple(q)
        assert detected_temple is not None, f"Expected single-temple detection for: '{q}'"

def test_normal_query_not_aggregation(agent):
    """Verify normal informational queries do not trigger aggregation."""
    non_agg_queries = [
        "What is the dress code?",
        "How to reach by bus?",
        "Tell me about temple history"
    ]
    for q in non_agg_queries:
        intent = agent.detect_aggregation_intent(q)
        assert intent is None, f"Query '{q}' should NOT trigger aggregation intent"

# -----------------------------------------------------------------------------
# 2. Exhaustive Aggregation & Evidence Tests
# -----------------------------------------------------------------------------

def test_river_bank_returns_11_current_results(agent):
    """Verify dynamic discovery returns 11 matching temples for the current dataset."""
    result = agent.aggregate_temples("river_bank")
    assert result["matching_temples_count"] == 11, f"Expected 11 river-bank temples, found {result['matching_temples_count']}"

def test_river_bank_aggregation_exact_set(agent):
    """Verify exact set match against expected baseline without false positives or negatives."""
    result = agent.aggregate_temples("river_bank")
    actual_temples = {m["temple"] for m in result["matches"]}

    assert actual_temples == EXPECTED_RIVER_BANK_TEMPLES, (
        f"Mismatch in river bank temples!\n"
        f"Missing: {EXPECTED_RIVER_BANK_TEMPLES - actual_temples}\n"
        f"Unexpected: {actual_temples - EXPECTED_RIVER_BANK_TEMPLES}"
    )

def test_no_top3_truncation(agent):
    """Verify that cross-temple aggregation is not truncated at Top-3 boundary."""
    result = agent.aggregate_temples("river_bank")
    assert result["matching_temples_count"] > 3
    assert len(result["matches"]) == 11

def test_no_duplicate_temples(agent):
    """Verify no duplicate temple entries exist in the result set."""
    result = agent.aggregate_temples("river_bank")
    temple_names = [m["temple"] for m in result["matches"]]
    assert len(temple_names) == len(set(temple_names)), "Duplicate temples found in aggregation results!"

def test_every_result_has_source_evidence(agent):
    """Verify every returned match has valid source file, property, and evidence."""
    result = agent.aggregate_temples("river_bank")
    for match in result["matches"]:
        assert match["temple"], "Temple name must not be empty"
        assert match["source_file"].endswith(".json"), "Source file must be a JSON file"
        assert match["evidence"], "Evidence string must not be empty"
        assert match["confidence"] > 0, "Confidence score must be positive"

def test_second_cross_temple_property(agent):
    """Verify aggregation capability across other properties like accommodation."""
    result = agent.aggregate_temples("accommodation")
    assert result["matching_temples_count"] > 0
    assert result["total_temples_searched"] == 20
    for match in result["matches"]:
        assert match["property"] == "accommodation"
        assert "accommodation" in match["source_file"]

def test_unknown_property_is_grounded(agent):
    """Verify unknown/unsupported properties return empty result without hallucination."""
    result = agent.aggregate_temples("flying_helicopters_xyz")
    assert result["matching_temples_count"] == 0
    assert len(result["matches"]) == 0

def test_no_match_returns_grounded_empty_result(agent):
    """Verify format_response returns grounded refusal when no matches exist."""
    empty_result = {
        "property_key": "space_launches",
        "total_temples_searched": 20,
        "matching_temples_count": 0,
        "matches": [],
        "sources": []
    }
    response = agent.format_response(empty_result)
    assert "could not find" in response.lower()

# -----------------------------------------------------------------------------
# 3. Chat Pipeline Integration & Baseline Preservation Tests
# -----------------------------------------------------------------------------

def test_chat_pipeline_routes_aggregation_query(rag_service):
    """Verify that PilgrimRAGService.answer routes cross-temple queries correctly."""
    query = "List all the temples that have river bank"
    res = rag_service.answer(query)

    assert res.get("is_aggregation") is True
    assert res["retrieved_chunks"] == 11
    assert len(res["sources"]) == 11
    assert "Dharmapuri" in res["answer"]
    assert "Basara" in res["answer"]
    assert "Srisaila" in res["answer"]
    assert "Badrachalam" in res["answer"] or "Bhadrachalam" in res["answer"]

def test_aggregation_does_not_modify_normal_rag(rag_service):
    """Verify that targeted single-temple queries remain on the Top-3 RAG path."""
    query = "What is the price of Abhishekam in Dharmapuri?"
    res = rag_service.answer(query)

    assert res.get("is_aggregation") is not True
    assert res["retrieved_chunks"] <= 3
    assert "500" in res["answer"]
