import sys
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

from app.rag.query_planner import query_planner, QueryPlan
from app.rag.answer_scope_controller import answer_scope_controller, AnswerScopeController, AnswerScope

@pytest.fixture(scope="module")
def controller():
    return AnswerScopeController()

def test_scope_derivation_targeted_query(controller):
    """Test targeted fact query scope derivation."""
    plan = query_planner.plan("What are the temple timings at Bhadrachalam?")
    scope = controller.derive_scope(plan)
    
    assert scope.scope == "single_temple"
    assert "Badrachalam" in scope.temples
    assert "timings" in scope.categories
    assert scope.allow_unrequested_categories is False
    assert scope.exhaustive is False
    assert "sevas" in scope.prohibited_categories

def test_scope_derivation_complete_list(controller):
    """Test complete list query scope derivation."""
    plan = query_planner.plan("What are all the sevas in Dharmapuri?")
    scope = controller.derive_scope(plan)

    assert scope.scope == "single_temple"
    assert "Dharmapuri" in scope.temples
    assert "sevas" in scope.categories
    assert scope.intent == "complete_list"
    assert scope.exhaustive is True
    assert scope.allow_unrequested_categories is False

def test_scope_derivation_broad_query(controller):
    """Test broad temple query allows multi-category context."""
    plan = query_planner.plan("Tell me everything about Dharmapuri Temple.")
    scope = controller.derive_scope(plan)

    assert scope.scope == "single_temple"
    assert "Dharmapuri" in scope.temples
    assert scope.intent == "broad_information"
    assert scope.allow_unrequested_categories is True

def test_context_filtering_removes_unrequested_categories(controller):
    """Test context filtering keeps only targeted category documents."""
    scope = AnswerScope(
        scope="single_temple",
        temples=["Badrachalam"],
        categories=["timings"],
        intent="targeted_fact",
        exhaustive=False,
        allow_unrequested_categories=False
    )

    doc_timings = Document(page_content="Temple opens 4:30 AM", metadata={"temple": "Badrachalam", "category": "timings"})
    doc_sevas = Document(page_content="Abhishekam at 6:00 AM", metadata={"temple": "Badrachalam", "category": "sevas"})
    doc_foreign = Document(page_content="Dharmapuri timings", metadata={"temple": "Dharmapuri", "category": "timings"})

    filtered = controller.filter_context([doc_timings, doc_sevas, doc_foreign], scope)
    assert len(filtered) == 1
    assert filtered[0].page_content == "Temple opens 4:30 AM"

def test_scoped_prompt_construction_targeted(controller):
    """Test scoped prompt contains strict negative instructions against dumping unrelated categories."""
    scope = AnswerScope(
        scope="single_temple",
        temples=["Badrachalam"],
        categories=["timings"],
        intent="targeted_fact",
        exhaustive=False,
        allow_unrequested_categories=False
    )
    prompt = controller.build_scoped_prompt(scope, "Open 4:30 AM", "What are timings at Bhadrachalam?")
    assert "Answer ONLY the user's specific question" in prompt
    assert "Do NOT output unrelated categories" in prompt
