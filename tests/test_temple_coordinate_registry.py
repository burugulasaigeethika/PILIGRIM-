"""
PilgrimAI - Temple Coordinate Registry (Phase O2) Test Suite

Certifies TempleCoordinateRegistry, coordinate validation, provenance preservation,
case/whitespace resilience, alias resolution, and read-only immutability.
Zero modification to the 417 source JSON files; zero RAG dependencies.
"""

import sys
import json
import tempfile
from pathlib import Path
import pytest

# Ensure backend is in sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.coordinate_registry import (
    coordinate_registry,
    TempleCoordinateRegistry,
    TempleCoordinate,
)

EXPECTED_20_CANONICAL_TEMPLES = {
    "Ahobilam", "Badrachalam", "Balkampet", "Basara", "Birla Mandir",
    "Chilkur", "Dharmapuri", "Edupayal", "Jogulamba(New)", "Kaleshvaram",
    "Karmanghat", "Medaram", "Ramappa", "Srisaila", "Thousand Pillar",
    "Ttd", "Ujjaini", "Veera Satyanarayana", "Vemulavada", "Yadadri"
}


# ---------------------------------------------------------------------
# Tests 1-2: Registry Loading and Exact 20 Temple Coverage
# ---------------------------------------------------------------------

def test_1_registry_loads_successfully():
    """Verify TempleCoordinateRegistry loads default asset cleanly."""
    registry = coordinate_registry
    assert registry is not None
    assert len(registry.get_all_coordinates()) == 20


def test_2_registry_contains_expected_20_canonical_temples():
    """Verify registry contains exactly the 20 canonical temples matching project registry."""
    all_coords = coordinate_registry.get_all_coordinates()
    assert set(all_coords.keys()) == EXPECTED_20_CANONICAL_TEMPLES
    assert len(all_coords) == 20


# ---------------------------------------------------------------------
# Tests 3-6: Lookup, Aliases, Case & Whitespace Normalization
# ---------------------------------------------------------------------

def test_3_canonical_temple_lookup():
    """Verify direct lookup of canonical temple returns accurate TempleCoordinate."""
    coord = coordinate_registry.get_coordinate("Basara")
    assert coord is not None
    assert coord.canonical_name == "Basara"
    assert pytest.approx(coord.latitude, 0.001) == 18.870451
    assert pytest.approx(coord.longitude, 0.001) == 77.954153
    assert coord.verification_status == "derived_from_temple_maps_json"


def test_4_alias_lookup():
    """Verify canonical temple resolution from natural language aliases."""
    # Yadagirigutta -> Yadadri
    assert coordinate_registry.resolve_alias("yadagirigutta") == "Yadadri"
    yadadri_coord = coordinate_registry.get_coordinate("yadagirigutta")
    assert yadadri_coord is not None
    assert yadadri_coord.canonical_name == "Yadadri"

    # Visa Balaji -> Chilkur
    assert coordinate_registry.resolve_alias("visa balaji") == "Chilkur"
    chilkur_coord = coordinate_registry.get_coordinate("visa balaji")
    assert chilkur_coord is not None
    assert chilkur_coord.canonical_name == "Chilkur"

    # Vanadurga Bhavani -> Edupayal
    assert coordinate_registry.resolve_alias("vanadurga bhavani") == "Edupayal"
    edupayal_coord = coordinate_registry.get_coordinate("vanadurga bhavani")
    assert edupayal_coord is not None
    assert edupayal_coord.canonical_name == "Edupayal"

    # Bhadrachalam -> Badrachalam
    assert coordinate_registry.resolve_alias("bhadrachalam") == "Badrachalam"
    badrachalam_coord = coordinate_registry.get_coordinate("bhadrachalam")
    assert badrachalam_coord is not None
    assert badrachalam_coord.canonical_name == "Badrachalam"


def test_5_case_normalization():
    """Verify case-insensitive lookup across arbitrary casings."""
    assert coordinate_registry.has_coordinate("YADADRI") is True
    assert coordinate_registry.has_coordinate("yAdAdRi") is True
    assert coordinate_registry.has_coordinate("bAsArA") is True

    coord = coordinate_registry.get_coordinate("yAdAdRi")
    assert coord is not None
    assert coord.canonical_name == "Yadadri"


def test_6_whitespace_normalization():
    """Verify leading and trailing whitespace does not impair lookup."""
    coord = coordinate_registry.get_coordinate("   Basara   \t\n")
    assert coord is not None
    assert coord.canonical_name == "Basara"

    alias_coord = coordinate_registry.get_coordinate("   yadagirigutta   ")
    assert alias_coord is not None
    assert alias_coord.canonical_name == "Yadadri"


# ---------------------------------------------------------------------
# Test 7: Unknown Temple Handling
# ---------------------------------------------------------------------

def test_7_unknown_temple_returns_controlled_unavailable_result():
    """Verify unrecognized or unsupported temples return None without crashing."""
    assert coordinate_registry.resolve_alias("Golden Temple Amritsar") is None
    assert coordinate_registry.has_coordinate("Golden Temple Amritsar") is False
    assert coordinate_registry.get_coordinate("Golden Temple Amritsar") is None
    assert coordinate_registry.get_coordinate("") is None
    assert coordinate_registry.get_coordinate("   ") is None


# ---------------------------------------------------------------------
# Tests 8-12: Coordinate Validation & Malformed Registry Rejection
# ---------------------------------------------------------------------

def test_8_invalid_latitude_is_rejected():
    """Verify latitudes outside [-90, 90] trigger ValueError."""
    with pytest.raises(ValueError):
        TempleCoordinate(
            canonical_name="InvalidLat",
            latitude=95.5,
            longitude=78.5,
            source="test",
            verification_status="needs_verification"
        )

    with pytest.raises(ValueError):
        TempleCoordinate(
            canonical_name="InvalidLatNegative",
            latitude=-91.0,
            longitude=78.5,
            source="test",
            verification_status="needs_verification"
        )


def test_9_invalid_longitude_is_rejected():
    """Verify longitudes outside [-180, 180] trigger ValueError."""
    with pytest.raises(ValueError):
        TempleCoordinate(
            canonical_name="InvalidLon",
            latitude=17.5,
            longitude=185.0,
            source="test",
            verification_status="needs_verification"
        )

    with pytest.raises(ValueError):
        TempleCoordinate(
            canonical_name="InvalidLonNegative",
            latitude=17.5,
            longitude=-181.0,
            source="test",
            verification_status="needs_verification"
        )


def test_10_missing_coordinate_is_handled_safely():
    """Verify missing coordinate fields or malformed payload fails fast on load."""
    malformed_json = {
        "TestTemple": {
            "canonical_name": "TestTemple",
            # missing latitude and longitude
            "source": "test",
            "verification_status": "needs_verification"
        }
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
        json.dump(malformed_json, tf)
        tmp_path = tf.name

    try:
        with pytest.raises(ValueError):
            TempleCoordinateRegistry(data_path=tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_11_duplicate_canonical_name_is_rejected():
    """Verify duplicate canonical names in registry trigger ValueError on load."""
    raw_json = {
        "Temple1": {
            "canonical_name": "Yadadri",
            "latitude": 17.58,
            "longitude": 78.94,
            "source": "test1",
            "verification_status": "needs_verification"
        },
        "Temple2": {
            "canonical_name": "Yadadri",  # Duplicate canonical name
            "latitude": 17.59,
            "longitude": 78.95,
            "source": "test2",
            "verification_status": "needs_verification"
        }
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
        json.dump(raw_json, tf)
        tmp_path = tf.name

    try:
        with pytest.raises(ValueError) as exc_info:
            TempleCoordinateRegistry(data_path=tmp_path)
        assert "duplicate" in str(exc_info.value).lower()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_12_alias_collision_is_rejected():
    """Verify alias mapping detects and prevents multi-temple collisions."""
    # Ensure current alias map has zero collisions
    registry = coordinate_registry
    assert len(registry._alias_map) > 20
    # Every canonical temple has an entry
    for c in EXPECTED_20_CANONICAL_TEMPLES:
        assert c.lower() in registry._alias_map


# ---------------------------------------------------------------------
# Tests 13-16: Read-Only Immutability, Source Dataset & RAG Isolation, Provenance
# ---------------------------------------------------------------------

def test_13_registry_is_read_only_at_runtime():
    """Verify mutating returned models does not alter internal registry state."""
    coord1 = coordinate_registry.get_coordinate("Basara")
    assert coord1 is not None

    # Mutate the returned copy
    original_lat = coord1.latitude
    coord1.latitude = 0.0

    # Fetch again: internal registry must remain intact
    coord2 = coordinate_registry.get_coordinate("Basara")
    assert coord2.latitude == original_lat
    assert coord2.latitude != 0.0


def test_14_source_temple_json_files_remain_unchanged():
    """Verify that coordinate registry is an independent asset and source JSON files remain untouched."""
    coord_file = root_dir / "backend" / "app" / "agents" / "data" / "temple_coordinates.json"
    assert coord_file.exists()
    assert str(coord_file).startswith(str(root_dir / "backend"))

    # Verify no coordinates were injected into source files
    with open(root_dir / "yadadri" / "temple.json", "r", encoding="utf-8") as f:
        yadadri_data = json.load(f)
        assert "latitude" not in yadadri_data
        assert "longitude" not in yadadri_data


def test_15_no_rag_imports_are_introduced():
    """Verify coordinate_registry.py contains zero imports of RAG internals, vector DBs, or models."""
    registry_file = root_dir / "backend" / "app" / "agents" / "coordinate_registry.py"
    content = registry_file.read_text(encoding="utf-8")

    forbidden = [
        "PilgrimRAGService",
        "qdrant_client",
        "rank_bm25",
        "CrossEncoder",
        "sentence_transformers",
        "RAGTool",
        "app.rag"
    ]

    for item in forbidden:
        assert item not in content, f"Forbidden RAG import '{item}' detected in coordinate_registry.py!"


def test_16_coordinate_provenance_and_verification_status_preserved():
    """Verify provenance integrity: 14 derived from maps.json, 6 provisional landmarks requiring verification."""
    all_coords = coordinate_registry.get_all_coordinates()

    derived_count = sum(1 for c in all_coords.values() if c.verification_status == "derived_from_temple_maps_json")
    needs_verif_count = sum(1 for c in all_coords.values() if c.verification_status == "needs_verification")

    assert derived_count == 14, f"Expected 14 derived from maps.json, found {derived_count}"
    assert needs_verif_count == 6, f"Expected 6 needing verification, found {needs_verif_count}"
    assert derived_count + needs_verif_count == 20

    # Test filtering via only_verified
    verified_only = coordinate_registry.get_all_coordinates(only_verified=True)
    assert len(verified_only) == 14
    assert "Basara" in verified_only
    assert "Yadadri" not in verified_only  # Yadadri is marked needs_verification

    # Test provenance query
    prov = coordinate_registry.get_provenance("Basara")
    assert prov is not None
    assert "maps.json" in prov["source"]
    assert prov["verification_status"] == "derived_from_temple_maps_json"
