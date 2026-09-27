import os
import sys
import pytest
from pathlib import Path

# Ensure root workspace directory is in sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.rag.config import settings
from app.rag.loader import TempleDatasetLoader
from app.rag.parser import JSONToDocumentParser
from app.rag.chat import PilgrimRAGService
from app.rag.guardrail import DEFAULT_REFUSAL_MESSAGE

@pytest.fixture(scope="module")
def rag_service():
    return PilgrimRAGService()

# -----------------------------------------------------------------------------
# 1. Dataset & Schema Flexibility Tests
# -----------------------------------------------------------------------------

def test_dataset_loader_discovers_all_temples():
    """Verify loader discovers all temple directories without hardcoding."""
    loader = TempleDatasetLoader(dataset_dir=settings.DATASET_DIR)
    folders = loader.discover_temple_folders()
    folder_names = [f.name.lower() for f in folders]

    assert len(folders) >= 14, f"Expected at least 14 temple folders, found {len(folders)}"
    assert "yadadri" in folder_names
    assert "basara" in folder_names
    assert "srisaila" in folder_names
    assert "badrachalam" in folder_names

def test_parser_dynamic_category_extraction():
    """Verify JSON parser handles arbitrary/missing categories without breaking."""
    parser = JSONToDocumentParser()
    sample_data = {
        "custom_category_xyz": {
            "title": "Special Festival",
            "date": "Annual Day",
            "price": "Free"
        }
    }
    docs = parser.parse_to_parent_documents("TestTemple", "custom.json", "testtemple/custom.json", sample_data)
    assert len(docs) == 1
    assert docs[0].metadata["temple"] == "TestTemple"
    assert "custom category xyz" in docs[0].metadata["category"]
    assert "Special Festival" in docs[0].page_content

# -----------------------------------------------------------------------------
# 2. Retrieval Precision Tests
# -----------------------------------------------------------------------------

def test_retrieval_yadadri_timings(rag_service):
    """Test retrieval precision for Yadadri timings query."""
    docs = rag_service.retrieve("What are the timings of Yadadri temple?", top_k=5)
    assert len(docs) > 0
    text_content = " ".join([d.page_content.lower() for d in docs])
    assert "yadadri" in text_content
    assert "timing" in text_content or "am" in text_content or "pm" in text_content

def test_retrieval_basara_facilities(rag_service):
    """Test retrieval precision for Basara facilities query."""
    docs = rag_service.retrieve("What facilities are available at Basara temple?", top_k=5)
    assert len(docs) > 0
    text_content = " ".join([d.page_content.lower() for d in docs])
    assert "basara" in text_content

# -----------------------------------------------------------------------------
# 3. Negative Retrieval & Guardrail Tests (Anti-Hallucination)
# -----------------------------------------------------------------------------

def test_negative_query_refusal(rag_service):
    """Verify irrelevant query triggers refusal without hallucination."""
    result = rag_service.answer("What is the cost of space rocket launch ticket at Yadadri?")
    assert DEFAULT_REFUSAL_MESSAGE in result["answer"] or "could not find" in result["answer"].lower()

# -----------------------------------------------------------------------------
# 4. End-to-End RAG Answer Grounding Test
# -----------------------------------------------------------------------------

def test_answer_yadadri_timings(rag_service):
    """Test end-to-end grounded answer generation for Yadadri temple timings."""
    result = rag_service.answer("What are the timings of Yadadri temple?")
    assert result["retrieved_chunks"] > 0
    assert len(result["sources"]) > 0
    assert "answer" in result
    assert len(result["answer"]) > 5

def test_answer_srisailam_sevas(rag_service):
    """Test end-to-end grounded answer generation for Srisailam sevas."""
    result = rag_service.answer("What sevas are performed at Srisailam temple?")
    assert result["retrieved_chunks"] > 0
    assert "answer" in result
