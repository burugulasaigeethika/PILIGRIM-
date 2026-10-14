"""
Focused validation test for Budget Agent generalization and Nearby Attractions handling.
Tests dynamic data access, calculations, and category isolation across multiple temples.
"""

import sys
import re
from typing import Dict, Any

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "backend")

from app.agents.state import AgentState, AgentRouteDecision
from app.agents.budget_agent import BudgetAgent, parse_price_text
from app.agents.temple_information_agent import TempleInformationAgent
from app.agents.router import AgentRouter
from app.agents.tools.rag_tool import RAGTool


def run_tests():
    print("=====================================================================")
    print("PILGRIMAI GENERALIZATION TEST SUITE — BUDGET & NEARBY ATTRACTIONS")
    print("=====================================================================\n")

    rag_tool = RAGTool()
    budget_agent = BudgetAgent(rag_tool=rag_tool)
    temple_agent = TempleInformationAgent(rag_tool=rag_tool)
    router = AgentRouter(active_agents={"temple_information", "recommendation", "budget", "live_navigation", "weather"})

    passed = 0
    failed = 0

    def assert_test(cond: bool, test_name: str, details: str = ""):
        nonlocal passed, failed
        if cond:
            print(f"  [PASS] {test_name}")
            passed += 1
        else:
            print(f"  [FAIL] {test_name} -- {details}")
            failed += 1

    # =========================================================================
    # PART 1: DETERMINISTIC PRICE PARSER TESTS
    # =========================================================================
    print("--- 1. Testing Price Parser Distance & Unit Filtering ---")

    # Distance only should not parse as price
    min_v, max_v, _, _, _, is_q, _ = parse_price_text("~41.3 km", category="accommodation")
    assert_test(not is_q and min_v is None, "Distance '~41.3 km' not parsed as price", f"Got min={min_v}, is_q={is_q}")

    min_v, max_v, _, _, _, is_q, _ = parse_price_text("~37.2 km", category="accommodation")
    assert_test(not is_q and min_v is None, "Distance '~37.2 km' not parsed as price", f"Got min={min_v}, is_q={is_q}")

    min_v, max_v, _, _, _, is_q, _ = parse_price_text("500 meters from temple", category="accommodation")
    assert_test(not is_q and min_v is None, "Distance '500 meters from temple' not parsed as price", f"Got min={min_v}, is_q={is_q}")

    # Valid prices should parse correctly
    min_v, max_v, _, is_free, _, is_q, _ = parse_price_text("Free", category="entry")
    assert_test(is_q and is_free and min_v == 0.0, "Confirmed 'Free' parses as 0.0", f"Got min={min_v}, is_f={is_free}")

    min_v, max_v, _, _, is_rng, is_q, _ = parse_price_text("Rs. 500 - 1000", category="accommodation")
    assert_test(is_q and is_rng and min_v == 500.0 and max_v == 1000.0, "Range 'Rs. 500 - 1000' parses correctly", f"Got min={min_v}, max={max_v}")

    # =========================================================================
    # PART 2: BUDGET AGENT GENERALIZATION TESTS
    # =========================================================================
    print("\n--- 2. Testing Budget Agent Across Multiple Temples ---")

    # Scenario 2.1: Edupayala - 2 days overnight with unquantified accommodation in records
    print("\n[Scenario 2.1: Edupayala - Overnight Trip with Unquantified Accommodation]")
    state = AgentState(user_query="Estimate budget for 2 days 2 people at Edupayala with ₹2000 budget")
    resp = budget_agent.execute(state)
    assert_test(resp.success, "Edupayala 2-day query executes successfully")
    assert_test(not resp.metadata.get("calculated_total", {}).get("is_complete_estimate", True),
                "Edupayala estimate marked as incomplete due to missing room tariffs",
                f"is_complete_estimate={resp.metadata.get('calculated_total', {}).get('is_complete_estimate')}")
    assert_test("✅ Within Budget" not in resp.answer,
                "Edupayala does not falsely claim 'Within Budget' when accommodation is unknown")
    assert_test("Total" in resp.answer and ("Incomplete estimate" in resp.answer or "baseline only" in resp.answer),
                "Edupayala total clearly reports incomplete estimate")
    assert_test("₹41" not in resp.answer and "₹37" not in resp.answer and "Selected Accommodation — Vanam" not in resp.answer,
                "Edupayala does not treat 41.3 km or 37.2 km distance as ₹41 / ₹37 accommodation cost")

    # Scenario 2.2: Yadadri - 2 days 2 people, populated accommodation data, budget ₹5000
    print("\n[Scenario 2.2: Yadadri - 2 Days, 2 People with Populated Accommodation]")
    state = AgentState(user_query="Plan budget for 2 days 2 persons at Yadadri with a budget of ₹5000")
    resp = budget_agent.execute(state)
    assert_test(resp.success, "Yadadri 2-day query executes successfully")
    assert_test(resp.metadata["parameters"]["pax"] == 2, "Group size correctly parsed as 2", f"pax={resp.metadata['parameters']['pax']}")
    assert_test(resp.metadata["parameters"]["days"] == 2 and resp.metadata["parameters"]["nights"] == 1,
                "Duration parsed as 2 days, 1 night", f"days={resp.metadata['parameters']['days']}, nights={resp.metadata['parameters']['nights']}")
    assert_test(resp.metadata["calculated_total"]["is_complete_estimate"], "Yadadri estimate marked as complete (quantified rooms exist)")
    assert_test("Alternative Accommodation Options" in resp.answer, "Alternative accommodation options listed separately")
    assert_test("Selected Accommodation" in resp.answer, "One feasible accommodation selected and priced")

    # Scenario 2.3: Yadadri - Budget lower than accommodation (e.g. ₹200)
    print("\n[Scenario 2.3: Yadadri - Low Budget Exceeded]")
    state = AgentState(user_query="Budget for 2 days at Yadadri with ₹200 budget")
    resp = budget_agent.execute(state)
    assert_test("Exceeds Budget" in resp.answer, "Low budget ₹200 correctly flagged as Exceeds Budget")

    # Scenario 2.4: Chilkur Balaji - Day trip (no stay requested), free entry baseline
    print("\n[Scenario 2.4: Chilkur Balaji - Day Trip, Free Entry Baseline]")
    state = AgentState(user_query="What is the budget for 1 day visit to Chilkur Balaji for 2 people with ₹1000 budget?")
    resp = budget_agent.execute(state)
    assert_test(resp.success, "Chilkur Balaji day trip query executes successfully")
    assert_test(resp.metadata["parameters"]["nights"] == 0, "Chilkur day trip has 0 nights")
    assert_test("FREE" in resp.answer or "₹0" in resp.answer, "Chilkur general darshan identified as free")
    assert_test("excludes" in resp.answer.lower() or "unquantified" in resp.answer.lower(),
                "Chilkur explicitly explains excluded travel and dining expenses")
    # Verify it doesn't just state "Trip cost is ₹0 and within budget" without qualification
    assert_test("Note that" in resp.answer or "baseline only" in resp.answer or "excludes" in resp.answer,
                "Chilkur qualifies free entry baseline honestly")

    # Scenario 2.5: Basara - Overnight trip with user-provided travel cost
    print("\n[Scenario 2.5: Basara - Overnight Trip with User-Provided Travel Cost]")
    state = AgentState(user_query="Budget for 2 days 3 people at Basara, my travel cost is ₹1500, budget is ₹6000")
    resp = budget_agent.execute(state)
    assert_test(resp.success, "Basara query executes successfully")
    assert_test(resp.metadata["parameters"]["pax"] == 3, "Basara pax parsed as 3")
    assert_test(resp.metadata.get("user_item_count", 0) >= 1,
                "User travel cost tracked in budget metadata")
    assert_test("₹1,500" in resp.answer or "1500" in resp.answer, "User-provided travel ₹1500 reflected in breakdown")

    # Scenario 2.6: Srisailam - Multi-day trip (Generalization across another temple)
    print("\n[Scenario 2.6: Srisailam - 3 Days, 4 People]")
    state = AgentState(user_query="Plan budget for 3 days 4 people at Srisailam with ₹8000 budget")
    resp = budget_agent.execute(state)
    assert_test(resp.success, "Srisailam 3-day query executes successfully")
    assert_test(resp.metadata["parameters"]["pax"] == 4, "Srisailam pax parsed as 4")
    assert_test(resp.metadata["parameters"]["days"] == 3 and resp.metadata["parameters"]["nights"] == 2,
                "Srisailam duration parsed as 3 days, 2 nights")

    # =========================================================================
    # PART 3: NEARBY ATTRACTIONS TESTS
    # =========================================================================
    print("\n--- 3. Testing Nearby Attractions Across Multiple Temples ---")

    # Scenario 3.1: Yadadri - Populated attractions with distances
    print("\n[Scenario 3.1: Yadadri - Populated Attractions with Distances]")
    state = AgentState(user_query="What are the nearby places of Yadadri?")
    resp = temple_agent.execute(state)
    assert_test(resp.success, "Yadadri nearby attractions query succeeds")
    assert_test("Nearby Attractions" in resp.answer, "Response header confirms Nearby Attractions")
    assert_test("Patha Lakshmi Narasimha" in resp.answer or "Pathagutta" in resp.answer, "Authentic attraction Pathagutta present")
    assert_test("2 km" in resp.answer, "Distance '2 km' included from verified record")
    assert_test(any("nearby_attractions.json" in s for s in resp.sources), "Source strictly points to nearby_attractions.json")
    assert_test(not any("accommodation.json" in s for s in resp.sources), "Accommodation not substituted for nearby attractions")

    # Scenario 3.2: Basara - Natural variation ("What can I visit near Basara?")
    print("\n[Scenario 3.2: Basara - 'What can I visit near Basara?']")
    state = AgentState(user_query="What can I visit near Basara?")
    resp = temple_agent.execute(state)
    assert_test(resp.success, "Basara natural variation query succeeds")
    assert_test("Godavari River" in resp.answer or "Vyasa Maharshi" in resp.answer, "Authentic Basara attraction present")
    assert_test(any("basara/nearby_attractions.json" in s.replace("\\", "/") for s in resp.sources), "Basara nearby_attractions.json source preserved")

    # Scenario 3.3: Dharmapuri - Natural variation ("Recommend places to visit near Dharmapuri")
    print("\n[Scenario 3.3: Dharmapuri - 'Recommend places to visit near Dharmapuri']")
    # Test router decision
    r_dec = router.route("Recommend places to visit near Dharmapuri")
    assert_test(r_dec.selected_agent == "temple_information",
                "Router routes 'Recommend places to visit near Dharmapuri' to temple_information (not cross-temple recommendation)")
    state = AgentState(user_query="Recommend places to visit near Dharmapuri")
    resp = temple_agent.execute(state)
    assert_test(resp.success, "Dharmapuri attraction query succeeds")
    assert_test("Godavari" in resp.answer or "Ramalingeshwara" in resp.answer, "Authentic Dharmapuri attraction present")

    # Scenario 3.4: Edupayala - Natural variation with explicit distance mention
    print("\n[Scenario 3.4: Edupayala - 'Nearby attractions around Edupayala with distances']")
    state = AgentState(user_query="Nearby attractions around Edupayala with distances")
    resp = temple_agent.execute(state)
    assert_test(resp.success, "Edupayala attractions query succeeds")
    assert_test("Medak Fort" in resp.answer or "Medak Cathedral" in resp.answer or "Pocharam" in resp.answer,
                "Authentic Edupayala nearby attraction present")
    assert_test(any("nearby_attractions.json" in s for s in resp.sources), "Edupayala source points to nearby_attractions.json")

    # Scenario 3.5: Accommodation Query Preservation ("What are the hotels near Yadadri?")
    print("\n[Scenario 3.5: Accommodation Query Preservation - 'What are the hotels near Yadadri?']")
    q_hotel = "What are the hotels near Yadadri?"
    assert_test(not temple_agent._is_nearby_attractions_query(q_hotel),
                "Hotels query is NOT misclassified as nearby attractions")

    q_stay = "Places to stay near Basara"
    assert_test(not temple_agent._is_nearby_attractions_query(q_stay),
                "Places to stay query is NOT misclassified as nearby attractions")

    q_rooms = "Are there rooms available near Dharmapuri?"
    assert_test(not temple_agent._is_nearby_attractions_query(q_rooms),
                "Rooms query is NOT misclassified as nearby attractions")

    # Scenario 3.6: Multi-Intent Query ("What are the timings and nearby places of Yadadri?")
    print("\n[Scenario 3.6: Multi-Intent Query - Timings and Nearby Places]")
    r_multi = router.route("What are the timings and nearby places of Yadadri?")
    assert_test(r_multi.intent == "multi_intent",
                "Conjoined timings and nearby places detected as multi-intent")
    assert_test("nearby_attractions" in r_multi.metadata.get("sub_intents", []),
                "'nearby_attractions' identified as distinct sub-intent")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n=====================================================================")
    print(f"TEST RESULTS: {passed} PASSED, {failed} FAILED (TOTAL: {passed + failed})")
    print("=====================================================================")
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
