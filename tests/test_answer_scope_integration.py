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

def test_scope_integration_bhadrachalam_timings_strict(rag):
    """Test 1: 'What are the temple timings at Bhadrachalam?' answers ONLY Bhadrachalam timings."""
    q = "What are the temple timings at Bhadrachalam?"
    res = rag.answer(q)
    
    assert res["plan"].retrieval_mode == "targeted"
    assert res["scope"].temples == ["Badrachalam"]
    assert res["scope"].categories == ["timings"]
    
    ans = res["answer"]
    assert "4:30" in ans or "AM" in ans or "PM" in ans
    
    # Must NOT contain foreign temple dumps or unrelated categories
    assert "Dharmapuri" not in ans
    assert "Basara" not in ans
    assert "### Sevas" not in ans
    assert "### Accommodation" not in ans

def test_scope_integration_dharmapuri_abhishekam_price(rag):
    """Test 2: 'What is the price of Abhishekam in Dharmapuri?' is strictly targeted."""
    q = "What is the price of Abhishekam in Dharmapuri?"
    res = rag.answer(q)
    
    assert res["plan"].retrieval_mode == "targeted"
    assert "500" in res["answer"]
    assert "Bhadrachalam" not in res["answer"]
    assert "### Hotels" not in res["answer"]

def test_scope_integration_complete_sevas_dharmapuri(rag):
    """Test 3: 'What are all the sevas in Dharmapuri?' provides complete seva list."""
    q = "What are all the sevas in Dharmapuri?"
    res = rag.answer(q)
    
    assert res["plan"].retrieval_mode == "complete_category"
    assert res.get("is_complete_list") is True
    assert "Abhishekam" in res["answer"]
    assert "Archana" in res["answer"]

def test_scope_integration_complete_festivals_basara(rag):
    """Test 4: 'List all festivals at Basara.' provides complete festivals without foreign temple info."""
    q = "List all festivals at Basara."
    res = rag.answer(q)
    
    assert res["plan"].retrieval_mode == "complete_category"
    assert "Basara" in res["plan"].temples
    assert "Yadadri" not in res["answer"]

def test_scope_integration_river_bank_aggregation(rag):
    """Test 5: 'List all temples that have a river bank.' returns exact 11 temples."""
    q = "List all temples that have a river bank."
    res = rag.answer(q)
    
    assert res["plan"].retrieval_mode == "cross_temple_aggregation"
    assert res["retrieved_chunks"] == 11
    assert "Dharmapuri" in res["answer"]
    assert "Basara" in res["answer"]

def test_scope_integration_negative_wheelchair_aggregation(rag):
    """Test 6: 'List all temples that don't have wheelchair facilities.' separates confirmed absence."""
    q = "List all temples that don't have wheelchair facilities."
    res = rag.answer(q)
    
    assert res["plan"].retrieval_mode == "cross_temple_aggregation"
    assert res["plan"].condition == "negative"
    assert "Balkampet" in res["answer"] or "Ramappa" in res["answer"]

def test_scope_integration_positive_accommodation_aggregation(rag):
    """Test 7: 'Which temples have accommodation?' returns full scope."""
    q = "Which temples have accommodation?"
    res = rag.answer(q)
    
    assert res["plan"].retrieval_mode == "cross_temple_aggregation"
    assert res["retrieved_chunks"] > 3

def test_scope_integration_multi_category_accommodation_restaurants(rag):
    """Test 8: 'What accommodation and restaurants are available near Dharmapuri?' contains both."""
    q = "What accommodation and restaurants are available near Dharmapuri?"
    res = rag.answer(q)
    
    assert res["plan"].retrieval_mode == "multi_category"
    assert "accommodation" in res["plan"].categories
    assert "restaurants" in res["plan"].categories
    assert res.get("is_multi_category") is True

def test_scope_integration_yadadri_history_targeted(rag):
    """Test 9: 'Tell me the history of Yadadri.' targets Yadadri history only."""
    q = "Tell me the history of Yadadri."
    res = rag.answer(q)
    
    assert res["plan"].retrieval_mode == "targeted"
    assert "Yadadri" in res["plan"].temples
    assert "Dharmapuri" not in res["answer"]

def test_scope_integration_broad_dharmapuri_overview(rag):
    """Test 10: 'Tell me everything about Dharmapuri Temple.' provides structured overview."""
    q = "Tell me everything about Dharmapuri Temple."
    res = rag.answer(q)
    
    assert res["plan"].retrieval_mode == "broad_temple"
    assert res.get("is_broad_temple") is True

def test_scope_integration_dharmapuri_wheelchair_targeted(rag):
    """Test 11: 'Does Dharmapuri have wheelchair facilities?' targets single wheelchair fact."""
    q = "Does Dharmapuri have wheelchair facilities?"
    res = rag.answer(q)
    
    assert res["plan"].retrieval_mode == "targeted"
    assert "Dharmapuri" in res["plan"].temples

def test_scope_integration_fictitious_helipad_refusal(rag):
    """Test 12: 'Does Dharmapuri have a helicopter launch pad?' gives grounded refusal."""
    q = "Does Dharmapuri have a helicopter launch pad?"
    res = rag.answer(q)
    
    assert res["plan"].retrieval_mode == "targeted"
    ans_lower = res["answer"].lower()
    assert (
        "not mentioned" in ans_lower
        or "does not" in ans_lower
        or "no information" in ans_lower
        or "not available" in ans_lower
        or DEFAULT_REFUSAL_MESSAGE.lower() in ans_lower
    )
