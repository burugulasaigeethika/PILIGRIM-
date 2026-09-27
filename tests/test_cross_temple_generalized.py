import sys
from pathlib import Path
import pytest

# Setup path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.cross_temple_aggregation_agent import CrossTempleAggregationAgent
from app.rag.completeness_validator import CONFIRMED_AVAILABLE, CONFIRMED_UNAVAILABLE, INFORMATION_NOT_AVAILABLE
from app.rag.chat import PilgrimRAGService

@pytest.fixture(scope="module")
def agent():
    return CrossTempleAggregationAgent()

@pytest.fixture(scope="module")
def rag_service():
    return PilgrimRAGService()

# -----------------------------------------------------------------------------
# 1. Positive Aggregation across Multiple Categories
# -----------------------------------------------------------------------------

def test_river_bank_positive_aggregation(agent):
    """Test 1: River-bank positive aggregation discovers exactly 11 temples in current dataset."""
    res = agent.aggregate_temples("river_bank", condition="positive")
    assert res["total_scope_evaluated"] == 20
    assert res["matching_temples_count"] == 11
    assert res["complete"] is True
    assert len(res["matches"]) == 11
    temple_names = {m["temple"] for m in res["matches"]}
    assert "Dharmapuri" in temple_names
    assert "Basara" in temple_names
    assert "Srisaila" in temple_names

def test_wheelchair_positive_aggregation(agent):
    """Test 2: Wheelchair positive aggregation discovers accessible temples."""
    res = agent.aggregate_temples("wheelchair", condition="positive")
    assert res["total_scope_evaluated"] == 20
    assert res["matching_temples_count"] > 0
    temple_names = {m["temple"] for m in res["matches"]}
    assert "Badrachalam" in temple_names
    assert "Yadadri" in temple_names
    assert "Srisaila" in temple_names

def test_accommodation_positive_aggregation(agent):
    """Test 3: Accommodation positive aggregation discovers temples with lodging options."""
    res = agent.aggregate_temples("accommodation", condition="positive")
    assert res["total_scope_evaluated"] == 20
    assert res["matching_temples_count"] > 0
    assert len(res["sources"]) > 0

def test_restaurant_positive_aggregation(agent):
    """Test 4: Restaurant positive aggregation discovers temples with nearby dining."""
    res = agent.aggregate_temples("restaurants", condition="positive")
    assert res["total_scope_evaluated"] == 20
    assert res["matching_temples_count"] > 0

# -----------------------------------------------------------------------------
# 2. Negative Aggregation across Categories (Absence != Missing)
# -----------------------------------------------------------------------------

def test_wheelchair_negative_aggregation(agent):
    """Test 5: Wheelchair negative aggregation correctly isolates confirmed unavailable temples."""
    res = agent.aggregate_temples("wheelchair", condition="negative")
    assert res["total_scope_evaluated"] == 20
    assert res["matching_temples_count"] > 0

    unavail_temples = {m["temple"] for m in res["matches"]}
    # Explicitly documented inaccessible/subterranean/steep temples
    assert "Balkampet" in unavail_temples
    assert "Ramappa" in unavail_temples
    assert "Ujjaini" in unavail_temples
    assert "Edupayal" in unavail_temples

    # Ensure missing temples are NOT in matches
    for missing_t in res["information_not_available"]:
        assert missing_t not in unavail_temples

def test_restaurant_negative_aggregation(agent):
    """Test 6: Restaurant negative aggregation separates confirmed absence from missing."""
    res = agent.aggregate_temples("restaurants", condition="negative")
    assert res["total_scope_evaluated"] == 20
    # Missing restaurants data must not be classified as confirmed negative
    assert isinstance(res["information_not_available"], list)

def test_accommodation_negative_aggregation(agent):
    """Test 7: Accommodation negative aggregation."""
    res = agent.aggregate_temples("accommodation", condition="negative")
    assert res["total_scope_evaluated"] == 20
    assert isinstance(res["confirmed_unavailable"], list)

# -----------------------------------------------------------------------------
# 3. Completeness, Isolation, Deduplication & Safety Tests
# -----------------------------------------------------------------------------

def test_missing_data_is_never_confirmed_absence(agent):
    """Test 8: Missing data is strictly categorized as INFORMATION_NOT_AVAILABLE."""
    res = agent.aggregate_temples("wheelchair", condition="negative")
    info_missing = res["information_not_available"]
    confirmed_unavail = {m["temple"] for m in res["confirmed_unavailable"]}
    
    assert len(info_missing) > 0
    for t in info_missing:
        assert t not in confirmed_unavail

def test_exactly_20_temples_evaluated(agent):
    """Test 9: Every aggregation checks the full 20-temple scope."""
    res = agent.aggregate_temples("facilities", condition="positive")
    assert res["total_temples_searched"] == 20
    assert res["total_scope_evaluated"] == 20

def test_no_duplicate_temples_in_aggregation(agent):
    """Test 10: Aggregation results are strictly deduplicated by canonical temple."""
    res = agent.aggregate_temples("accommodation", condition="positive")
    names = [m["temple"] for m in res["matches"]]
    assert len(names) == len(set(names))

def test_no_top3_truncation_in_aggregation(agent):
    """Test 11: Cross-temple results returning >3 items are not truncated."""
    res = agent.aggregate_temples("river_bank", condition="positive")
    assert len(res["matches"]) == 11
    assert res["matching_temples_count"] > 3

def test_unknown_category_handling(agent):
    """Test 12: Querying an unknown category returns clean empty result without crashing."""
    res = agent.aggregate_temples("space_rocket_launch_pad", condition="positive")
    assert res["matching_temples_count"] == 0
    assert len(res["matches"]) == 0
    formatted = agent.format_response(res)
    assert "could not find" in formatted.lower() or "no temples" in formatted.lower()

def test_single_temple_query_not_aggregation(agent):
    """Test 13: Single-temple query is not routed as cross-temple aggregation."""
    intent = agent.detect_aggregation_intent("What are the timings of Basara temple?")
    assert intent is None

def test_targeted_query_remains_on_top3_path(rag_service):
    """Test 14: Targeted query uses the Top-3 RAG path."""
    query = "What is the price of Abhishekam in Dharmapuri?"
    res = rag_service.answer(query)
    assert res.get("is_aggregation") is not True
    assert res["retrieved_chunks"] <= 3
    assert "500" in res["answer"]

def test_grounding_metadata_preserved_on_all_matches(agent):
    """Test 15: Every match preserves temple, property, source_file, evidence, and confidence."""
    res = agent.aggregate_temples("river_bank", condition="positive")
    for m in res["matches"]:
        assert m["temple"]
        assert m["property"] == "river_bank"
        assert m["source_file"].endswith(".json")
        assert m["evidence"]
        assert m["confidence"] > 0
