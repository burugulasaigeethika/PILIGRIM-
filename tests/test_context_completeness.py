import sys
import json
from pathlib import Path
import pytest
from langchain_core.documents import Document

# Setup path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.rag.completeness_validator import (
    completeness_validator,
    CompletenessValidator,
    CONFIRMED_AVAILABLE,
    CONFIRMED_UNAVAILABLE,
    INFORMATION_NOT_AVAILABLE
)
from app.rag.context_builder import context_builder, ContextBuilder
from app.rag.knowledge_registry import knowledge_registry, KnowledgeRegistry

@pytest.fixture(scope="module")
def validator():
    return CompletenessValidator()

@pytest.fixture(scope="module")
def builder():
    return ContextBuilder()

@pytest.fixture(scope="module")
def k_reg():
    return KnowledgeRegistry()

# -----------------------------------------------------------------------------
# 1. List Completeness Validation Tests
# -----------------------------------------------------------------------------

def test_complete_list_validation_success(validator, k_reg):
    """Test 1: Dharmapuri sevas complete list validation (9/9 items)."""
    val_res = validator.validate_list_completeness(
        temple="Dharmapuri",
        category="sevas",
        retrieved_items_count=9,
        expected_items_count=9
    )
    assert val_res["complete"] is True
    assert val_res["expected_count"] == 9
    assert val_res["retrieved_count"] == 9
    assert val_res["missing_count"] == 0

def test_incomplete_list_validation_failure(validator):
    """Test 2: Incomplete list detection (e.g. 3 retrieved when 9 expected)."""
    val_res = validator.validate_list_completeness(
        temple="Dharmapuri",
        category="sevas",
        retrieved_items_count=3,
        expected_items_count=9
    )
    assert val_res["complete"] is False
    assert val_res["missing_count"] == 6

# -----------------------------------------------------------------------------
# 2. Cross-Temple Aggregation Validation Tests (Positive & Negative)
# -----------------------------------------------------------------------------

def test_river_bank_positive_aggregation_completeness(validator, k_reg):
    """Test 3: River-bank positive aggregation across all 20 temples."""
    temples = k_reg.get_temples()
    assert len(temples) == 20

    evaluation_results = []
    for t in temples:
        data = k_reg.get_temple_raw_data(t, "river_bank")
        status, evidence, field = validator.evaluate_availability(data, "river_bank")
        evaluation_results.append({
            "temple": t,
            "status": status,
            "evidence": evidence,
            "field": field
        })

    agg_res = validator.validate_cross_temple_aggregation(
        category="river_bank",
        condition="positive",
        evaluation_results=evaluation_results,
        total_scope=20
    )

    assert agg_res["total_temples_evaluated"] == 20
    assert agg_res["complete_evaluation"] is True
    assert agg_res["matching_temples_count"] == 11
    
    expected_11 = {
        "Ahobilam", "Badrachalam", "Basara", "Dharmapuri", "Edupayal",
        "Jogulamba(New)", "Kaleshvaram", "Medaram", "Srisaila",
        "Veera Satyanarayana", "Vemulavada"
    }
    assert set(agg_res["matching_temples"]) == expected_11

def test_wheelchair_negative_aggregation_distinguishes_unavailable_from_missing(validator, k_reg):
    """Test 4 & 5: Negative wheelchair aggregation separates confirmed unavailable from missing data."""
    temples = k_reg.get_temples()
    evaluation_results = []

    for t in temples:
        data = k_reg.get_temple_raw_data(t, "wheelchair")
        status, evidence, field = validator.evaluate_availability(data, "wheelchair")
        evaluation_results.append({
            "temple": t,
            "status": status,
            "evidence": evidence,
            "field": field
        })

    agg_res = validator.validate_cross_temple_aggregation(
        category="wheelchair",
        condition="negative",
        evaluation_results=evaluation_results,
        total_scope=20
    )

    assert agg_res["total_temples_evaluated"] == 20
    assert agg_res["matching_temples_count"] > 0
    
    # Verify Balkampet, Ramappa, Ujjaini, Dharmapuri, Edupayal are in confirmed_unavailable
    unavail_temple_names = {item["temple"] for item in agg_res["confirmed_unavailable"]}
    assert "Balkampet" in unavail_temple_names
    assert "Ramappa" in unavail_temple_names
    assert "Ujjaini" in unavail_temple_names
    assert "Edupayal" in unavail_temple_names

    # Verify missing temples are NOT in confirmed_unavailable
    missing_temples = set(agg_res["information_not_available"])
    assert len(missing_temples) > 0
    for m in missing_temples:
        assert m not in unavail_temple_names

def test_missing_data_is_never_classified_as_unavailable(validator):
    """Test 5: Explicitly verify that None / empty records yield INFORMATION_NOT_AVAILABLE."""
    status_none, ev, _ = validator.evaluate_availability(None, "wheelchair")
    assert status_none == INFORMATION_NOT_AVAILABLE
    assert ev is None

    status_empty, ev2, _ = validator.evaluate_availability({}, "accommodation")
    assert status_empty == INFORMATION_NOT_AVAILABLE
    assert ev2 is None

# -----------------------------------------------------------------------------
# 3. Multi-Category Coverage & Context Builder Tests
# -----------------------------------------------------------------------------

def test_multi_category_coverage_validation(validator):
    """Test 6: Multi-category validation confirms all requested categories are covered."""
    req_cats = ["accommodation", "restaurants"]
    ret_cats = {"accommodation", "restaurants"}

    cov = validator.validate_multi_category_coverage(req_cats, ret_cats)
    assert cov["complete"] is True
    assert len(cov["missing_categories"]) == 0

    partial_cov = validator.validate_multi_category_coverage(req_cats, {"accommodation"})
    assert partial_cov["complete"] is False
    assert "restaurants" in partial_cov["missing_categories"]

def test_context_builder_multi_category_formatting(builder):
    """Test 6b: ContextBuilder formats multi-category context with balanced sections."""
    doc_acc = Document(page_content="4 cottages available", metadata={"path": "dharmapuri/accommodation.json"})
    doc_rest = Document(page_content="5 restaurants nearby", metadata={"path": "dharmapuri/restaurants.json"})

    category_docs = {
        "accommodation": [doc_acc],
        "restaurants": [doc_rest]
    }

    ctx = builder.build_multi_category_context("Dharmapuri", category_docs)
    assert "=== CATEGORY: ACCOMMODATION ===" in ctx
    assert "=== CATEGORY: RESTAURANTS ===" in ctx
    assert "4 cottages available" in ctx
    assert "5 restaurants nearby" in ctx

def test_context_builder_deduplication(builder):
    """Test 7: ContextBuilder deduplicates identical documents."""
    doc1 = Document(page_content="Sri Swami vari Abhishekam at 6 AM", metadata={"temple": "Dharmapuri", "category": "sevas"})
    doc2 = Document(page_content="Sri Swami vari Abhishekam at 6 AM", metadata={"temple": "Dharmapuri", "category": "sevas"})
    doc3 = Document(page_content="Tulasi Archana at 8 AM", metadata={"temple": "Dharmapuri", "category": "sevas"})

    ctx = builder.build_targeted_context([doc1, doc2, doc3])
    assert ctx.count("Abhishekam") == 1
    assert "Tulasi Archana" in ctx

def test_context_builder_complete_category_formatting(builder):
    """Test 8: Complete category context formatting with metadata headers."""
    full_text = "1. Abhishekam (₹500)\n2. Tulasi Archana (₹500)"
    ctx = builder.build_complete_category_context(
        temple="Dharmapuri",
        category="sevas",
        full_parent_text=full_text,
        source_path="dharmapuri/sevas.json",
        item_count=2
    )
    assert "[TEMPLE]" in ctx
    assert "Dharmapuri" in ctx
    assert "[CATEGORY]\nSEVAS" in ctx
    assert "[COMPLETENESS]\n2 verified items" in ctx
    assert "Abhishekam" in ctx

def test_context_builder_broad_temple_budgeting(builder):
    """Test 9: Broad temple context prioritizes key categories and stays within budget."""
    category_texts = {
        "temple": "Ancient Narasimha Swamy temple on the banks of Godavari.",
        "timings": "Open 5:00 AM to 8:30 PM.",
        "sevas": "Daily Abhishekam and Archana rituals.",
        "festivals": "Brahmotsavam celebrated annually.",
        "facilities": "Drinking water, parking, and cloak rooms."
    }

    ctx = builder.build_broad_temple_context("Dharmapuri", category_texts, max_categories=4)
    assert "[TEMPLE] Dharmapuri" in ctx
    assert "### Temple" in ctx
    assert "### Timings" in ctx
    assert "### Sevas" in ctx
    assert "### Festivals" in ctx
