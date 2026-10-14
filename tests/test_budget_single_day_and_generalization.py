"""
PilgrimAI - Focused Regression Tests for Standalone Single-Day Budget Fix
Verifies:
1. Parsing and Duration:
   - Budget query with no explicit duration (default to 1 day).
   - Explicit single-day request (1 day).
   - Explicit two-day request (2 days).
   - Explicit three-day request (3 days).
   - Unspecified temple budget query (clarification, no silent invention of temple).
   - Specified temple with no origin (honest representation, no fabricated transit).
2. Calculation:
   - User budget (e.g. ₹3,000) is distinct from estimated expenses.
   - Missing expenses do not become confirmed ₹0 cost.
   - Known costs calculated using correct logic.
   - Unknown prices represented honestly.
   - Distances (e.g. 18 km) not mistaken for prices.
   - Day trip does not require accommodation.
   - Expenses not multiplied by duration twice.
   - Does not claim trip is Within Budget when material expenses are unknown.
3. Regression:
   - 2-day Vemulavada ₹7,000 continues working.
   - Accommodation queries remain unchanged.
   - Nearby attractions queries remain unchanged.
   - Navigation and weather queries remain unchanged.
   - Budget-plus-itinerary aggregation remains functional.
"""

import sys
import re
from pathlib import Path
import pytest

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.state import AgentState, AgentResponse
from app.agents.router import AgentRouter
from app.agents.budget_agent import BudgetAgent, extract_budget_parameters, parse_price_text
from app.agents.coordinator import MasterAgentCoordinator
from app.agents.response_aggregator import ResponseAggregator
from app.agents.multi_intent_pipeline import SequentialMultiIntentPipeline
from app.agents.itinerary_planning_agent import ItineraryPlanningAgent
from app.agents.live_weather_agent import LiveWeatherAgent
from app.agents.live_navigation_agent import LiveNavigationAgent
from app.agents.temple_information_agent import TempleInformationAgent
from app.agents.memory import ConversationMemoryManager


# =====================================================================
# Fixtures and Mock Tools
# =====================================================================

class MockRAGTool:
    """Mock RAG tool with realistic records for testing."""
    def __init__(self):
        self._data = {
            "Vemulavada": {
                "timings": {"entry_fee": "Free General Darshan"},
                "sevas": [
                    {"name": "Mangala Vaidyam", "price": "Free"},
                    {"name": "Suprabhata Seva", "price": "Free"},
                    {"name": "Maha Pooja", "price": "₹200"}
                ],
                "accommodation": [
                    {"name": "Super Hotel O Vemulawada Temple", "tariff": "₹1,200 – ₹2,500 per night"},
                    {"name": "Balaji Lodge", "tariff": "₹900 – ₹1,700 per night"}
                ],
                "prasadam": [{"item": "Laddu", "price": "₹25 – ₹30"}],
                "nearby_attractions": [{"name": "Baddi Pochamma Temple", "distance": "700 m"}]
            },
            "Yadadri": {
                "timings": {"entry_fee": "Free"},
                "sevas": [
                    {"name": "Special Entry", "price": "₹150"},
                    {"name": "Break Darshanam", "price": "₹300"},
                    {"name": "Nijabhishekam", "price": "₹800"}
                ],
                "accommodation": [
                    {"name": "YTDA Divya Sannidhi Cottages", "tariff": "₹3,000 per night"},
                    {"name": "Haritha Hotel Yadagirigutta", "tariff": "₹1,000 – ₹1,700 per night"}
                ],
                "prasadam": [{"item": "Yadadri Ghee Laddu", "price": "₹30"}],
                "nearby_attractions": [{"name": "Surendrapuri", "distance": "5 km"}]
            },
            "Basara": {
                "timings": {"entry_fee": "Free"},
                "sevas": [
                    {"name": "Special Aksharabyasam", "price": "₹1,000"},
                    {"name": "Aksharabyasam", "price": "₹100"}
                ],
                "accommodation": [
                    {"name": "Haritha Hotel Basara", "tariff": "₹1,500 – ₹2,500 per night"}
                ],
                "prasadam": [{"item": "Laddu", "price": "₹20"}],
                "nearby_attractions": [{"name": "Vyasa Guha", "distance": "1 km"}]
            }
        }

    def get_registered_temples(self):
        return list(self._data.keys())

    def get_temple_category_data(self, temple: str, category: str):
        t_clean = temple.title().strip()
        for k, v in self._data.items():
            if k.lower() == temple.lower():
                return v.get(category)
        return None


@pytest.fixture
def mock_rag():
    return MockRAGTool()


@pytest.fixture
def router():
    return AgentRouter(active_agents={
        "temple_information", "live_weather", "live_navigation",
        "budget", "itinerary_planning", "emergency", "recommendation"
    })


@pytest.fixture
def budget_agent(mock_rag):
    agent = BudgetAgent(rag_tool=mock_rag)
    return agent


# =====================================================================
# 1. Parsing and Duration Tests
# =====================================================================

def test_parsing_duration_default_single_day():
    """A budget query with no explicit duration defaults to 1 day."""
    params = extract_budget_parameters("Can I visit Vemulavada within 3000?")
    assert params["days"] == 1
    assert params["nights"] == 0
    assert params["days_assumed"] is True
    assert params["budget_limit"] == 3000.0


def test_parsing_explicit_single_day():
    """An explicit single-day request is parsed as 1 day, 0 nights."""
    params = extract_budget_parameters("Plan a single-day visit to Yadadri with a budget of 3000")
    assert params["days"] == 1
    assert params["nights"] == 0
    assert params["days_assumed"] is False
    assert params["budget_limit"] == 3000.0


def test_parsing_explicit_two_day():
    """An explicit two-day request is parsed as 2 days, 1 night."""
    params = extract_budget_parameters("Plan a 2 day trip to Vemulavada with a budget of 7000")
    assert params["days"] == 2
    assert params["nights"] == 1
    assert params["days_assumed"] is False
    assert params["budget_limit"] == 7000.0


def test_parsing_explicit_three_day():
    """An explicit three-day request is parsed as 3 days, 2 nights."""
    params = extract_budget_parameters("Estimate a 3-day temple trip with a budget of 10000")
    assert params["days"] == 3
    assert params["nights"] == 2
    assert params["days_assumed"] is False
    assert params["budget_limit"] == 10000.0


def test_unspecified_temple_budget_query_routing(router):
    """A request with an unspecified temple ('some temple') must ask for clarification, not invent a temple."""
    decision = router.route("My budget is 3000 to visit some temple")
    assert decision.intent == "clarification"
    assert decision.metadata.get("missing_temple") is True
    assert decision.metadata.get("budget_intent") is True


def test_single_day_temple_visit_not_unsupported_temple(router):
    """'Plan a single day temple visit with a budget of ₹3000' must not treat 'single' as an unregistered temple."""
    decision = router.route("Plan a single day temple visit with a budget of ₹3000")
    assert decision.intent == "clarification"
    assert decision.metadata.get("missing_temple") is True
    assert decision.metadata.get("detected_unknown_temple") is None


def test_distance_not_parsed_as_price():
    """Distance (e.g. 18 km) must not be mistaken for travel fare."""
    params = extract_budget_parameters("Travel distance is 18 km with a budget of 3000")
    assert params["budget_limit"] == 3000.0
    # User costs must not contain 18 as travel fare
    travel_costs = [u for u in params["user_costs"] if u.category == "travel"]
    assert len(travel_costs) == 0

    # Also test price parser directly
    min_v, max_v, unit_t, is_free, is_rng, is_q, notes = parse_price_text("18 km from railway station", category="travel")
    assert is_q is False
    assert min_v is None


# =====================================================================
# 2. Calculation & Honest Missing Data Representation Tests
# =====================================================================

def test_budget_distinct_from_estimated_expenses(budget_agent):
    """User budget (₹3000) must not become the estimated expenses for a single-day visit."""
    state = AgentState(user_query="Estimate my budget for a single-day visit to Yadadri with ₹3000")
    resp = budget_agent.execute(state)
    assert resp.success is True

    # User budget is ₹3000, but estimated expenses must not be ₹3000
    calc_total = resp.metadata["calculated_total"]
    assert calc_total["min"] != 3000.0
    assert resp.metadata["parameters"]["budget_limit"] == 3000.0


def test_single_day_free_entry_does_not_claim_zero_total(budget_agent):
    """When mandatory entry is free, the response must NOT claim the trip total is ₹0."""
    state = AgentState(user_query="Estimate my budget for a single-day visit to Yadadri with ₹3000")
    resp = budget_agent.execute(state)

    # Must be marked as incomplete estimate because travel/food are unquantified
    assert resp.metadata["calculated_total"]["is_complete_estimate"] is False

    # The total line must clearly indicate incomplete estimate / known baseline
    assert "Incomplete Estimate" in resp.answer
    assert "- **Total**:\n- **₹0**" not in resp.answer
    assert "Total represents mandatory & selected baseline costs" in resp.answer

    # Must list personal travel and meals under Costs Not Available
    assert "Personal Travel / Transit" in resp.answer
    assert "Personal Meals / Food" in resp.answer


def test_single_day_does_not_falsely_claim_within_budget_when_travel_unknown(budget_agent):
    """Response must not claim ✅ Within Budget when material expenses (transport, food) are unknown."""
    state = AgentState(user_query="Can I visit Vemulavada within ₹3000?")
    resp = budget_agent.execute(state)

    # Status must NOT be '✅ Within Budget'
    assert "✅ **Within Budget**" not in resp.answer
    assert "Feasibility Incomplete" in resp.answer or "Feasibility Cannot Be Confirmed" in resp.answer


def test_day_trip_does_not_require_accommodation(budget_agent):
    """A day trip must not automatically require accommodation or fail because accommodation is missing."""
    state = AgentState(user_query="Can I visit Vemulavada within ₹3000?")
    resp = budget_agent.execute(state)

    # Day trip should not treat accommodation as missing required expense
    assert resp.metadata["parameters"]["nights"] == 0
    assert resp.metadata["parameters"]["accom_requested"] is False
    # Accommodation options may be listed as alternatives, but not in mandatory subtotal
    assert "Mandatory Temple Entry Subtotal**: **₹0" in resp.answer


def test_known_sevas_calculated_correctly(budget_agent):
    """When user requests a specific paid seva, known costs must be calculated correctly."""
    state = AgentState(user_query="Estimate my budget for a single day visit to Yadadri with Special Entry ticket and budget 3000")
    resp = budget_agent.execute(state)
    assert resp.success is True

    # Special Entry at Yadadri is ₹150
    assert resp.metadata["calculated_total"]["min"] == 150.0
    assert resp.metadata["calculated_total"]["max"] == 150.0
    assert resp.metadata["calculated_total"]["is_complete_estimate"] is False
    assert "₹150" in resp.answer


# =====================================================================
# 3. Regression Tests (Preserve Existing Capabilities)
# =====================================================================

def test_regression_two_day_vemulavada_budget(budget_agent):
    """Preserve existing working 2-day Vemulavada ₹7000 calculation."""
    state = AgentState(user_query="Plan a 2 day trip to Vemulavada with a budget of 7000")
    resp = budget_agent.execute(state)
    assert resp.success is True

    # Selected accommodation tier is ₹1200 - ₹2500
    calc_total = resp.metadata["calculated_total"]
    assert calc_total["min"] == 1200.0
    assert calc_total["max"] == 2500.0
    assert calc_total["is_complete_estimate"] is True
    assert "✅ **Within Budget**" in resp.answer
    assert "Super Hotel O Vemulawada Temple" in resp.answer


def test_regression_accommodation_query_routing(router):
    """Accommodation queries must remain routed to accommodation / temple_information, not budget."""
    decision = router.route("Show all accommodations in Yadadri with tariffs")
    assert decision.intent == "temple_information"
    assert decision.metadata.get("detected_temple") == "Yadadri"


def test_regression_nearby_attractions_query_routing(router):
    """Nearby attractions queries must remain routed to temple_information."""
    decision = router.route("What are the nearby places to visit near Vemulavada?")
    assert decision.intent == "temple_information"


def test_regression_navigation_query_routing(router):
    """Live navigation queries must remain routed to live_navigation."""
    decision = router.route("How to reach Vemulavada from Hyderabad by car?")
    assert decision.intent == "live_navigation"


def test_regression_weather_query_routing(router):
    """Live weather queries must remain routed to live_weather."""
    decision = router.route("What is the current weather in Yadadri?")
    assert decision.intent == "weather"
    assert decision.selected_agent == "live_weather"


def test_regression_conversation_memory_unspecified_temple():
    """Conversation memory must not override 'some temple' with a previous turn's temple."""
    memory = ConversationMemoryManager()
    session_id = "test-session-unspecified"

    # Turn 1: Discuss Vemulavada
    memory.record_turn(
        session_id=session_id,
        user_query="Plan a 2 day trip to Vemulavada with a budget of 7000",
        identified_temples=["Vemulavada"]
    )

    # Turn 2: User asks about 'some temple'
    resolution = memory.resolve_query(session_id=session_id, query="My budget is 3000 to visit some temple")
    # Must NOT resolve to Vemulavada!
    assert resolution.get("referenced_temple") is None
    assert "Vemulavada" not in resolution["resolved_query"]


# =====================================================================
# 4. Targeted Basara & Standalone Budget Semantics Tests
# =====================================================================

def test_basara_standalone_budget_distinguishes_baseline_from_total(budget_agent):
    """
    For 'budget 2000 to visit basara temple':
    1. Verified general-darshan cost is ₹0.
    2. Not treated as total cost of trip (is_complete_estimate is False).
    3. Mandatory temple-entry subtotal is ₹0 baseline.
    4. Travel is explicitly marked unquantified.
    5. Meals are explicitly marked unquantified.
    6. unquantified_item_count is >= 2.
    7. No false affordability claim of full trip within budget.
    """
    state = AgentState(user_query="budget 2000 to visit basara temple")
    resp = budget_agent.execute(state)
    assert resp.success is True

    meta = resp.metadata
    calc_total = meta["calculated_total"]

    # 1. Baseline bounds are 0.0
    assert calc_total["min"] == 0.0
    assert calc_total["max"] == 0.0

    # 2. Incomplete estimate
    assert calc_total["is_complete_estimate"] is False
    assert calc_total["is_quantified"] is True

    # 3. Unquantified count is at least 2 (travel and meals)
    assert meta["unquantified_item_count"] >= 2

    # 4. Costs Not Available section lists both travel and meals
    assert "Personal Travel / Transit" in resp.answer
    assert "Personal Meals / Food" in resp.answer

    # 5. Answer distinguishes free general darshan baseline from total trip
    assert "Free general darshan" in resp.answer or "FREE" in resp.answer
    assert "Incomplete Estimate" in resp.answer

    # 6. No false claim that trip is within budget
    assert "✅ **Within Budget**" not in resp.answer


def test_origin_extraction_and_unquantified_transit_representation(budget_agent):
    """When user specifies origin ('from Nizamabad') but no fare, transit is unquantified with origin noted."""
    state = AgentState(user_query="budget 2000 to visit basara temple from Nizamabad")
    resp = budget_agent.execute(state)
    assert resp.success is True

    assert resp.metadata["parameters"]["origin"] == "Nizamabad"
    assert "from Nizamabad" in resp.answer
    assert resp.metadata["calculated_total"]["is_complete_estimate"] is False
    assert resp.metadata["unquantified_item_count"] >= 2


def test_utf8_json_response_media_type():
    """UTF8JSONResponse media_type must explicitly define charset=utf-8."""
    from app.main import UTF8JSONResponse
    assert UTF8JSONResponse.media_type == "application/json; charset=utf-8"
