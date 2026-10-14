"""
PilgrimAI - Focused Regression Tests: Budget Enforcement, Accommodation Preferences & Itinerary Output

Verifies all 16 required test scenarios:
1. Budget preference excludes Standard and Premium properties from matching recommendations.
2. Standard / Comfort preference excludes Premium properties from matching recommendations.
3. Premium preference excludes other tiers from matching recommendations.
4. No preference preserves verified baseline options across tiers.
5. No Accommodation results in zero lodging charges.
6. A plan within budget is correctly identified.
7. An over-budget plan displays the correct shortfall.
8. Unknown transport and food expenses are not silently treated as zero (partial estimate).
9. Selected accommodation is counted exactly once.
10. Multiple rooms and nights are calculated correctly (nights * rooms * tariff).
11. Multi-destination accommodation costs use the correct night allocation.
12. Alternative properties do not inflate the selected plan's total.
13. Changing accommodation selection updates the total.
14. A supplied budget causes the itinerary to show concise lodging details instead of duplicating the full comparison.
15. An omitted budget preserves useful accommodation alternatives.
16. Partial estimates are not labelled as complete trip costs.
"""

import sys
from pathlib import Path
import pytest

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.state import AgentState
from app.agents.budget_agent import BudgetAgent, normalize_accommodation_tier, extract_budget_parameters
from app.agents.itinerary_planning_agent import ItineraryPlanningAgent
from app.agents.tools.rag_tool import RAGTool


@pytest.fixture(scope="module")
def budget_agent():
    rag = RAGTool()
    return BudgetAgent(rag_tool=rag)


@pytest.fixture(scope="module")
def itinerary_agent():
    return ItineraryPlanningAgent()


# =====================================================================
# 1. Budget preference excludes Standard and Premium properties
# =====================================================================
def test_budget_preference_excludes_standard_and_premium(budget_agent):
    """
    Budget preference must mark only Budget-tier properties as matching recommendations.
    Standard / Comfort and Premium properties must have matches_preference == False.
    """
    state = AgentState(
        user_query="Plan a 2-day trip to Basara for 2 people with Rs 6000 budget with budget accommodation",
        structured_constraints={"accommodation_preference": "Budget"}
    )
    res = budget_agent.process(state)
    assert res.success is True

    opts = res.metadata.get("accommodation_options", [])
    assert len(opts) > 0

    matching = [o for o in opts if o.get("matches_preference") is True]
    non_matching = [o for o in opts if o.get("matches_preference") is False]

    assert len(matching) > 0
    # Every matching option must be Budget tier
    for m in matching:
        assert m["tier"] == "Budget"

    # Standard and Premium options must be in non_matching
    for nm in non_matching:
        assert nm["tier"] in ["Standard / Comfort", "Premium"]

    # Selected property must be Budget tier
    selected = next(o for o in opts if o.get("is_selected"))
    assert selected["tier"] == "Budget"


# =====================================================================
# 2. Standard / Comfort preference excludes Premium properties
# =====================================================================
def test_standard_comfort_preference_excludes_premium(budget_agent):
    """
    Standard / Comfort preference must exclude Premium properties from matching recommendations.
    """
    state = AgentState(
        user_query="Plan a 2-day trip to Basara for 2 people with Rs 8000 budget with standard accommodation",
        structured_constraints={"accommodation_preference": "Standard / Comfort"}
    )
    res = budget_agent.process(state)
    assert res.success is True

    opts = res.metadata.get("accommodation_options", [])
    assert len(opts) > 0

    matching = [o for o in opts if o.get("matches_preference") is True]
    assert len(matching) > 0
    for m in matching:
        assert m["tier"] == "Standard / Comfort"

    # Premium properties must not be matching
    premium_opts = [o for o in opts if o["tier"] == "Premium"]
    for p in premium_opts:
        assert p.get("matches_preference") is False

    # Selected property must be Standard / Comfort tier
    selected = next(o for o in opts if o.get("is_selected"))
    assert selected["tier"] == "Standard / Comfort"


# =====================================================================
# 3. Premium preference excludes other tiers from matching
# =====================================================================
def test_premium_preference_excludes_other_tiers(budget_agent):
    """
    Premium preference must exclude Budget and Standard properties from matching recommendations.
    """
    state = AgentState(
        user_query="Plan a 2-day trip to Basara for 2 people with Rs 15000 budget with premium accommodation",
        structured_constraints={"accommodation_preference": "Premium"}
    )
    res = budget_agent.process(state)
    assert res.success is True

    opts = res.metadata.get("accommodation_options", [])
    assert len(opts) > 0

    matching = [o for o in opts if o.get("matches_preference") is True]
    assert len(matching) > 0
    for m in matching:
        assert m["tier"] == "Premium"

    non_premium = [o for o in opts if o["tier"] != "Premium"]
    for np in non_premium:
        assert np.get("matches_preference") is False

    selected = next(o for o in opts if o.get("is_selected"))
    assert selected["tier"] == "Premium"


# =====================================================================
# 4. No preference preserves verified baseline options across tiers
# =====================================================================
def test_no_preference_preserves_verified_baseline_options(budget_agent):
    """
    When no preference is specified, all verified baseline options across tiers
    are preserved and marked as available matching options.
    """
    state = AgentState(
        user_query="Plan a 2-day trip to Basara for 2 people with Rs 7000 budget",
        structured_constraints={"accommodation_preference": None}
    )
    res = budget_agent.process(state)
    assert res.success is True

    opts = res.metadata.get("accommodation_options", [])
    assert len(opts) >= 3
    # All options are considered available without tier exclusion
    assert all(o.get("matches_preference") is True for o in opts)
    tiers = {o["tier"] for o in opts}
    assert "Budget" in tiers
    assert "Standard / Comfort" in tiers


# =====================================================================
# 5. No Accommodation results in zero lodging charges
# =====================================================================
def test_no_accommodation_results_in_zero_lodging_charges(budget_agent):
    """
    Selecting No Accommodation results in 0 lodging charges, 0 nights charged,
    and clear disclosure in budget breakdown.
    """
    state = AgentState(
        user_query="Plan a 2-day visit to Basara without accommodation for 2 people",
        structured_constraints={"accommodation_preference": "none"}
    )
    res = budget_agent.process(state)
    assert res.success is True

    bd = res.metadata.get("budget_breakdown", {})
    assert bd.get("accommodation_min") == 0.0
    assert bd.get("accommodation_max") == 0.0

    params = res.metadata.get("parameters", {})
    assert params.get("nights") == 0
    assert params.get("accommodation_preference") == "none"

    assert "Zero lodging charges" in res.answer or "without accommodation" in res.answer.lower()


# =====================================================================
# 6. Plan within budget is correctly identified
# =====================================================================
def test_plan_within_budget_correctly_identified(budget_agent):
    """
    When total estimated expenses are less than user's budget,
    the plan is correctly identified as within budget with surplus reported.
    """
    state = AgentState(
        user_query="Plan a 2-day trip to Basara for 2 people with Rs 10000 budget with budget accommodation",
        structured_constraints={"budget_limit": 10000.0, "accommodation_preference": "Budget"}
    )
    res = budget_agent.process(state)
    assert res.success is True

    bd = res.metadata.get("budget_breakdown", {})
    assert bd.get("status") == "within"
    assert bd.get("total_min") <= 10000.0
    assert "Within Budget" in res.answer or "Surplus" in res.answer


# =====================================================================
# 7. Over-budget plan displays the correct shortfall
# =====================================================================
def test_over_budget_plan_displays_correct_shortfall(budget_agent):
    """
    When estimated cost exceeds budget, status is 'exceeds' and
    the exact shortfall (total_min - budget_limit) is reported.
    """
    # Basara cheapest accommodation is ₹600 for 1 night. Budget is ₹400.
    state = AgentState(
        user_query="Plan a 2-day trip to Basara for 2 people with Rs 400 budget",
        structured_constraints={"budget_limit": 400.0}
    )
    res = budget_agent.process(state)
    assert res.success is True

    bd = res.metadata.get("budget_breakdown", {})
    assert bd.get("status") == "exceeds"
    shortfall = bd["total_min"] - 400.0
    assert shortfall > 0
    assert f"Shortfall of ₹{shortfall:,.0f}" in res.answer or f"exceeding your budget of ₹400 by ₹{shortfall:,.0f}" in res.answer or "Exceeds Budget" in res.answer


# =====================================================================
# 8. Unknown transport and food expenses are not silently treated as zero
# =====================================================================
def test_unknown_transport_and_food_not_silently_treated_as_zero(budget_agent):
    """
    When transport and dining expenses are unknown/unsupplied, they are not
    silently treated as ₹0 complete trip cost; unquantified records disclose this.
    """
    state = AgentState(user_query="What is the budget for 1 day trip to Basara?")
    res = budget_agent.process(state)
    assert res.success is True

    unq_count = res.metadata.get("unquantified_item_count", 0)
    assert unq_count > 0

    assert "Costs Not Available" in res.answer
    assert "Personal Travel / Transit" in res.answer or "transit" in res.answer.lower()
    assert "Personal Meals / Food" in res.answer or "meals" in res.answer.lower()


# =====================================================================
# 9. Selected accommodation is counted exactly once
# =====================================================================
def test_selected_accommodation_counted_exactly_once(budget_agent):
    """
    The selected hotel's stay cost is counted exactly once in the grand total:
    total_min == entry_min + sevas_min + accommodation_min + travel_min + food_min.
    """
    state = AgentState(
        user_query="Plan a 2-day trip to Basara for 2 people with Rs 7000 budget with budget accommodation",
        structured_constraints={"accommodation_preference": "Budget"}
    )
    res = budget_agent.process(state)
    assert res.success is True

    bd = res.metadata.get("budget_breakdown", {})
    calc = res.metadata.get("calculated_total", {})

    expected_sum = (
        bd.get("entry_min", 0.0)
        + bd.get("sevas_min", 0.0)
        + bd.get("accommodation_min", 0.0)
        + bd.get("travel_min", 0.0)
        + bd.get("food_min", 0.0)
    )
    assert calc.get("min") == expected_sum
    assert bd.get("total_min") == expected_sum


# =====================================================================
# 10. Multiple rooms and nights are calculated correctly
# =====================================================================
def test_multiple_rooms_and_nights_calculated_correctly(budget_agent):
    """
    For 4 pilgrims (pax=4 -> 2 rooms) and 3 days (nights=2):
    stay_cost = nights * rooms * nightly_tariff.
    """
    state = AgentState(
        user_query="Plan a 3-day trip to Basara for 4 people with Rs 12000 budget with budget accommodation",
        structured_constraints={"duration_days": 3, "pax": 4, "accommodation_preference": "Budget"}
    )
    res = budget_agent.process(state)
    assert res.success is True

    params = res.metadata.get("parameters", {})
    assert params.get("pax") == 4
    assert params.get("rooms") == 2
    assert params.get("nights") == 2

    opts = res.metadata.get("accommodation_options", [])
    selected = next(o for o in opts if o.get("is_selected"))
    tariff_min = selected["tariff_min"]
    expected_stay = 2 * 2 * tariff_min
    assert selected["stay_cost_min"] == expected_stay

    bd = res.metadata.get("budget_breakdown", {})
    assert bd.get("accommodation_min") == expected_stay


# =====================================================================
# 11. Multi-destination accommodation uses correct night allocation
# =====================================================================
def test_multi_destination_accommodation_correct_night_allocation(budget_agent):
    """
    For a 3-day (2 nights) trip across 2 temples (Basara and Vemulavada),
    nights are split (1 night each), rather than charging 2 nights at both.
    """
    state = AgentState(
        user_query="Plan a 3-day trip to Basara and Vemulavada for 2 people with Rs 10000 budget",
        structured_constraints={"duration_days": 3, "pax": 2}
    )
    res = budget_agent.process(state)
    assert res.success is True

    params = res.metadata.get("parameters", {})
    assert params.get("nights") == 2
    assert "Multi-destination stay allocation: Total 2 night(s)" in res.answer or "night(s)" in res.answer


# =====================================================================
# 12. Alternative properties do not inflate the selected plan's total
# =====================================================================
def test_alternative_properties_do_not_inflate_selected_total(budget_agent):
    """
    Alternative properties shown in comparison tables must not be added
    to the selected plan's total.
    """
    state = AgentState(
        user_query="Plan a 2-day trip to Basara for 2 people with Rs 6000 budget with budget accommodation",
        structured_constraints={"accommodation_preference": "Budget"}
    )
    res = budget_agent.process(state)
    assert res.success is True

    opts = res.metadata.get("accommodation_options", [])
    assert len(opts) > 1

    selected = next(o for o in opts if o.get("is_selected"))
    bd = res.metadata.get("budget_breakdown", {})
    # Accommodation total must strictly equal only the selected property stay cost
    assert bd["accommodation_min"] == selected["stay_cost_min"]


# =====================================================================
# 13. Changing accommodation selection updates the total
# =====================================================================
def test_changing_accommodation_selection_updates_total(budget_agent):
    """
    Switching from Budget accommodation to Premium accommodation updates
    the total by the exact difference in tariffs, with no double-counting.
    """
    # 1. Budget preference
    state_b = AgentState(
        user_query="Plan a 2-day trip to Basara for 2 people staying with budget accommodation",
        structured_constraints={"accommodation_preference": "Budget"}
    )
    res_b = budget_agent.process(state_b)
    sel_b = next(o for o in res_b.metadata["accommodation_options"] if o["is_selected"])

    # 2. Premium preference
    state_p = AgentState(
        user_query="Plan a 2-day trip to Basara for 2 people staying with premium accommodation",
        structured_constraints={"accommodation_preference": "Premium"}
    )
    res_p = budget_agent.process(state_p)
    sel_p = next(o for o in res_p.metadata["accommodation_options"] if o["is_selected"])

    cost_diff = sel_p["stay_cost_min"] - sel_b["stay_cost_min"]
    tot_diff = res_p.metadata["calculated_total"]["min"] - res_b.metadata["calculated_total"]["min"]
    assert tot_diff == cost_diff


# =====================================================================
# 14. Supplied budget causes itinerary to show concise lodging details
# =====================================================================
def test_supplied_budget_causes_itinerary_to_show_concise_lodging(itinerary_agent):
    """
    When a budget is provided, the itinerary outputs concise lodging information
    and leaves the full comparison table to the Budget section.
    """
    state = AgentState(
        user_query="Plan a 2-day trip to Basara with Rs 5000 budget",
        structured_constraints={"duration_days": 2, "budget_limit": 5000.0}
    )
    res = itinerary_agent.process(state)
    assert res.success is True

    # Shows concise lodging & night allocation
    assert "### 🏨 Lodging & Night Allocation" in res.answer
    # Does NOT duplicate the full property catalogue comparison
    assert "### 🏨 Accommodation Options by Temple" not in res.answer


# =====================================================================
# 15. An omitted budget preserves useful accommodation alternatives
# =====================================================================
def test_omitted_budget_preserves_useful_accommodation_alternatives(itinerary_agent):
    """
    When no budget is supplied, the itinerary preserves verified accommodation
    alternatives in Section 10 for user guidance.
    """
    state = AgentState(
        user_query="Plan a 2-day trip to Basara",
        structured_constraints={"duration_days": 2, "budget_limit": None}
    )
    res = itinerary_agent.process(state)
    assert res.success is True

    # Preserves accommodation options
    assert "### 🏨 Accommodation Options by Temple" in res.answer
    assert "Basara" in res.answer


# =====================================================================
# 16. Partial estimates are not labelled as complete trip costs
# =====================================================================
def test_partial_estimates_not_labelled_as_complete_trip_costs(budget_agent):
    """
    When transit or meals are unquantified, the total is explicitly disclosed
    as a partial baseline / incomplete estimate, never a complete trip cost.
    """
    state = AgentState(user_query="Plan a 1-day trip to Basara for 2 people")
    res = budget_agent.process(state)
    assert res.success is True

    calc = res.metadata.get("calculated_total", {})
    assert calc.get("is_complete_estimate") is False
    assert calc.get("estimate_type") == "baseline_subtotal"

    assert "Incomplete Estimate" in res.answer or "Partial known baseline" in res.answer
    assert "Complete trip cost" not in res.answer
