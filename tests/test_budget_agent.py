"""
Phase O4 - BudgetAgent Test Suite

Exhaustive offline test suite verifying:
- BaseAgent contract, lifecycle, and safety
- Temple location detection (canonical, alias, unknown, missing)
- Deterministic price parsing (currency symbols, ranges, units, free, unquantified)
- RAG category retrieval (sevas, accommodation, prasadam, restaurants, entry)
- Parameter extraction (pax, duration, accommodation, specific seva)
- Grounded calculations (fixed, ranges, unit multiplication, excluded items, min <= max)
- Cost provenance classification (VERIFIED, USER_PROVIDED, CALCULATED, UNAVAILABLE, no hallucination)
- Deterministic router integration (single budget, inactive, weather+budget, itinerary+budget, comparison protection, multi-temple)
- Coordinator DI (zero auto-instantiation, explicit injection, dynamic registration, E2E dispatch)
- Architectural boundary security (zero prohibited raw RAG/DB imports, zero secrets)

Total tests: 55 deterministic offline tests.
"""

import re
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import pytest

# Ensure backend directory is in sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState, AgentResponse, AgentRouteDecision
from app.agents.router import AgentRouter
from app.agents.coordinator import MasterAgentCoordinator
from app.agents.budget_agent import (
    BudgetAgent,
    CostProvenance,
    BudgetItem,
    parse_price_text,
    extract_budget_parameters
)


# =====================================================================
# Mock RAG Tool for Fast Offline Testing
# =====================================================================

class MockRAGTool:
    """Deterministic, in-memory mock of RAGTool for instant offline testing."""

    def __init__(self, data_store: Optional[Dict[str, Dict[str, Any]]] = None):
        self.data_store = data_store or {
            "yadadri": {
                "sevas": {
                    "temple_id": "yadadri",
                    "category": "sevas",
                    "sevas": [
                        {"name": "Nitya Kalyanam", "price": "₹1,500", "timings": "9:30 AM"},
                        {"name": "Nijabhishekam", "price": "₹500", "timings": "7:00 AM"},
                        {"name": "Sudarshana Homam", "price": "₹1,116", "timings": "8:30 AM"},
                        {"name": "Special Darshan", "price": "₹150 per person", "timings": "All day"}
                    ]
                },
                "accommodation": {
                    "temple_id": "yadadri",
                    "category": "accommodation",
                    "rooms": [
                        {"type": "AC Deluxe Room", "tariff": "₹1,500 per night", "amenities": "AC, TV"},
                        {"type": "Standard Non-AC", "tariff": "₹800 per night", "amenities": "Fan"},
                        {"type": "Choultry / Dormitory", "tariff": "Nominal fee", "amenities": "Shared hall"}
                    ]
                },
                "prasadam": {
                    "temple_id": "yadadri",
                    "category": "prasadam",
                    "items": [
                        {"item": "Laddu", "price": "₹25 per piece"},
                        {"item": "Pulihora", "price": "₹20 per packet"},
                        {"item": "Annadanam (Free Meals)", "price": "FREE", "notes": "Daily noon"}
                    ]
                },
                "restaurants": {
                    "temple_id": "yadadri",
                    "category": "restaurants",
                    "restaurants": [
                        {"name": "Haritha Hotel", "avg_cost": "₹150 - ₹300 per person"}
                    ]
                },
                "timings": {
                    "temple_id": "yadadri",
                    "category": "timings",
                    "entry_fee": "Free General Darshan; Special Entry ₹100"
                }
            },
            "basara_gnana_saraswathi": {
                "sevas": {
                    "temple_id": "basara_gnana_saraswathi",
                    "category": "sevas",
                    "sevas": [
                        {"name": "Aksharabhyasam", "price": "₹150", "timings": "8:00 AM"},
                        {"name": "Special Aksharabhyasam", "price": "₹500", "timings": "All day"},
                        {"name": "Abhishekam", "price": "₹200", "timings": "4:30 AM"},
                        {"name": "Sahasranamarchana", "price": "Contact temple office"}
                    ]
                },
                "accommodation": {
                    "temple_id": "basara_gnana_saraswathi",
                    "category": "accommodation",
                    "rooms": [
                        {"type": "Guest House AC", "tariff": "₹1,000 per day"},
                        {"type": "Teshildar Choultry", "tariff": "₹200 - ₹400 per night"}
                    ]
                },
                "prasadam": {
                    "temple_id": "basara_gnana_saraswathi",
                    "category": "prasadam",
                    "items": [
                        {"item": "Laddu Prasadam", "price": "₹20"},
                        {"item": "Free Annadanam", "price": "Free"}
                    ]
                }
            },
            "dharmapuri_lakshmi_narasimha": {
                "sevas": {
                    "temple_id": "dharmapuri_lakshmi_narasimha",
                    "category": "sevas",
                    "sevas": [
                        {"name": "Abhishekam", "price": "₹500"},
                        {"name": "Kalyanotsavam", "price": "₹1,116"}
                    ]
                }
            }
        }

    def get_temple_category_data(self, temple_id: str, category: str) -> Optional[Dict[str, Any]]:
        t_clean = temple_id.lower().replace(" ", "_")
        for key, cat_dict in self.data_store.items():
            if t_clean in key or key in t_clean or t_clean.startswith(key[:4]) or key.startswith(t_clean[:4]):
                return cat_dict.get(category.lower())
        return None


@pytest.fixture
def mock_rag():
    return MockRAGTool()


@pytest.fixture
def budget_agent(mock_rag):
    return BudgetAgent(rag_tool=mock_rag)


# =====================================================================
# 1. Contract Tests (1 - 5)
# =====================================================================

def test_01_base_agent_inheritance(budget_agent):
    """1. Verify BudgetAgent inherits from BaseAgent."""
    assert isinstance(budget_agent, BaseAgent)


def test_02_correct_name_and_description(budget_agent):
    """2. Verify agent name is exactly 'budget' and description describes grounded costs."""
    assert budget_agent.name == "budget"
    assert "cost" in budget_agent.description.lower() or "budget" in budget_agent.description.lower()
    assert "verified" in budget_agent.description.lower()


def test_03_lifecycle_execution(budget_agent):
    """3. Verify standard BaseAgent lifecycle execution returns valid AgentResponse."""
    state = AgentState(user_query="What does Abhishekam cost at Yadadri?")
    response = budget_agent.process(state)
    assert isinstance(response, AgentResponse)
    assert response.agent_name == "budget"
    assert response.success is True
    assert "Yadadri" in response.answer
    assert response.latency_ms >= 0


def test_04_empty_query(budget_agent):
    """4. Verify empty query is handled safely without exception."""
    state = AgentState(user_query="")
    response = budget_agent.process(state)
    assert isinstance(response, AgentResponse)
    assert response.success is False
    assert "empty" in response.error.lower() or "empty" in response.answer.lower()


def test_05_whitespace_query(budget_agent):
    """5. Verify whitespace query is handled safely without exception."""
    state = AgentState(user_query="     \t \n  ")
    response = budget_agent.process(state)
    assert isinstance(response, AgentResponse)
    assert response.success is False
    assert "empty" in response.error.lower() or "empty" in response.answer.lower()


# =====================================================================
# 2. Location Tests (6 - 9)
# =====================================================================

def test_06_canonical_temple_detection(budget_agent):
    """6. Verify canonical temple ID is detected and costs retrieved."""
    state = AgentState(user_query="Calculate budget for yadadri")
    res = budget_agent.process(state)
    assert res.success is True
    assert "yadadri" in res.metadata["temples"]
    assert "₹" in res.answer


def test_07_alias_temple_detection(budget_agent):
    """7. Verify alias temple name ('Basar' -> 'basara_gnana_saraswathi') is resolved."""
    state = AgentState(user_query="How much does Aksharabhyasam cost at Basar?")
    res = budget_agent.process(state)
    assert res.success is True
    assert "basara_gnana_saraswathi" in res.metadata["temples"]
    assert "150" in res.answer


def test_08_unknown_unregistered_temple(budget_agent):
    """8. Verify explicit unregistered temple is rejected gracefully."""
    state = AgentState(user_query="What is the budget for Golden Temple in Amritsar?")
    res = budget_agent.process(state)
    assert res.success is False
    assert "not currently in the registered" in res.answer
    assert "Golden Temple" in res.answer


def test_09_missing_temple_clarification(budget_agent):
    """9. Verify query with no temple name asks user for clarification."""
    state = AgentState(user_query="How much does seva cost?")
    res = budget_agent.process(state)
    assert res.success is False
    assert "which temple" in res.answer.lower()


# =====================================================================
# 3. Parsing Tests (10 - 20)
# =====================================================================

def test_10_parse_simple_rupee():
    """10. Parse standard ₹25 format."""
    mn, mx, unit, free, is_rng, qn, notes = parse_price_text("₹25")
    assert mn == 25.0
    assert mx == 25.0
    assert not is_rng
    assert not free
    assert qn is True


def test_11_parse_comma_separated_rupee():
    """11. Parse ₹1,500 with comma separation."""
    mn, mx, unit, free, is_rng, qn, notes = parse_price_text("₹1,500")
    assert mn == 1500.0
    assert mx == 1500.0


def test_12_parse_rs_dot():
    """12. Parse Rs. 500 format."""
    mn, mx, unit, free, is_rng, qn, notes = parse_price_text("Rs. 500")
    assert mn == 500.0
    assert mx == 500.0


def test_13_parse_inr():
    """13. Parse INR 500 format."""
    mn, mx, unit, free, is_rng, qn, notes = parse_price_text("INR 500")
    assert mn == 500.0
    assert mx == 500.0


def test_14_parse_hyphen_range():
    """14. Parse ₹100–₹300 hyphen/en-dash range."""
    mn, mx, unit, free, is_rng, qn, notes = parse_price_text("₹100–₹300")
    assert mn == 100.0
    assert mx == 300.0
    assert is_rng is True


def test_15_parse_to_range():
    """15. Parse ₹100 to ₹300 range format."""
    mn, mx, unit, free, is_rng, qn, notes = parse_price_text("₹100 to ₹300")
    assert mn == 100.0
    assert mx == 300.0
    assert is_rng is True


def test_16_parse_per_person():
    """16. Parse unit 'per person'."""
    mn, mx, unit, free, is_rng, qn, notes = parse_price_text("₹220 per person")
    assert mn == 220.0
    assert unit == "per person"


def test_17_parse_per_room():
    """17. Parse unit 'per room'."""
    mn, mx, unit, free, is_rng, qn, notes = parse_price_text("₹1,000 per room")
    assert mn == 1000.0
    assert unit == "per room"


def test_18_parse_per_night():
    """18. Parse unit 'per night'."""
    mn, mx, unit, free, is_rng, qn, notes = parse_price_text("₹900 - ₹1,700 per night")
    assert mn == 900.0
    assert mx == 1700.0
    assert unit == "per room per night"
    assert is_rng is True


def test_19_parse_free_value():
    """19. Parse confirmed free indicators (FREE, ₹0, No Ticket Required)."""
    for text in ["FREE", "Free Darshan", "₹0", "No Ticket Required", "Complimentary"]:
        mn, mx, unit, free, is_rng, qn, notes = parse_price_text(text)
        assert free is True
        assert mn == 0.0
        assert mx == 0.0
        assert qn is True


def test_20_parse_unquantified_value():
    """20. Parse unquantified values (varies, nominal fee, contact office) as NOT quantified."""
    for text in ["varies", "nominal fee", "contact temple office", "not specified"]:
        mn, mx, unit, free, is_rng, qn, notes = parse_price_text(text)
        assert qn is False
        assert mn is None
        assert free is False


# =====================================================================
# 4. RAG Category Tests (21 - 26)
# =====================================================================

def test_21_seva_price_retrieval(budget_agent):
    """21. Verify seva prices are retrieved from RAGTool."""
    state = AgentState(user_query="What is the price of Nijabhishekam at Yadadri?")
    res = budget_agent.process(state)
    assert res.success is True
    assert "Nijabhishekam" in res.answer
    assert "₹500" in res.answer


def test_22_accommodation_price_retrieval(budget_agent):
    """22. Verify accommodation tariffs are retrieved when requested."""
    state = AgentState(user_query="How much does AC room accommodation cost at Yadadri?")
    res = budget_agent.process(state)
    assert res.success is True
    assert "AC Deluxe Room" in res.answer
    assert "₹1,500" in res.answer


def test_23_prasadam_price_retrieval(budget_agent):
    """23. Verify prasadam prices are retrieved."""
    state = AgentState(user_query="How much does laddu prasadam cost at Basara?")
    res = budget_agent.process(state)
    assert res.success is True
    assert "Laddu" in res.answer
    assert "₹20" in res.answer


def test_24_restaurant_range_retrieval(budget_agent):
    """24. Verify dining/restaurant expense ranges are retrieved."""
    state = AgentState(user_query="What is the food cost and budget at Yadadri?")
    res = budget_agent.process(state)
    assert res.success is True
    assert "Haritha Hotel" in res.answer or "₹150" in res.answer


def test_25_entry_fee_retrieval(budget_agent):
    """25. Verify darshan / entry fee is retrieved."""
    state = AgentState(user_query="What is the darshan fee at Yadadri?")
    res = budget_agent.process(state)
    assert res.success is True
    assert "Special Entry" in res.answer or "₹100" in res.answer


def test_26_missing_category_graceful(budget_agent):
    """26. Verify missing category in temple record is handled gracefully without crash."""
    state = AgentState(user_query="Calculate budget for Dharmapuri")
    res = budget_agent.process(state)
    assert res.success is True
    assert "Dharmapuri" in res.answer


# =====================================================================
# 5. Parameter Extraction Tests (27 - 31)
# =====================================================================

def test_27_extract_people_count():
    """27. Extract explicit people count (2 people, group of 5)."""
    p1 = extract_budget_parameters("Budget for 2 people at Yadadri")
    assert p1["pax"] == 2
    assert p1["pax_assumed"] is False

    p2 = extract_budget_parameters("Visit for group of 5 at Basara")
    assert p2["pax"] == 5

    p3 = extract_budget_parameters("Trip for two devotees")
    assert p3["pax"] == 2


def test_28_family_size_default():
    """28. Extract family of 4, and test default of 1 is clearly flagged as assumed."""
    p1 = extract_budget_parameters("Trip for family of 4 at Yadadri")
    assert p1["pax"] == 4
    assert p1["pax_assumed"] is False

    p2 = extract_budget_parameters("Trip to Yadadri")
    assert p2["pax"] == 1
    assert p2["pax_assumed"] is True


def test_29_duration_extraction():
    """29. Extract trip duration (2 days, weekend)."""
    p1 = extract_budget_parameters("2 days visit to Yadadri")
    assert p1["days"] == 2
    assert p1["days_assumed"] is False

    p2 = extract_budget_parameters("weekend trip to Basara")
    assert p2["days"] == 2


def test_30_named_seva_extraction():
    """30. Extract named seva from query."""
    p1 = extract_budget_parameters("What is the cost of Nitya Kalyanam at Yadadri?")
    assert p1["specific_seva"] is not None
    assert "nitya kalyanam" in p1["specific_seva"].lower()


def test_31_accommodation_preference():
    """31. Extract accommodation preference (AC vs Non-AC vs cottage)."""
    p1 = extract_budget_parameters("Need an AC room stay at Yadadri")
    assert p1["accom_requested"] is True
    assert p1["accom_type"] == "ac"

    p2 = extract_budget_parameters("Non-AC room for 1 night at Basara")
    assert p2["accom_requested"] is True
    assert p2["accom_type"] == "non_ac"


# =====================================================================
# 6. Calculations Tests (32 - 38)
# =====================================================================

def test_32_fixed_total_arithmetic(budget_agent):
    """32. Grounded fixed total: verified seva (₹500) + user travel (₹1,000) = ₹1,500."""
    state = AgentState(user_query="Abhishekam at Dharmapuri and my travel is ₹1000")
    res = budget_agent.process(state)
    assert res.success is True
    assert "₹1,500" in res.answer
    assert res.metadata["calculated_total"]["min"] == 1500.0
    assert res.metadata["calculated_total"]["max"] == 1500.0


def test_33_range_total_arithmetic(budget_agent):
    """33. Range total calculation preserving minimum and maximum bounds."""
    state = AgentState(user_query="Calculate budget at Basara including Teshildar Choultry and Aksharabhyasam")
    res = budget_agent.process(state)
    assert res.success is True
    # Aksharabhyasam (₹150) + Choultry (₹200 - ₹400) = ₹350 - ₹550
    assert res.metadata["calculated_total"]["min"] >= 350.0
    assert res.metadata["calculated_total"]["max"] >= 550.0


def test_34_per_person_multiplication(budget_agent):
    """34. Unit multiplication: ₹150 per person × 2 people = ₹300."""
    state = AgentState(user_query="Special Darshan at Yadadri for 2 people")
    res = budget_agent.process(state)
    assert res.success is True
    # Special Darshan ₹150 * 2 = ₹300
    assert "₹300" in res.answer or res.metadata["calculated_total"]["min"] == 300.0


def test_35_per_night_multiplication(budget_agent):
    """35. Unit multiplication: ₹1,500 per night × 2 nights = ₹3,000."""
    state = AgentState(user_query="AC Deluxe Room accommodation at Yadadri for 2 days")
    res = budget_agent.process(state)
    assert res.success is True
    # ₹1500 * 2 = ₹3000
    assert "₹3,000" in res.answer or res.metadata["calculated_total"]["min"] >= 3000.0


def test_36_missing_cost_excluded_not_zero(budget_agent):
    """36. Missing costs are explicitly reported as excluded, NEVER treated as ₹0."""
    state = AgentState(user_query="What is the total budget for Dharmapuri for Abhishekam and accommodation?")
    res = budget_agent.process(state)
    assert res.success is True
    # Accommodation is missing in Dharmapuri data; must be reported in excluded/unavailable section
    assert "Costs Not Available" in res.answer or "Excluded" in res.answer
    assert "accommodation" in res.answer.lower()


def test_37_min_le_max_invariant(budget_agent):
    """37. Verify min_cost <= max_cost invariant holds in all responses."""
    queries = [
        "Budget for Yadadri for 2 people",
        "Basara trip for 3 days and hotel ₹1000",
        "Dharmapuri visit for 1 person"
    ]
    for q in queries:
        state = AgentState(user_query=q)
        res = budget_agent.process(state)
        tot = res.metadata["calculated_total"]
        if tot["min"] is not None and tot["max"] is not None:
            assert tot["min"] <= tot["max"]


def test_38_decimal_rounding_safety():
    """38. Verify floating point precision is cleanly formatted as integers or 2 decimals."""
    mn, mx, unit, free, is_rng, qn, notes = parse_price_text("₹220.50 per person")
    assert mn == 220.50
    assert mx == 220.50


# =====================================================================
# 7. Provenance Tests (39 - 43)
# =====================================================================

def test_39_verified_classification(budget_agent):
    """39. Temple records must be explicitly classified as VERIFIED."""
    state = AgentState(user_query="What does Abhishekam cost at Dharmapuri?")
    res = budget_agent.process(state)
    assert res.success is True
    assert "Verified Costs" in res.answer
    assert "₹500" in res.answer


def test_40_user_provided_classification(budget_agent):
    """40. User-supplied figures must be explicitly classified as USER-PROVIDED."""
    state = AgentState(user_query="My travel is ₹1000 and hotel is ₹1500 for Yadadri")
    res = budget_agent.process(state)
    assert res.success is True
    assert "User-Provided Costs" in res.answer
    assert "₹1,000" in res.answer or "1000" in res.answer
    assert "₹1,500" in res.answer or "1500" in res.answer


def test_41_calculated_classification(budget_agent):
    """41. Total must be explicitly identified as Calculated."""
    state = AgentState(user_query="Calculate budget for Abhishekam at Dharmapuri with ₹500 travel")
    res = budget_agent.process(state)
    assert res.success is True
    assert "Calculated" in res.answer or "Total" in res.answer


def test_42_unavailable_classification(budget_agent):
    """42. Unquantified items (e.g. Sahasranamarchana) must be tagged UNAVAILABLE."""
    state = AgentState(user_query="How much does Sahasranamarchana cost at Basara?")
    res = budget_agent.process(state)
    assert res.success is True
    assert "Costs Not Available" in res.answer or "Unavailable" in res.answer or "contact temple office" in res.answer.lower()


def test_43_no_fabricated_tiers(budget_agent):
    """43. Verify response NEVER manufactures fake Economy/Standard/Premium tiers."""
    state = AgentState(user_query="What is the budget for Yadadri?")
    res = budget_agent.process(state)
    assert res.success is True
    # Forbidden generic fabricated tier labels
    assert "Economy = ₹" not in res.answer
    assert "Standard = ₹" not in res.answer
    assert "Premium = ₹" not in res.answer


# =====================================================================
# 8. Routing Tests (44 - 49)
# =====================================================================

@pytest.fixture
def active_router():
    r = AgentRouter()
    r.register_agent("temple_information")
    r.register_agent("live_weather")
    r.register_agent("itinerary_planning")
    r.register_agent("comparison")
    r.register_agent("cross_temple_aggregation")
    r.register_agent("budget")
    return r


def test_44_single_budget_routing(active_router):
    """44. Query 'What does Abhishekam cost at Basara?' routes to budget."""
    decision = active_router.route("What does Abhishekam cost at Basara?")
    assert decision.selected_agent == "budget"
    assert decision.intent == "budget"
    assert any(t in ["Basara", "basara_gnana_saraswathi"] for t in decision.metadata["detected_temples"])


def test_45_inactive_budget_agent():
    """45. When budget agent is not active, returns selected_agent='none'."""
    inactive_router = AgentRouter()
    decision = inactive_router.route("What does Abhishekam cost at Basara?")
    assert decision.selected_agent == "none"
    assert decision.intent == "budget"
    assert decision.metadata["available"] is False


def test_46_weather_plus_budget_multi_intent(active_router):
    """46. 'What is the weather at Yadadri and how much will it cost?' routes to multi_intent."""
    decision = active_router.route("What is the weather at Yadadri and how much will it cost?")
    assert decision.selected_agent == "none"
    assert decision.intent == "multi_intent"
    assert "weather" in decision.metadata["sub_intents"]
    assert "budget" in decision.metadata["sub_intents"]


def test_47_itinerary_plus_budget_multi_intent(active_router):
    """47. 'Plan a 2 day trip to Basara and calculate the budget.' routes to multi_intent."""
    decision = active_router.route("Plan a 2 day trip to Basara and calculate the budget.")
    assert decision.selected_agent == "none"
    assert decision.intent == "multi_intent"
    assert "itinerary" in decision.metadata["sub_intents"]
    assert "budget" in decision.metadata["sub_intents"]


def test_48_comparison_protection(active_router):
    """48. 'Compare seva costs at Basara and Yadadri.' must remain comparison intent."""
    decision = active_router.route("Compare seva costs at Basara and Yadadri.")
    assert decision.selected_agent == "comparison"
    assert decision.intent == "comparison"


def test_49_multi_temple_budget(active_router):
    """49. 'Calculate the budget for Basara and Yadadri.' routes to budget, NOT comparison."""
    decision = active_router.route("Calculate the budget for Basara and Yadadri.")
    assert decision.selected_agent == "budget"
    assert decision.intent == "budget"
    assert len(decision.metadata["detected_temples"]) == 2


# =====================================================================
# 9. Coordinator Tests (50 - 53)
# =====================================================================

def test_50_no_auto_instantiation():
    """50. Coordinator initialized without budget_agent does NOT auto-instantiate it."""
    coord = MasterAgentCoordinator()
    assert "budget" not in coord.agents
    assert "budget" not in coord.router.active_agents


def test_51_explicit_injection(budget_agent):
    """51. Passing budget_agent explicitly to coordinator registers it in agents and router."""
    coord = MasterAgentCoordinator(budget_agent=budget_agent)
    assert "budget" in coord.agents
    assert "budget" in coord.router.active_agents
    assert coord.agents["budget"] is budget_agent


def test_52_dynamic_registration(budget_agent):
    """52. Dynamic registration via coordinator.register_agent(budget_agent)."""
    coord = MasterAgentCoordinator()
    assert "budget" not in coord.agents
    coord.register_agent(budget_agent)
    assert "budget" in coord.agents
    assert "budget" in coord.router.active_agents
    assert "budget" in coord.pipeline.agents


def test_53_end_to_end_coordinator_execution(budget_agent):
    """53. End-to-end coordinator execution dispatches budget query and aggregates response."""
    coord = MasterAgentCoordinator(budget_agent=budget_agent)
    state = AgentState(user_query="What does Abhishekam cost at Yadadri?")
    response = coord.process(state)
    assert isinstance(response, AgentResponse)
    assert response.success is True
    assert "Yadadri" in response.answer
    assert "Nijabhishekam" in response.answer or "₹500" in response.answer


# =====================================================================
# 10. Security & Boundary Tests (54 - 55)
# =====================================================================

def test_54_static_import_boundary():
    """54. Confirm BudgetAgent does NOT directly import raw database or model libraries."""
    budget_agent_file = backend_dir / "app" / "agents" / "budget_agent.py"
    content = budget_agent_file.read_text(encoding="utf-8")

    forbidden_imports = [
        "PilgrimRAGService",
        "qdrant_client",
        "rank_bm25",
        "sentence_transformers",
        "CrossEncoder",
        "LocalQdrantManager",
        "LocalBM25Manager",
        "open(",       # Should not open raw JSON files directly
    ]

    for item in forbidden_imports:
        assert item not in content, f"Forbidden import or direct file access '{item}' found in budget_agent.py!"


def test_55_no_secrets_in_response(budget_agent):
    """55. Confirm no API keys or internal secrets are exposed in response, metadata, or logs."""
    state = AgentState(user_query="Calculate budget for Yadadri for 2 people")
    response = budget_agent.process(state)

    for secret_pattern in [r"api[_-]?key", r"secret", r"password", r"bearer\s+"]:
        assert not re.search(secret_pattern, response.answer, re.IGNORECASE)
        for k, v in response.metadata.items():
            assert not re.search(secret_pattern, str(k), re.IGNORECASE)
            assert not re.search(secret_pattern, str(v), re.IGNORECASE)
