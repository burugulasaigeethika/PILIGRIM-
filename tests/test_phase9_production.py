import sys
from pathlib import Path
import pytest

# Setup root paths
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.rag.config import settings
from app.rag.category_registry import category_registry
from app.rag.knowledge_registry import knowledge_registry
from app.rag.query_planner import query_planner
from app.rag.chat import PilgrimRAGService

@pytest.fixture(scope="module")
def rag():
    return PilgrimRAGService()

def test_phase9_dataset_count_and_integrity():
    """Verify all 20 temples and 21 categories are discoverable in production."""
    temples = knowledge_registry.get_temples()
    assert len(temples) == 20
    assert len(category_registry.all_categories()) == 21

def test_phase9_production_model_is_qwen_1_5b():
    """Verify production configuration strictly uses qwen2.5:1.5b."""
    assert settings.LOCAL_LLM_MODEL == "qwen2.5:1.5b"

def test_phase9_deterministic_routing_matrix():
    """Verify deterministic routing across all 5 production routes."""
    assert query_planner.plan("What are the timings of Bhadrachalam?").retrieval_mode == "targeted"
    assert query_planner.plan("What are all the sevas in Dharmapuri?").retrieval_mode == "complete_category"
    assert query_planner.plan("Which temples have a river bank?").retrieval_mode == "cross_temple_aggregation"
    assert query_planner.plan("Which temples don't have wheelchair facilities?").retrieval_mode == "cross_temple_aggregation"
    assert query_planner.plan("What accommodation and restaurants are available near Dharmapuri?").retrieval_mode == "multi_category"
    assert query_planner.plan("Tell me everything about Dharmapuri Temple.").retrieval_mode == "broad_temple"

def test_phase9_cross_temple_isolation_and_scope(rag):
    """Verify single-temple targeted queries do not bleed across temples."""
    res = rag.answer("What are the temple timings at Bhadrachalam?")
    assert res["plan"].retrieval_mode == "targeted"
    assert "Dharmapuri" not in res["answer"]
    assert "Basara" not in res["answer"]
