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

from app.rag.chat import PilgrimRAGService
from app.rag.guardrail import DEFAULT_REFUSAL_MESSAGE

@pytest.fixture(scope="module")
def rag():
    return PilgrimRAGService()

# -----------------------------------------------------------------------------
# Test 1: Targeted Query - Price of Abhishekam in Dharmapuri (Top-3 path)
# -----------------------------------------------------------------------------
def test_orchestrator_targeted_seva_price(rag):
    q = "What is the price of Abhishekam in Dharmapuri?"
    res = rag.answer(q)
    assert res["plan"].retrieval_mode == "targeted"
    assert res["retrieved_chunks"] <= 3
    assert "500" in res["answer"]
    assert any("dharmapuri" in s.lower() for s in res["sources"])

# -----------------------------------------------------------------------------
# Test 2: Complete Category - All Sevas in Dharmapuri
# -----------------------------------------------------------------------------
def test_orchestrator_complete_sevas_dharmapuri(rag):
    q = "What are all the sevas in Dharmapuri?"
    res = rag.answer(q)
    assert res["plan"].retrieval_mode == "complete_category"
    assert res.get("is_complete_list") is True
    # Should mention major sevas
    ans = res["answer"]
    assert "Abhishekam" in ans or "Archana" in ans or "sevas" in ans.lower()

# -----------------------------------------------------------------------------
# Test 3: Complete Category - All Festivals at Basara
# -----------------------------------------------------------------------------
def test_orchestrator_complete_festivals_basara(rag):
    q = "List all festivals at Basara."
    res = rag.answer(q)
    assert res["plan"].retrieval_mode == "complete_category"
    assert res.get("is_complete_list") is True
    assert "Basara" in res["plan"].temples

# -----------------------------------------------------------------------------
# Test 4: Positive Cross-Temple Aggregation - River Bank (11 Temples)
# -----------------------------------------------------------------------------
def test_orchestrator_positive_river_aggregation(rag):
    q = "List all temples that have a river bank."
    res = rag.answer(q)
    assert res["plan"].retrieval_mode == "cross_temple_aggregation"
    assert res.get("is_aggregation") is True
    assert res["retrieved_chunks"] == 11
    assert "Dharmapuri" in res["answer"]
    assert "Basara" in res["answer"]
    assert "Srisaila" in res["answer"]

# -----------------------------------------------------------------------------
# Test 5: Negative Cross-Temple Aggregation - Wheelchair Inaccessible
# -----------------------------------------------------------------------------
def test_orchestrator_negative_wheelchair_aggregation(rag):
    q = "List all temples that don't have wheelchair facilities."
    res = rag.answer(q)
    assert res["plan"].retrieval_mode == "cross_temple_aggregation"
    assert res["plan"].condition == "negative"
    assert res.get("is_aggregation") is True
    assert res["retrieved_chunks"] > 0
    # Balkampet, Ramappa, Ujjaini are confirmed unavailable
    assert "Balkampet" in res["answer"] or "Ramappa" in res["answer"]

# -----------------------------------------------------------------------------
# Test 6: Positive Cross-Temple Aggregation - Accommodation
# -----------------------------------------------------------------------------
def test_orchestrator_positive_accommodation_aggregation(rag):
    q = "Which temples have accommodation?"
    res = rag.answer(q)
    assert res["plan"].retrieval_mode == "cross_temple_aggregation"
    assert res.get("is_aggregation") is True
    assert res["retrieved_chunks"] > 3  # No Top-3 limit

# -----------------------------------------------------------------------------
# Test 7: Negative Cross-Temple Aggregation - Restaurants
# -----------------------------------------------------------------------------
def test_orchestrator_negative_restaurants_aggregation(rag):
    q = "Which temples don't have restaurants?"
    res = rag.answer(q)
    assert res["plan"].retrieval_mode == "cross_temple_aggregation"
    assert res["plan"].condition == "negative"
    assert res.get("is_aggregation") is True

# -----------------------------------------------------------------------------
# Test 8: Multi-Category Query - Accommodation & Restaurants Near Dharmapuri
# -----------------------------------------------------------------------------
def test_orchestrator_multi_category_query(rag):
    q = "What accommodation and restaurants are available near Dharmapuri?"
    res = rag.answer(q)
    assert res["plan"].retrieval_mode == "multi_category"
    assert "accommodation" in res["plan"].categories
    assert "restaurants" in res["plan"].categories
    assert res.get("is_multi_category") is True
    assert len(res["sources"]) >= 2

# -----------------------------------------------------------------------------
# Test 9: Targeted Query - Timings of Dharmapuri Temple
# -----------------------------------------------------------------------------
def test_orchestrator_targeted_timings(rag):
    q = "What are the timings of Dharmapuri Temple?"
    res = rag.answer(q)
    assert res["plan"].retrieval_mode == "targeted"
    assert res["retrieved_chunks"] <= 3
    assert "5:00" in res["answer"] or "AM" in res["answer"] or "PM" in res["answer"] or "timings" in res["answer"].lower()

# -----------------------------------------------------------------------------
# Test 10: Targeted Query - History of Yadadri
# -----------------------------------------------------------------------------
def test_orchestrator_targeted_history(rag):
    q = "Tell me the history of Yadadri."
    res = rag.answer(q)
    assert res["plan"].retrieval_mode == "targeted"
    assert "Yadadri" in res["plan"].temples

# -----------------------------------------------------------------------------
# Test 11: Broad Temple Query - Everything About Dharmapuri Temple
# -----------------------------------------------------------------------------
def test_orchestrator_broad_temple_query(rag):
    q = "Tell me everything about Dharmapuri Temple."
    res = rag.answer(q)
    assert res["plan"].retrieval_mode == "broad_temple"
    assert res.get("is_broad_temple") is True
    assert len(res["sources"]) > 1

# -----------------------------------------------------------------------------
# Test 12: Single Temple Accessibility Fact Check (Targeted Path)
# -----------------------------------------------------------------------------
def test_orchestrator_single_temple_wheelchair(rag):
    q = "Does Dharmapuri have wheelchair facilities?"
    res = rag.answer(q)
    assert res["plan"].retrieval_mode == "targeted"
    assert "Dharmapuri" in res["plan"].temples

# -----------------------------------------------------------------------------
# Test 13: Unsupported Fact Refusal / No Hallucination
# -----------------------------------------------------------------------------
def test_orchestrator_unsupported_refusal(rag):
    q = "Does Dharmapuri have a helicopter launch pad?"
    res = rag.answer(q)
    assert res["plan"].retrieval_mode == "targeted"
    ans_lower = res["answer"].lower()
    # Must refuse or state not mentioned/not available, strictly NO hallucinated helipad confirmation
    assert (
        "not mentioned" in ans_lower
        or "does not" in ans_lower
        or "no information" in ans_lower
        or "not available" in ans_lower
        or "i don't have" in ans_lower
        or DEFAULT_REFUSAL_MESSAGE.lower() in ans_lower
    )
