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

from app.rag.category_registry import category_registry, CategoryRegistry
from app.rag.knowledge_registry import knowledge_registry, KnowledgeRegistry
from app.rag.query_planner import query_planner, QueryPlanner, QueryPlan

@pytest.fixture(scope="module")
def planner():
    return QueryPlanner()

@pytest.fixture(scope="module")
def k_registry():
    return KnowledgeRegistry()

@pytest.fixture(scope="module")
def c_registry():
    return CategoryRegistry()

# -----------------------------------------------------------------------------
# 1. Category Registry Tests
# -----------------------------------------------------------------------------

def test_category_registry_covers_all_discovered_categories(c_registry):
    """Verify registry contains all 21 core dataset categories."""
    cats = {c.key for c in c_registry.all_categories()}
    expected_categories = {
        "accommodation", "restaurants", "contacts", "crowd", "donations",
        "wheelchair", "emergency_contacts", "facilities", "faq", "festivals",
        "gallery", "maps", "nearby_attractions", "prasadam", "river_bank",
        "rules", "sevas", "sub_temples", "temple", "timings", "travel"
    }
    assert expected_categories.issubset(cats), f"Missing categories: {expected_categories - cats}"

def test_category_registry_synonym_matching(c_registry):
    """Verify synonym matching works accurately."""
    assert "wheelchair" in c_registry.match_categories("Are there ramps and wheelchair access?")
    assert "river_bank" in c_registry.match_categories("Where can I take a holy dip in the river ghats?")
    assert "sevas" in c_registry.match_categories("What are the pooja rituals and abhishekam?")
    assert "prasadam" in c_registry.match_categories("Is free annadanam meal provided?")

# -----------------------------------------------------------------------------
# 2. Knowledge Registry Tests
# -----------------------------------------------------------------------------

def test_knowledge_registry_discovers_all_20_temples(k_registry):
    """Verify knowledge registry dynamically discovers all 20 temples."""
    temples = k_registry.get_temples()
    assert len(temples) == 20, f"Expected 20 temples, found {len(temples)}: {temples}"
    assert "Dharmapuri" in temples
    assert "Basara" in temples
    assert "Yadadri" in temples
    assert "Srisaila" in temples

def test_knowledge_registry_temple_category_lookups(k_registry):
    """Verify per-temple category availability lookup."""
    dharmapuri_cats = k_registry.get_categories_for_temple("Dharmapuri")
    assert "sevas" in dharmapuri_cats
    assert "river_bank" in dharmapuri_cats
    assert "timings" in dharmapuri_cats

    basara_cats = k_registry.get_categories_for_temple("Basara")
    assert "festivals" in basara_cats
    assert "facilities" in basara_cats

def test_knowledge_registry_complete_parent_resolution(k_registry):
    """Verify complete parent text retrieval from parent_store."""
    complete_sevas = k_registry.get_complete_parent("Dharmapuri", "sevas")
    assert complete_sevas is not None
    assert "Abhishekam" in complete_sevas
    assert "Tulasi" in complete_sevas

    complete_festivals = k_registry.get_complete_parent("Basara", "festivals")
    assert complete_festivals is not None
    assert "Vasant" in complete_festivals or "Navarathr" in complete_festivals or "Mahasivarathri" in complete_festivals

def test_knowledge_registry_wheelchair_lookups(k_registry):
    """Verify wheelchair / elderly accessibility mapping."""
    balkampet_files = k_registry.get_source_files("Balkampet", "wheelchair")
    assert any("elderly_ppl.json" in f for f in balkampet_files)

# -----------------------------------------------------------------------------
# 3. Query Planner - Temple Detection Tests (All 20 Temples)
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("temple_query,expected_temple", [
    ("What are the timings of Ahobilam temple?", "Ahobilam"),
    ("Tell me about Bhadrachalam Lord Rama temple", "Badrachalam"),
    ("Is Balkampet Yellamma open today?", "Balkampet"),
    ("What is special at Basara Saraswathi temple?", "Basara"),
    ("How to reach Birla Mandir Hyderabad?", "Birla Mandir"),
    ("Tell me about Chilkur Visa Balaji", "Chilkur"),
    ("What are sevas in Dharmapuri?", "Dharmapuri"),
    ("Where is Edupayala Vanadurga Bhavani temple located?", "Edupayal"),
    ("Tell me about Jogulamba temple in Alampur", "Jogulamba(New)"),
    ("What is the history of Kaleshwaram Mukteshwara temple?", "Kaleshvaram"),
    ("What are the timings of Karmanghat Hanuman temple?", "Karmanghat"),
    ("When is Sammakka Saralamma Jatara Medaram celebrated?", "Medaram"),
    ("Tell me about Ramappa Rudreshwara temple", "Ramappa"),
    ("What sevas are performed at Srisailam Mallikarjuna temple?", "Srisaila"),
    ("Tell me about Thousand Pillar Temple in Hanamkonda", "Thousand Pillar"),
    ("What are the darshan rules at TTD Tirumala?", "Ttd"),
    ("Where is Ujjaini Mahakali Secunderabad located?", "Ujjaini"),
    ("Tell me about Veera Satyanarayana Swamy temple Annavaram", "Veera Satyanarayana"),
    ("What are the poojas at Vemulawada Rajanna temple?", "Vemulavada"),
    ("How to reach Yadagirigutta Laxmi Narasimha temple Yadadri?", "Yadadri"),
])
def test_temple_detection_all_20_temples(planner, temple_query, expected_temple):
    """Verify word-boundary safe detection of all 20 temples."""
    plan = planner.plan(temple_query)
    assert plan.scope == "single_temple"
    assert expected_temple in plan.temples

# -----------------------------------------------------------------------------
# 4. Query Planner - Retrieval Mode & Intent Classification Tests
# -----------------------------------------------------------------------------

def test_planner_targeted_fact_query(planner):
    """Test 1: Targeted fact query uses targeted Top-3 mode."""
    q = "What is the price of Abhishekam in Dharmapuri?"
    plan = planner.plan(q)
    assert plan.scope == "single_temple"
    assert "Dharmapuri" in plan.temples
    assert "sevas" in plan.categories
    assert plan.intent == "targeted_fact"
    assert plan.retrieval_mode == "targeted"
    assert plan.exhaustive is False

def test_planner_complete_list_query(planner):
    """Test 2: Single-temple complete list query uses complete_category mode."""
    q = "What are all the sevas in Dharmapuri?"
    plan = planner.plan(q)
    assert plan.scope == "single_temple"
    assert "Dharmapuri" in plan.temples
    assert "sevas" in plan.categories
    assert plan.intent == "complete_list"
    assert plan.retrieval_mode == "complete_category"
    assert plan.exhaustive is True

def test_planner_complete_festivals_query(planner):
    """Test 3: List all festivals at Basara."""
    q = "List all festivals at Basara."
    plan = planner.plan(q)
    assert plan.scope == "single_temple"
    assert "Basara" in plan.temples
    assert "festivals" in plan.categories
    assert plan.intent == "complete_list"
    assert plan.retrieval_mode == "complete_category"
    assert plan.exhaustive is True

def test_planner_cross_temple_positive_aggregation_river(planner):
    """Test 4: Cross-temple positive river aggregation."""
    q = "List all temples that have a river bank."
    plan = planner.plan(q)
    assert plan.scope == "cross_temple"
    assert "river_bank" in plan.categories
    assert plan.intent == "aggregation"
    assert plan.condition == "positive"
    assert plan.retrieval_mode == "cross_temple_aggregation"
    assert plan.exhaustive is True

def test_planner_cross_temple_negative_aggregation_wheelchair(planner):
    """Test 5: Cross-temple negative wheelchair aggregation."""
    q = "List all temples that don't have wheelchair facilities."
    plan = planner.plan(q)
    assert plan.scope == "cross_temple"
    assert "wheelchair" in plan.categories
    assert plan.intent == "aggregation"
    assert plan.condition == "negative"
    assert plan.retrieval_mode == "cross_temple_aggregation"
    assert plan.exhaustive is True

def test_planner_cross_temple_positive_accommodation(planner):
    """Test 6: Which temples have accommodation?"""
    q = "Which temples have accommodation?"
    plan = planner.plan(q)
    assert plan.scope == "cross_temple"
    assert "accommodation" in plan.categories
    assert plan.intent == "aggregation"
    assert plan.condition == "positive"
    assert plan.retrieval_mode == "cross_temple_aggregation"
    assert plan.exhaustive is True

def test_planner_cross_temple_negative_restaurants(planner):
    """Test 7: Which temples don't have restaurants?"""
    q = "Which temples don't have restaurants?"
    plan = planner.plan(q)
    assert plan.scope == "cross_temple"
    assert "restaurants" in plan.categories
    assert plan.intent == "aggregation"
    assert plan.condition == "negative"
    assert plan.retrieval_mode == "cross_temple_aggregation"
    assert plan.exhaustive is True

def test_planner_multi_category_query(planner):
    """Test 8: Multi-category query for single temple."""
    q = "What accommodation and restaurants are available near Dharmapuri?"
    plan = planner.plan(q)
    assert plan.scope == "single_temple"
    assert "Dharmapuri" in plan.temples
    assert "accommodation" in plan.categories
    assert "restaurants" in plan.categories
    assert plan.intent == "multi_category"
    assert plan.retrieval_mode == "multi_category"
    assert plan.exhaustive is True

def test_planner_timings_targeted_query(planner):
    """Test 9: What are the timings of Dharmapuri Temple?"""
    q = "What are the timings of Dharmapuri Temple?"
    plan = planner.plan(q)
    assert plan.scope == "single_temple"
    assert "Dharmapuri" in plan.temples
    assert "timings" in plan.categories
    assert plan.intent == "targeted_fact"
    assert plan.retrieval_mode == "targeted"
    assert plan.exhaustive is False

def test_planner_history_targeted_query(planner):
    """Test 10: Tell me the history of Yadadri."""
    q = "Tell me the history of Yadadri."
    plan = planner.plan(q)
    assert plan.scope == "single_temple"
    assert "Yadadri" in plan.temples
    assert "temple" in plan.categories
    assert plan.intent == "targeted_fact"
    assert plan.retrieval_mode == "targeted"
    assert plan.exhaustive is False

def test_planner_broad_temple_information(planner):
    """Test 11: Tell me everything about Dharmapuri Temple."""
    q = "Tell me everything about Dharmapuri Temple."
    plan = planner.plan(q)
    assert plan.scope == "single_temple"
    assert "Dharmapuri" in plan.temples
    assert plan.intent == "broad_information"
    assert plan.retrieval_mode == "broad_temple"
    assert plan.exhaustive is True

def test_planner_single_temple_wheelchair_check(planner):
    """Test 12: Does Dharmapuri have wheelchair facilities? (Targeted, NOT cross-temple aggregation)"""
    q = "Does Dharmapuri have wheelchair facilities?"
    plan = planner.plan(q)
    assert plan.scope == "single_temple"
    assert "Dharmapuri" in plan.temples
    assert "wheelchair" in plan.categories
    assert plan.intent == "targeted_fact"
    assert plan.retrieval_mode == "targeted"
    assert plan.exhaustive is False

def test_planner_unsupported_category_query(planner):
    """Test 13: Does Dharmapuri have a helicopter launch pad?"""
    q = "Does Dharmapuri have a helicopter launch pad?"
    plan = planner.plan(q)
    assert plan.scope == "single_temple"
    assert "Dharmapuri" in plan.temples
    assert len(plan.categories) == 0
    assert plan.intent == "targeted_fact"
    assert plan.retrieval_mode == "targeted"

def test_planner_general_query_no_temple(planner):
    """Test 14: General question with no temple or aggregation trigger."""
    q = "What is the traditional dress code for visiting South Indian temples?"
    plan = planner.plan(q)
    assert plan.scope == "general"
    assert plan.intent == "targeted_fact"
    assert plan.retrieval_mode == "targeted"
    assert plan.exhaustive is False
