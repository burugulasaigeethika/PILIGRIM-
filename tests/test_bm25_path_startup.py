import os
import sys
import asyncio
from pathlib import Path
import pytest

# Ensure backend is on sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.rag.config import _sanitize_path, settings
from app.main import app
from app.api.chat import chat_endpoint, ChatRequest


def test_path_sanitization_single_quoted():
    """Requirement A: single-quoted path is stripped and normalized."""
    raw = "'./bm25_index'"
    cleaned = _sanitize_path(raw)
    assert cleaned == os.path.normpath("./bm25_index")
    assert "'" not in cleaned
    assert '"' not in cleaned


def test_path_sanitization_double_quoted():
    """Requirement B: double-quoted path is stripped and normalized."""
    raw = '"./bm25_index"'
    cleaned = _sanitize_path(raw)
    assert cleaned == os.path.normpath("./bm25_index")
    assert "'" not in cleaned
    assert '"' not in cleaned


def test_path_sanitization_normal_path():
    """Requirement C: normal path remains unchanged."""
    raw = "./bm25_index"
    cleaned = _sanitize_path(raw)
    assert cleaned == os.path.normpath("./bm25_index")


def test_resolved_bm25_and_qdrant_paths():
    """Requirements D & E: resolved paths point to expected workspace directories."""
    project_root = Path(__file__).resolve().parent.parent
    expected_bm25 = str(project_root / "bm25_index")
    expected_qdrant = str(project_root / "qdrant_db")

    assert os.path.normpath(settings.BM25_DIR).lower() == os.path.normpath(expected_bm25).lower()
    assert os.path.normpath(settings.QDRANT_DIR).lower() == os.path.normpath(expected_qdrant).lower()
    assert Path(settings.BM25_DIR).exists()
    assert Path(settings.QDRANT_DIR).exists()


def test_eager_startup_initializes_coordinator():
    """Requirement F: FastAPI startup lifecycle initializes the coordinator successfully."""
    from app.api.chat import get_coordinator
    coordinator = get_coordinator()
    assert coordinator is not None
    assert hasattr(coordinator, "coordinate") or hasattr(coordinator, "agents")


@pytest.mark.asyncio
async def test_chat_yadadri_timings():
    """Requirement G: POST /chat with Yadadri timings query returns normal non-empty response."""
    req = ChatRequest(question="What are the timings of Yadadri?")
    response = await chat_endpoint(req)
    assert response is not None
    assert hasattr(response, "answer")
    assert len(response.answer.strip()) > 0
    ans_lower = response.answer.lower()
    assert any(term in ans_lower for term in ["yadadri", "temple", "am", "pm", "darshan", "open"])
