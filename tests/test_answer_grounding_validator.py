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

from app.rag.answer_scope_controller import AnswerScope
from app.rag.answer_grounding_validator import answer_grounding_validator, AnswerGroundingValidator

@pytest.fixture(scope="module")
def validator():
    return AnswerGroundingValidator()

def test_grounding_validator_detects_temple_bleed(validator):
    """Verify validator flags foreign temple names in single_temple responses."""
    scope = AnswerScope(
        scope="single_temple",
        temples=["Badrachalam"],
        categories=["timings"],
        intent="targeted_fact",
        exhaustive=False,
        allow_unrequested_categories=False
    )
    
    dirty_answer = "Bhadrachalam opens at 4:30 AM. Meanwhile, Dharmapuri opens at 5:00 AM."
    report = validator.validate(dirty_answer, scope, [])
    assert report["temple_scope_valid"] is False
    assert report["is_valid"] is False
    assert any("Dharmapuri" in v for v in report["violations"])

def test_grounding_validator_passes_clean_answer(validator):
    """Verify validator accepts clean single_temple responses."""
    scope = AnswerScope(
        scope="single_temple",
        temples=["Badrachalam"],
        categories=["timings"],
        intent="targeted_fact",
        exhaustive=False,
        allow_unrequested_categories=False
    )
    clean_answer = "Sri Sita Ramachandraswamy Temple, Bhadrachalam is open from 4:30 AM to 1:00 PM and 3:00 PM to 9:00 PM."
    report = validator.validate(clean_answer, scope, [])
    assert report["temple_scope_valid"] is True
    assert report["category_scope_valid"] is True
    assert report["is_valid"] is True

def test_sanitizer_trims_unrequested_category_dump(validator):
    """Verify sanitizer strips extra category header dumps from targeted responses."""
    scope = AnswerScope(
        scope="single_temple",
        temples=["Badrachalam"],
        categories=["timings"],
        intent="targeted_fact",
        exhaustive=False,
        allow_unrequested_categories=False
    )
    polluted_answer = (
        "The temple is open from 4:30 AM to 9:00 PM.\n"
        "### Sevas\n"
        "1. Abhishekam (₹500)\n"
        "2. Kalyanam (₹1000)\n"
        "### Accommodation\n"
        "Rooms available at Yatri Nivas"
    )
    sanitized = validator.sanitize_answer(polluted_answer, scope, [])
    assert "4:30 AM" in sanitized
    assert "### Sevas" not in sanitized
    assert "### Accommodation" not in sanitized
