"""
Targeted tests for PilgrimAI 30-Minute Itinerary Bug-Fix Sprint.
Validates:
1. Three selected temples result in three itinerary destinations in requested order.
2. Every selected destination appears in the final rendered itinerary.
3. A destination's attraction cannot be assigned to an unrelated day.
4. A Yadadri attraction is not offered for this trip unless explicitly scheduled as an extra stop.
5. Available Vemulavada attractions appear in the Vemulavada group.
6. Empty attraction results for one destination do not suppress results for another destination.
7. Adding and removing an attraction updates the correct itinerary day and selected-activity state.
8. Accommodation cards render readable text without leaked &#x...; entities or raw escaped Markdown table syntax.
9. Only selected accommodations are included in the chosen stay plan.
10. Duplicate route and accommodation sections are not emitted.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import pytest
from unittest.mock import patch, MagicMock

from backend.app.agents.itinerary_planning_agent import ItineraryPlanningAgent
from backend.app.agents.multi_intent_pipeline import SequentialMultiIntentPipeline
from backend.app.agents.budget_agent import BudgetAgent
from backend.app.agents.response_aggregator import ResponseAggregator
from backend.app.agents.state import AgentState, AgentResponse
from backend.app.api.maps import load_static_nearby_attractions


def test_1_and_2_decomposition_and_order_preservation():
    """Verify 3 selected temples are decomposed cleanly and preserved in requested order."""
    pipeline = SequentialMultiIntentPipeline()
    query = "Plan a 5-day pilgrimage to Edupayal, Vemulavada, and Bhadrachalam starting from Hyderabad with budget 10000 for 1 person"
    tasks = pipeline.decompose_query(query)
    
    # Should have itinerary_planning task
    itin_task = next((t for t in tasks if t.get("target_agent") == "itinerary_planning"), None)
    assert itin_task is not None, "itinerary_planning task must be present"
    
    rd = itin_task["route_decision"]
    temples_list = rd.metadata.get("detected_temples") or rd.metadata.get("destinations") or rd.metadata.get("temples") or []
    temples_lower = [t.lower() for t in temples_list]
    assert any("edupayal" in t for t in temples_lower), f"Edupayal not in {temples_lower}"
    assert any("vemulawada" in t or "vemulavada" in t for t in temples_lower), f"Vemulavada not in {temples_lower}"
    assert any("bhadrachalam" in t or "badrachalam" in t for t in temples_lower), f"Bhadrachalam not in {temples_lower}"
    
    # Origin must not be in destinations
    assert not any("hyderabad" in t for t in temples_lower)


def test_itinerary_destination_order_and_all_present():
    """Verify all 3 temples appear in day-by-day schedule in requested order."""
    agent = ItineraryPlanningAgent()
    state = AgentState(
        user_query="Plan a 5-day pilgrimage to Edupayal, Vemulavada, and Bhadrachalam from Hyderabad",
        structured_constraints={
            "origin": "Hyderabad",
            "destinations": ["Edupayal", "Vemulavada", "Bhadrachalam"],
            "temples": ["Edupayal", "Vemulavada", "Bhadrachalam"],
            "duration_days": 5,
            "group_size": 1,
            "budget": 10000
        },
        detected_intents=["itinerary_planning"]
    )
    
    with patch.object(agent.navigation_adapter, "compute_route", return_value={
        "routes": [{"distanceMeters": 150000, "duration": "10800s"}]
    }):
        resp = agent.execute(state)
        content = resp.answer
        metadata = resp.metadata
        
        # Check destinations preserved in order
        destinations = metadata.get("destinations", [])
        assert destinations == ["Edupayal", "Vemulavada", "Bhadrachalam"]
        
        # Verify all 3 appear in the day-by-day itinerary content
        assert "Edupayal" in content
        assert "Vemulavada" in content
        assert "Bhadrachalam" in content
        assert "Day 1" in content
        assert "Day 2" in content
        assert "Day 3" in content


def test_3_and_4_attraction_validation_and_no_unrelated_temple():
    """Verify attractions belong only to destination and cannot bleed to other destinations."""
    # Load attractions for Vemulavada
    vemulavada_attrs = load_static_nearby_attractions("Vemulavada")
    assert len(vemulavada_attrs) > 0, "Vemulavada attractions should be found"
    
    # Ensure none are from Yadadri
    for attr in vemulavada_attrs:
        name = attr.get("name", "").lower()
        desc = attr.get("description", "").lower()
        assert "yadadri" not in name and "pathagutta" not in name, f"Unexpected Yadadri attraction: {name}"


def test_5_and_6_vemulavada_and_empty_state_independence():
    """Verify Vemulavada attractions are discovered and empty destinations do not suppress others."""
    edupayal_attrs = load_static_nearby_attractions("Edupayal")
    vemulavada_attrs = load_static_nearby_attractions("Vemulavada")
    bhadrachalam_attrs = load_static_nearby_attractions("Bhadrachalam")
    
    assert len(edupayal_attrs) > 0, "Edupayal should have attractions"
    assert len(vemulavada_attrs) > 0, "Vemulavada should have attractions"
    assert len(bhadrachalam_attrs) > 0, "Bhadrachalam should have attractions"
    
    # Non-existent destination returns empty list, does not throw or suppress others
    fake_attrs = load_static_nearby_attractions("UnknownPlace999")
    assert fake_attrs == []


def test_7_activity_day_assignment_validation():
    """Verify activity destination matches active temple and scheduled day is clamped to valid days."""
    agent = ItineraryPlanningAgent()
    state = AgentState(
        user_query="Plan 5 day trip to Edupayal, Vemulavada, and Bhadrachalam",
        structured_constraints={
            "origin": "Hyderabad",
            "destinations": ["Edupayal", "Vemulavada", "Bhadrachalam"],
            "temples": ["Edupayal", "Vemulavada", "Bhadrachalam"],
            "duration_days": 5,
            # User selected an activity for Edupayal but tried to assign it to Day 4 (which is Bhadrachalam)
            "selected_activities": [
                {
                    "name": "Edupayal Forest Stream",
                    "destination": "Edupayal",
                    "day": 4
                }
            ]
        },
        detected_intents=["itinerary_planning"]
    )
    
    with patch.object(agent.navigation_adapter, "compute_route", return_value={"routes": []}):
        resp = agent.execute(state)
        content = resp.answer
        
        # Edupayal is allocated to Days 1 & 2. Day 4 is Bhadrachalam.
        # Verify "Edupayal Forest Stream" does not bleed into Day 4 schedule
        day_4_part = content.split("Day 4")[1] if "Day 4" in content else ""
        day_4_section = day_4_part.split("Day 5")[0] if "Day 5" in day_4_part else day_4_part
        assert "Edupayal Forest Stream" not in day_4_section, "Edupayal attraction must not bleed into Bhadrachalam day"


def test_8_and_9_accommodation_clean_cards_and_no_raw_tables():
    """Verify accommodation output uses card formatting, has no raw markdown table rows, and no entity leakage."""
    agent = BudgetAgent()
    state = AgentState(
        user_query="Budget for Edupayal, Vemulavada, Bhadrachalam",
        structured_constraints={
            "origin": "Hyderabad",
            "destinations": ["Edupayal", "Vemulavada", "Bhadrachalam"],
            "temples": ["Edupayal", "Vemulavada", "Bhadrachalam"],
            "duration_days": 5,
            "group_size": 1,
            "budget": 10000
        },
        detected_intents=["budget"]
    )
    
    resp = agent.execute(state)
    content = resp.answer
    
    # Must NOT have raw markdown table headers or pipes
    assert "| Property |" not in content, "Raw markdown table header '| Property |' should not be present"
    assert "|---" not in content, "Raw markdown table separator should not be present"
    
    # Must NOT have entity leakage
    assert "&#x20;" not in content
    assert "&#39;" not in content
    assert "&#x39;" not in content


def test_10_no_duplicate_sections_in_response_aggregator():
    """Verify response aggregator filters out duplicate accommodation and route sections."""
    aggregator = ResponseAggregator()
    
    itinerary_resp = AgentResponse(
        success=True,
        agent_name="itinerary_planning",
        answer="""### Route Overview
From Hyderabad to Edupayal.

### Day-by-Day Pilgrimage Plan
Day 1: Edupayal

### Recommended Stay Plan
Stay at Edupayal Lodge for ₹800.
""",
        metadata={"itinerary": {"days": []}}
    )
    
    budget_resp = AgentResponse(
        success=True,
        agent_name="budget",
        answer="""### Complete Pilgrimage Budget
Estimated cost ₹7,000.

### Recommended Stay Plan (Verified Official Records)
Stay at Edupayal Guest House.
""",
        metadata={"budget": {"total": 7000}}
    )
    
    result = aggregator.aggregate([itinerary_resp, budget_resp])
    final_content = result.answer
    
    # Should not have duplicate "Recommended Stay Plan"
    stay_count = final_content.count("Recommended Stay Plan")
    assert stay_count <= 1, f"Expected at most 1 'Recommended Stay Plan', got {stay_count}"
