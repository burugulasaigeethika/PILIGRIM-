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

from app.rag.category_registry import category_registry
from app.rag.knowledge_registry import knowledge_registry
from app.rag.query_planner import query_planner
from app.rag.completeness_validator import completeness_validator
from app.rag.context_builder import context_builder
from app.agents.cross_temple_aggregation_agent import CrossTempleAggregationAgent

@pytest.fixture(scope="module")
def agent():
    return CrossTempleAggregationAgent()

def test_phase6_audit_dataset_has_all_20_temples():
    """Verify all 20 temples are dynamically discoverable in the dataset."""
    temples = knowledge_registry.get_temples()
    assert len(temples) == 20
    assert "Dharmapuri" in temples
    assert "Basara" in temples
    assert "Yadadri" in temples

def test_phase6_audit_all_21_categories_registered():
    """Verify all 21 dataset categories are properly registered."""
    cats = category_registry.all_categories()
    assert len(cats) >= 21
    cat_keys = {c.key for c in cats}
    expected = {
        "accommodation", "restaurants", "contacts", "crowd", "donations",
        "wheelchair", "emergency_contacts", "facilities", "faq", "festivals",
        "gallery", "maps", "nearby_attractions", "prasadam", "river_bank",
        "rules", "sevas", "sub_temples", "temple", "timings", "travel"
    }
    assert expected.issubset(cat_keys)

def test_phase6_audit_temple_detection_accuracy():
    """Verify word-boundary safe temple detection for all 20 temples."""
    temples = knowledge_registry.get_temples()
    for t in temples:
        query = f"What are the timings of {t} temple?"
        detected = query_planner.detect_temple(query)
        assert detected == t, f"Failed to detect {t} from query '{query}' (got '{detected}')"

def test_phase6_audit_complete_list_completeness_validation():
    """Verify list completeness audit for Dharmapuri sevas (10/10 items in source JSON)."""
    raw_data = knowledge_registry.get_temple_raw_data("Dharmapuri", "sevas")
    assert isinstance(raw_data, list)
    expected_len = len(raw_data)
    assert expected_len == 10

    val = completeness_validator.validate_list_completeness(
        temple="Dharmapuri",
        category="sevas",
        retrieved_items_count=expected_len,
        expected_items_count=expected_len
    )
    assert val["complete"] is True
    assert val["missing_count"] == 0

def test_phase6_audit_river_bank_aggregation_exact_scope(agent):
    """Verify cross-temple river-bank positive aggregation across all 20 temples."""
    res = agent.aggregate_temples("river_bank", condition="positive")
    assert res["total_scope_evaluated"] == 20
    assert res["matching_temples_count"] == 11
    assert res["complete"] is True

def test_phase6_audit_wheelchair_negative_aggregation(agent):
    """Verify cross-temple negative wheelchair aggregation separates confirmed absence."""
    res = agent.aggregate_temples("wheelchair", condition="negative")
    assert res["total_scope_evaluated"] == 20
    assert len(res["confirmed_unavailable"]) > 0
    # Missing data must not be in confirmed_unavailable
    unavail_names = {m["temple"] for m in res["confirmed_unavailable"]}
    for m_temple in res["information_not_available"]:
        assert m_temple not in unavail_names

def test_phase6_audit_multi_category_planning():
    """Verify multi-category query plan."""
    q = "What accommodation and restaurants are available near Dharmapuri?"
    plan = query_planner.plan(q)
    assert plan.retrieval_mode == "multi_category"
    assert "accommodation" in plan.categories
    assert "restaurants" in plan.categories

def test_phase6_audit_broad_temple_planning():
    """Verify broad temple query plan."""
    q = "Tell me everything about Dharmapuri Temple."
    plan = query_planner.plan(q)
    assert plan.retrieval_mode == "broad_temple"
    assert plan.exhaustive is True

def test_phase6_audit_targeted_query_planning():
    """Verify targeted factual query plan."""
    q = "What is the price of Abhishekam in Dharmapuri?"
    plan = query_planner.plan(q)
    assert plan.retrieval_mode == "targeted"
    assert plan.exhaustive is False
