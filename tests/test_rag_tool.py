"""
Phase B - RAGTool Certification Tests

Verifies the RAGTool read-only facade against the frozen RAG foundation:
1. RAGTool initializes cleanly.
2. retrieve() returns normalized RAGChunk objects for factual queries.
3. RAGChunk contains non-empty text, source, score, and metadata.
4. execute_grounded_rag() delegates to PilgrimRAGService and returns grounded answer.
5. get_registered_temples() returns all 20 canonical temples.
6. get_registered_categories() returns all 21 registered categories.
7. get_temple_category_data() and get_complete_parent_text() return verified read-only data.
8. RAGTool strictly exposes READ-ONLY methods (no ingest, rebuild, delete, upsert, insert).
9. RAGTool source does NOT import qdrant_client, rank_bm25, or sentence_transformers.
10. Errors from invalid input or RAG failures are propagated and not silently masked with fabricated facts.

Integration-level certification against frozen local indices — zero data modification.
"""

import sys
import inspect
from pathlib import Path
import pytest

# Ensure backend is in sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.tools.rag_tool import RAGTool, RAGChunk


@pytest.fixture(scope="module")
def tool():
    return RAGTool()


def test_1_rag_tool_initialization(tool):
    """Verify RAGTool initializes and connects to underlying RAG service."""
    assert tool is not None
    assert tool.rag_service is not None


def test_2_retrieve_factual_query(tool):
    """Verify retrieve() returns chunks for Yadadri timings query."""
    query = "What are the timings of Yadadri temple?"
    chunks = tool.retrieve(query=query, top_k=3)

    assert isinstance(chunks, list)
    assert len(chunks) > 0
    assert all(isinstance(c, RAGChunk) for c in chunks)


def test_3_chunk_metadata_and_source_normalization(tool):
    """Verify RAGChunk normalizes text, sources, and scores."""
    chunks = tool.retrieve(query="What are the timings of Yadadri temple?", top_k=2)
    assert len(chunks) > 0

    first_chunk = chunks[0]
    assert len(first_chunk.text) > 0
    assert first_chunk.source is not None
    assert "yadadri" in first_chunk.source.lower()
    assert first_chunk.score is not None
    assert isinstance(first_chunk.metadata, dict)


def test_4_execute_grounded_rag_delegation(tool):
    """Verify execute_grounded_rag() returns grounded answer with sources and confidence."""
    res = tool.execute_grounded_rag("What are the timings of Yadadri temple?")

    assert isinstance(res, dict)
    assert "answer" in res
    assert len(res["answer"]) > 10
    assert "4:00" in res["answer"] or "9:45" in res["answer"] or "timings" in res["answer"].lower()
    assert res.get("retrieved_chunks", 0) > 0
    assert len(res.get("sources", [])) > 0
    assert any("yadadri" in s.lower() for s in res["sources"])
    assert res.get("confidence_score", -999) > -3.0


def test_5_get_registered_temples(tool):
    """Verify get_registered_temples() returns all 20 canonical temples."""
    temples = tool.get_registered_temples()

    assert isinstance(temples, list)
    assert len(temples) == 20
    assert "Yadadri" in temples
    assert "Basara" in temples
    assert "Badrachalam" in temples
    assert "Dharmapuri" in temples
    assert "Srisaila" in temples


def test_6_get_registered_categories(tool):
    """Verify get_registered_categories() returns all registered categories."""
    categories = tool.get_registered_categories()

    assert isinstance(categories, list)
    assert len(categories) >= 21
    expected_categories = {"timings", "sevas", "festivals", "facilities", "accommodation", "prasadam"}
    assert expected_categories.issubset(set(categories))


def test_7_raw_category_and_complete_parent_retrieval(tool):
    """Verify read-only inspection of source JSON and unified parent text."""
    # Raw JSON data read-only inspection
    raw_timings = tool.get_temple_category_data("Yadadri", "timings")
    assert raw_timings is not None

    # Complete parent resolution from parent store
    complete_parent = tool.get_complete_parent_text("Dharmapuri", "sevas")
    assert complete_parent is not None
    assert len(complete_parent) > 50


def test_8_rag_tool_is_strictly_read_only(tool):
    """Verify RAGTool does not expose write/mutation/rebuild methods."""
    prohibited_keywords = ["ingest", "rebuild", "delete", "update", "insert", "upsert", "reset", "drop", "write"]
    tool_methods = [m[0] for m in inspect.getmembers(tool, predicate=inspect.ismethod)]

    for method_name in tool_methods:
        for keyword in prohibited_keywords:
            assert keyword not in method_name.lower(), (
                f"Prohibited mutation method '{method_name}' exposed on read-only RAGTool!"
            )


def test_9_rag_tool_does_not_import_database_internals():
    """Verify rag_tool.py source file does not import Qdrant, BM25, or SentenceTransformers directly."""
    rag_tool_file = root_dir / "backend" / "app" / "agents" / "tools" / "rag_tool.py"
    content = rag_tool_file.read_text(encoding="utf-8")

    assert "import qdrant_client" not in content
    assert "from qdrant_client" not in content
    assert "import rank_bm25" not in content
    assert "from rank_bm25" not in content
    assert "import sentence_transformers" not in content
    assert "from sentence_transformers" not in content
    assert "LocalQdrantManager" not in content
    assert "LocalBM25Manager" not in content


def test_10_error_handling_and_no_hallucinated_fallbacks(tool):
    """Verify invalid queries raise ValueError and do not fabricate answers."""
    with pytest.raises(ValueError):
        tool.execute_grounded_rag("   ")

    # Empty retrieval returns empty list, not fabricated chunks
    empty_chunks = tool.retrieve("   ")
    assert empty_chunks == []
