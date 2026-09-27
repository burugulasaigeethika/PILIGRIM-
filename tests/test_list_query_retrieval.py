import sys
import json
import re
from pathlib import Path
import pytest

# Ensure root workspace directory is in sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.rag.config import settings
from app.rag.parser import JSONToDocumentParser

# -----------------------------------------------------------------------------
# 1. Parser & Complete List Parent Preservation Tests
# -----------------------------------------------------------------------------

def test_parser_complete_list_preservation_dharmapuri_sevas():
    """Verify that parser creates unified complete parent document for Dharmapuri sevas.json."""
    sevas_file = root_dir / "dharmapuri" / "sevas.json"
    with open(sevas_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    parser = JSONToDocumentParser()
    docs = parser.parse_to_parent_documents("Dharmapuri", "sevas.json", "dharmapuri/sevas.json", data)

    # Must produce exactly 1 unified parent document
    assert len(docs) == 1
    parent_doc = docs[0]
    assert parent_doc.metadata["temple"] == "Dharmapuri"
    assert parent_doc.metadata["category"] == "sevas"
    assert parent_doc.metadata["is_complete_list"] is True
    assert parent_doc.metadata["item_count"] == len(data)

    # Every seva from the source JSON must be present in the page_content
    for seva in data:
        assert seva["name"] in parent_doc.page_content
        assert seva["price"] in parent_doc.page_content

def test_parser_complete_list_preservation_basara_festivals():
    """Verify that parser creates unified complete parent document for Basara festivals.json."""
    festivals_file = root_dir / "basara" / "festivals.json"
    with open(festivals_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    parser = JSONToDocumentParser()
    docs = parser.parse_to_parent_documents("Basara", "festivals.json", "basara/festivals.json", data)

    assert len(docs) == 1
    parent_doc = docs[0]
    assert parent_doc.metadata["is_complete_list"] is True
    assert parent_doc.metadata["item_count"] == len(data)

    for fest in data:
        assert fest["festival_name"] in parent_doc.page_content

# -----------------------------------------------------------------------------
# 2. List Query Classifier Tests
# -----------------------------------------------------------------------------

def test_list_query_classification_patterns():
    """Verify regex classifier detects list intent for varied phrasing without LLM dependency."""
    patterns = {
        "sevas": [
            r"\b(all|list all|what are all the|list of|available|all the|list the)\s+(sevas?|poojas?|pujas?|rituals?)\b",
            r"\b(sevas?|poojas?|pujas?)\s+(list|available|names)\b",
            r"\b(what|which)\s+(sevas?|poojas?|pujas?)\s+(are\s+)?(performed|available|there)\b",
            r"\bsevas\s+(in|at|of)\b"
        ],
        "festivals": [
            r"\b(all|list all|what are all the|list of|available|major|annual)\s+(festivals?|utsavams?|utsavalu|brahmotsavams?)\b",
            r"\b(festivals?|utsavams?)\s+(list|celebrated|names)\b",
            r"\b(what|which)\s+(festivals?)\s+(are\s+)?(celebrated|held|there)\b"
        ],
        "facilities": [
            r"\b(all|list all|what are all the|list of|available)\s+(facilities|amenities)\b",
            r"\b(facilities|amenities)\s+(available|list)\b",
            r"\bwhat\s+(facilities|amenities)\s+(are\s+)?(available|provided|there)\b"
        ]
    }

    def detect_category(q):
        q_clean = q.lower()
        for cat, pat_list in patterns.items():
            for pat in pat_list:
                if re.search(pat, q_clean):
                    return cat
        return None

    # True positives (list queries)
    assert detect_category("What are all the sevas in Dharmapuri Temple?") == "sevas"
    assert detect_category("List all sevas available at Dharmapuri") == "sevas"
    assert detect_category("What sevas are performed at Srisailam?") == "sevas"
    assert detect_category("What are all the festivals at Basara?") == "festivals"
    assert detect_category("List of facilities available at Yadadri") == "facilities"

    # True negatives (targeted normal queries)
    assert detect_category("What is the price of Abhishekam in Dharmapuri?") is None
    assert detect_category("What are the timings of Yadadri temple?") is None
    assert detect_category("How to reach Chilkur Balaji temple?") is None

# -----------------------------------------------------------------------------
# 3. Data Integrity & Count Verification Tests
# -----------------------------------------------------------------------------

def test_data_integrity_source_vs_indexed_parent_store():
    """Verify source JSON list item count equals indexed complete parent list item count."""
    parent_store_file = root_dir / "qdrant_db" / "parent_store.json"
    assert parent_store_file.exists(), "parent_store.json must exist in qdrant_db"

    with open(parent_store_file, "r", encoding="utf-8") as f:
        parent_store = json.load(f)

    # 1. Dharmapuri Sevas
    sevas_src = root_dir / "dharmapuri" / "sevas.json"
    with open(sevas_src, "r", encoding="utf-8") as f:
        sevas_data = json.load(f)
    parent_text = parent_store.get("parent_dharmapuri_sevas_complete")
    assert parent_text is not None, "parent_dharmapuri_sevas_complete must be in parent store"
    for item in sevas_data:
        assert item["name"] in parent_text

    # 2. Basara Festivals
    fest_src = root_dir / "basara" / "festivals.json"
    with open(fest_src, "r", encoding="utf-8") as f:
        fest_data = json.load(f)
    fest_text = parent_store.get("parent_basara_festivals_complete")
    assert fest_text is not None, "parent_basara_festivals_complete must be in parent store"
    for item in fest_data:
        assert item["festival_name"] in fest_text
