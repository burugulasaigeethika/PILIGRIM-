"""
PilgrimAI - Unit & Regression Tests: Budget-Driven Accommodation Selection
Verifies that:
1. Changing the user's budget dynamically alters the recommended accommodation options and trip total.
2. Low budget selects Budget tier, standard budget selects Standard tier, and high budget selects Premium tier.
3. Budget below minimum accommodation triggers transparent shortfall reporting.
4. Room sharing calculation assigns rooms based on group size (pax >= 3 -> (pax + 1) // 2).
5. User's explicit property preference overrides default budget tier.
6. Structured response metadata includes 'accommodation_options' and 'budget_breakdown'.
7. Multi-turn budget follow-up preserves previous turn's duration, pax, and origin context.
"""

import sys
from pathlib import Path
import pytest

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.state import AgentState, AgentResponse
from app.agents.budget_agent import BudgetAgent, extract_budget_parameters
from app.agents.memory import ConversationMemoryManager
from app.agents.tools.rag_tool import RAGTool


@pytest.fixture
def budget_agent():
    rag = RAGTool()
    return BudgetAgent(rag_tool=rag)


def test_budget_scaling_changes_selected_accommodation(budget_agent):
    """
    Changing budget from ₹2,000 to ₹7,000 to ₹18,000 at Basara
    must change the recommended accommodation option and total cost.
    """
    # 1. Low budget: ₹2,000 for 2 days
    state_low = AgentState(user_query="Plan a 2-day trip to Basara for 2 people with Rs 2000 budget")
    res_low = budget_agent.process(state_low)
    assert res_low.success is True
    # Should pick affordable Budget tier (100 TTD Guest Houses, starts at ₹600)
    assert "100 TTD Guest Houses" in res_low.answer
    assert res_low.metadata["calculated_total"]["min"] <= 2000.0

    # 2. Standard budget: ₹7,000 for 2 days
    state_std = AgentState(user_query="Plan a 2-day trip to Basara for 2 people with Rs 7000 budget")
    res_std = budget_agent.process(state_std)
    assert res_std.success is True
    # Should pick Standard tier (Haritha Hotel Basara, starts at ₹1500)
    assert "Haritha Hotel Basara" in res_std.answer or "Nakshatra Inn" in res_std.answer
    assert res_std.metadata["calculated_total"]["min"] >= 1500.0

    # 3. Premium budget: ₹18,000 for 2 days
    state_prem = AgentState(user_query="Plan a 2-day trip to Basara for 2 people with Rs 18000 budget")
    res_prem = budget_agent.process(state_prem)
    assert res_prem.success is True
    # Should pick highest comfort private property (Laxmi Grand Inn)
    assert "Laxmi Grand Inn" in res_prem.answer
    assert res_prem.metadata["calculated_total"]["min"] >= 1600.0


def test_shortfall_when_budget_below_minimum(budget_agent):
    """
    When budget is below the minimum available accommodation,
    BudgetAgent chooses lowest option and transparently reports shortfall.
    """
    # Basara cheapest accommodation is ₹600 (100 TTD Guest Houses). Budget is ₹400.
    state = AgentState(user_query="Plan a 2-day trip to Basara for 2 people with Rs 400 budget")
    res = budget_agent.process(state)
    assert res.success is True
    # Must report that budget is exceeded
    assert "Exceeds Budget" in res.answer or "Shortfall" in res.answer or "exceeds" in str(res.metadata.get("budget_breakdown", {}).get("status"))
    assert res.metadata["calculated_total"]["min"] >= 600.0


def test_group_size_room_sharing(budget_agent):
    """
    Group size of 4 devotees defaults to 2 rooms ((4 + 1) // 2 = 2) with clear assumptions.
    """
    state = AgentState(user_query="Plan a 2-day trip to Basara for 4 people with Rs 10000 budget")
    res = budget_agent.process(state)
    assert res.success is True
    params = res.metadata["parameters"]
    assert params["pax"] == 4
    assert params["rooms"] == 2
    assert "2 room(s)" in res.answer or "Rooms: 2" in res.answer


def test_explicit_property_preference_overrides_budget(budget_agent):
    """
    User's explicit hotel preference (e.g. Laxmi Grand Inn) is respected even with a modest budget.
    """
    state = AgentState(user_query="Plan a 2-day trip to Basara with Rs 4000 budget staying at Laxmi Grand Inn")
    res = budget_agent.process(state)
    assert res.success is True
    assert "Laxmi Grand Inn" in res.answer


def test_metadata_accommodation_options_and_breakdown(budget_agent):
    """
    Response metadata must include structured accommodation_options and budget_breakdown.
    """
    state = AgentState(user_query="Plan a 2-day trip to Basara for 2 people with Rs 6000 budget")
    res = budget_agent.process(state)
    assert res.success is True
    meta = res.metadata

    # accommodation_options verification
    assert "accommodation_options" in meta
    opts = meta["accommodation_options"]
    assert len(opts) >= 3
    # Check structure
    sample = opts[0]
    assert "name" in sample
    assert "property_type" in sample
    assert "distance" in sample
    assert "tier" in sample
    assert "tariff_min" in sample
    assert "stay_cost_min" in sample
    assert "is_selected" in sample
    assert any(o["is_selected"] for o in opts)

    # budget_breakdown verification
    assert "budget_breakdown" in meta
    breakdown = meta["budget_breakdown"]
    assert "entry_min" in breakdown
    assert "accommodation_min" in breakdown
    assert "total_min" in breakdown
    assert "budget_limit" in breakdown
    assert breakdown["budget_limit"] == 6000.0


def test_multiturn_budget_followup_preserves_parameters():
    """
    ConversationMemoryManager preserves duration, pax, and origin when user changes budget in a follow-up.
    """
    memory = ConversationMemoryManager()
    session_id = "test_multiturn_budget_sess_1"

    # Turn 1: 2 days, 4 people, Basara, 5000 budget
    res1 = memory.resolve_query(session_id, "Plan a 2-day budget trip for 4 people to Basara with 5000 budget")
    memory.add_turn(
        session_id=session_id,
        user_query="Plan a 2-day budget trip for 4 people to Basara with 5000 budget",
        resolved_query=res1["resolved_query"],
        identified_temples=["Basara"],
        metadata={"parameters": {"days": 2, "nights": 1, "pax": 4, "rooms": 2, "budget_limit": 5000.0}}
    )

    # Turn 2: Follow-up changing only budget
    res2 = memory.resolve_query(session_id, "What if my budget is 8000?")
    resolved_q = res2["resolved_query"]
    assert "Basara" in resolved_q
    # Duration and group size must be preserved
    assert "2 days" in resolved_q or "days" in resolved_q
    assert "4 people" in resolved_q or "people" in resolved_q

    # Extract parameters from the resolved query
    params = extract_budget_parameters(resolved_q)
    assert params["days"] == 2
    assert params["nights"] == 1
    assert params["pax"] == 4
    assert params["rooms"] == 2
    assert params["budget_limit"] == 8000.0
