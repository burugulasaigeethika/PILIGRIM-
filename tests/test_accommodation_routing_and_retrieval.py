"""
PilgrimAI - Regression & Generalization Test Suite for Accommodation Routing,
Category Retrieval, and Budget Response Correctness.

Tests:
1. Routing:
   - Case A: Basic accommodation query ("edupayal accomodation")
   - Case B: All accommodations with amount and distance ("give all accomodations near edupayal templee with amount and distance")
   - Case C: Accommodation details with amount ("accomodation details of edupayal temple with amount")
   - Case D: Accommodation with prices ("accomodations of edupayal temple with prices")
   - Natural variations: "hotels near yadadri", "places to stay in basara", "room tariff at vemulavada"
   - Misspellings: "accomodation", "accomadations"
   - Preservation of genuine navigation ("how to reach Yadadri from Hyderabad")
   - Preservation of genuine total trip budget ("estimate budget for 2 days 2 people at Yadadri")
   - Multi-intent preservation ("how to reach Yadadri from Hyderabad and hotels near Yadadri")

2. Data Retrieval & Formatting:
   - Dynamic testing across multiple temples discovered from registry
   - Table formatting and presence of all records (not truncated to 1)
   - Proper source attribution (e.g. "{folder}/accommodation.json")
   - Rejection of distance strings as prices
   - Clear distinction between verified prices and unquantified tariffs

3. BudgetAgent Data Leakage Prevention:
   - No restaurants.json leak when dining is not requested
   - No unrequested sevas dumped under unavailable costs
   - No raw resort names with distances under unavailable costs
   - Honest incomplete estimate when overnight accommodation tariffs are unknown
"""

import sys
import os

# Ensure UTF-8 stdout on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add backend directory to path
sys.path.insert(0, os.path.abspath("backend"))

from app.agents.router import AgentRouter
from app.agents.temple_information_agent import TempleInformationAgent
from app.agents.budget_agent import BudgetAgent
from app.agents.state import AgentState
from app.agents.multi_intent_pipeline import SequentialMultiIntentPipeline


def run_tests():
    router = AgentRouter()
    info_agent = TempleInformationAgent()
    budget_agent = BudgetAgent()
    pipeline = SequentialMultiIntentPipeline(router=router, temple_info_agent=info_agent)

    passed = 0
    failed = 0

    def assert_test(cond, msg):
        nonlocal passed, failed
        if cond:
            print(f"  [PASS] {msg}")
            passed += 1
        else:
            print(f"  [FAIL] {msg}")
            failed += 1

    print("\n" + "=" * 70)
    print("PILGRIMAI ACCOMMODATION ROUTING & RETRIEVAL REGRESSION TESTS")
    print("=" * 70)

    # -------------------------------------------------------------
    # 1. Routing Verification: The 4 Live Cases + Natural Variations
    # -------------------------------------------------------------
    print("\n--- 1. Testing Accommodation Query Routing ---")

    # Case A
    dec_a = router.route("edupayal accomodation")
    assert_test(dec_a.selected_agent == "temple_information", "Case A: 'edupayal accomodation' routes to temple_information")
    assert_test(dec_a.intent == "temple_information", "Case A: intent is temple_information")

    # Case B
    dec_b = router.route("give all accomodations near edupayal templee with amount and distance")
    assert_test(dec_b.selected_agent == "temple_information", "Case B: 'give all accomodations near edupayal templee with amount and distance' routes to temple_information (not navigation)")
    assert_test(dec_b.intent != "live_navigation" and dec_b.intent != "multi_intent", "Case B: not misclassified as live_navigation or broken multi_intent")

    # Case C
    dec_c = router.route("accomodation details of edupayal temple with amount")
    assert_test(dec_c.selected_agent == "temple_information", "Case C: 'accomodation details of edupayal temple with amount' routes to temple_information")

    # Case D
    dec_d = router.route("accomodations of edupayal temple with prices")
    assert_test(dec_d.selected_agent == "temple_information", "Case D: 'accomodations of edupayal temple with prices' routes to temple_information (not budget)")

    # Natural variations across temples
    dec_yad = router.route("hotels near yadadri with price and distance")
    assert_test(dec_yad.selected_agent == "temple_information", "'hotels near yadadri with price and distance' routes to temple_information")

    dec_vem = router.route("room tariff at vemulavada")
    assert_test(dec_vem.selected_agent == "temple_information", "'room tariff at vemulavada' routes to temple_information")

    dec_bas = router.route("places to stay in basara")
    assert_test(dec_bas.selected_agent == "temple_information", "'places to stay in basara' routes to temple_information")

    dec_dhar = router.route("all lodges near dharmapuri with amount and distance")
    assert_test(dec_dhar.selected_agent == "temple_information", "'all lodges near dharmapuri with amount and distance' routes to temple_information")

    # -------------------------------------------------------------
    # 2. Preservation of Navigation, Budget, and Multi-Intent
    # -------------------------------------------------------------
    print("\n--- 2. Testing Preservation of Navigation, Budget & Multi-Intent ---")

    dec_nav = router.route("how to reach Yadadri from Hyderabad")
    assert_test(dec_nav.intent == "live_navigation", "Genuine navigation: 'how to reach Yadadri from Hyderabad' matches live_navigation intent")

    dec_dir = router.route("directions to Edupayala")
    assert_test(dec_dir.intent == "live_navigation", "Genuine navigation: 'directions to Edupayala' matches live_navigation intent")

    dec_bud = router.route("estimate budget for 2 days 2 people at Edupayala with ₹2000 budget")
    assert_test(dec_bud.intent == "budget", "Genuine budget: 'estimate budget for 2 days 2 people...' matches budget intent")

    dec_bud2 = router.route("calculate budget for Yadadri for 4 people with ₹5000 budget")
    assert_test(dec_bud2.intent == "budget", "Genuine budget: 'calculate budget for Yadadri for 4 people with ₹5000 budget' matches budget intent")

    # Multi-intent decomposition test
    multi_tasks = pipeline.decompose_query("how to reach Yadadri from Hyderabad and hotels near Yadadri")
    assert_test(len(multi_tasks) == 2, "Multi-intent: conjoined navigation and accommodation splits into 2 tasks")
    target_agents = [t["target_agent"] for t in multi_tasks]
    assert_test("live_navigation" in target_agents, "Multi-intent: clause 1 targets live_navigation")
    assert_test("temple_information" in target_agents, "Multi-intent: clause 2 targets temple_information")

    # Ensure attribute conjunctions are NOT split
    single_clause_tasks = pipeline.decompose_query("give all accomodations near edupayal templee with amount and distance")
    assert_test(len(single_clause_tasks) == 1, "'amount and distance' in accommodation query is NOT split into multiple tasks")

    # -------------------------------------------------------------
    # 3. Execution Verification for Case A, B, C, D on Edupayala
    # -------------------------------------------------------------
    print("\n--- 3. Testing Execution & Grounding on Edupayala ---")

    res_d = info_agent.execute(AgentState(user_query="accomodations of edupayal temple with prices"))
    assert_test(res_d.success, "Case D executes successfully")
    assert_test(res_d.sources == ["edupayal/accommodation.json"], f"Case D source strictly points to edupayal/accommodation.json (got: {res_d.sources})")
    assert_test("| Accommodation | Type | Distance / Location | Price / Tariff |" in res_d.answer, "Case D answer includes structured markdown table")
    assert_test("Cottages" in res_d.answer, "Case D includes Cottages record")
    assert_test("Haritha Hotel Edupayala" in res_d.answer, "Case D includes Haritha Hotel record")
    assert_test("Haritha Lake View Resort" in res_d.answer, "Case D includes Haritha Lake View Resort record")
    assert_test("Alankar Lodge" in res_d.answer, "Case D includes Alankar Lodge record")
    assert_test("Vanam Resort" in res_d.answer, "Case D includes Vanam Resort record")
    assert_test("Narsapur Forest Area Resorts" in res_d.answer, "Case D includes Narsapur Forest Area Resorts record")
    assert_test("₹41" not in res_d.answer and "₹37" not in res_d.answer, "Case D does NOT hallucinate distances (~41.3 km, ~37.2 km) as ₹41 / ₹37 prices")
    assert_test("General Darshan" not in res_d.answer, "Case D does NOT inject irrelevant general darshan into accommodation answer")
    assert_test("restaurants.json" not in str(res_d.sources), "Case D does NOT include restaurants.json in sources")

    res_b = info_agent.execute(AgentState(user_query="give all accomodations near edupayal templee with amount and distance"))
    assert_test(res_b.success, "Case B executes successfully")
    assert_test(res_b.sources == ["edupayal/accommodation.json"], "Case B source strictly points to edupayal/accommodation.json")
    assert_test("Please provide a recognizable origin" not in res_b.answer, "Case B does NOT output navigation error")
    assert_test("Adjoining the temple complex" in res_b.answer or "~500 meters" in res_b.answer, "Case B includes authentic distances from records")

    # -------------------------------------------------------------
    # 4. Generalization Across Other Registered Temples
    # -------------------------------------------------------------
    print("\n--- 4. Testing Generalization Across Multiple Registered Temples ---")

    # Yadadri
    res_yad = info_agent.execute(AgentState(user_query="give all accommodations near Yadadri with price and distance"))
    assert_test(res_yad.success, "Yadadri accommodation query succeeds")
    assert_test(res_yad.sources == ["yadadri/accommodation.json"], "Yadadri source points to yadadri/accommodation.json")
    assert_test("YTDA Divya Sannidhi Cottages" in res_yad.answer, "Yadadri includes YTDA Divya Sannidhi Cottages")
    assert_test("₹3,000" in res_yad.answer, "Yadadri preserves verified tariff ₹3,000 per night")
    assert_test("2.7 to 3.5 km" in res_yad.answer, "Yadadri preserves verified distance 2.7 to 3.5 km")

    # Vemulavada
    res_vem = info_agent.execute(AgentState(user_query="what are the hotels near Vemulavada with tariffs?"))
    assert_test(res_vem.success, "Vemulavada accommodation query succeeds")
    assert_test(res_vem.sources == ["vemulavada/accommodation.json"], "Vemulavada source points to vemulavada/accommodation.json")
    assert_test("Balaji Lodge" in res_vem.answer, "Vemulavada includes Balaji Lodge")
    assert_test("₹900 - ₹1,700" in res_vem.answer, "Vemulavada preserves verified tariff ₹900 - ₹1,700")

    # Karmanghat (no price fields in source)
    res_kar = info_agent.execute(AgentState(user_query="give accommodation options near Karmanghat"))
    assert_test(res_kar.success, "Karmanghat accommodation query succeeds")
    assert_test(res_kar.sources == ["karmanghat/accommodation.json"], "Karmanghat source points to karmanghat/accommodation.json")
    assert_test("Super Townhouse Oak" in res_kar.answer, "Karmanghat includes Super Townhouse Oak")
    assert_test("Not available in verified records" in res_kar.answer, "Karmanghat honestly states price is unquantified")

    # -------------------------------------------------------------
    # 5. BudgetAgent Data Leakage Prevention Tests
    # -------------------------------------------------------------
    print("\n--- 5. Testing BudgetAgent Data Leakage Prevention ---")

    res_bgt = budget_agent.execute(AgentState(user_query="estimate budget for 2 days 2 people at Edupayala with ₹2000 budget"))
    assert_test(res_bgt.success, "Edupayala budget executes successfully")
    assert_test("edupayal/restaurants.json" not in res_bgt.sources, f"BudgetAgent does NOT leak restaurants.json into sources when dining is not requested (got: {res_bgt.sources})")
    assert_test("Local Stalls" not in res_bgt.answer, "BudgetAgent does NOT list 'Local Stalls: Budget' under unavailable costs")
    assert_test("Abhishekam" not in res_bgt.answer and "Vedaparayanam" not in res_bgt.answer, "BudgetAgent does NOT dump unrequested sevas under unavailable costs")
    assert_test("Vanam Resort" not in res_bgt.answer and "~41.3 km" not in res_bgt.answer, "BudgetAgent does NOT dump individual resort distances under unavailable costs")
    assert_test("Accommodation / Stay" in res_bgt.answer, "BudgetAgent cleanly reports Accommodation / Stay tariff is unquantified")
    assert_test("Feasibility cannot be determined" in res_bgt.answer or "Incomplete Estimate" in res_bgt.answer, "BudgetAgent marks budget feasibility as cannot be confirmed")
    assert_test("✅ Within Budget" not in res_bgt.answer, "BudgetAgent does NOT falsely declare overnight stay 'Within Budget'")

    # Day trip with no accommodation requested: accommodation should not appear under Costs Not Available
    res_day = budget_agent.execute(AgentState(user_query="estimate budget for 1 day trip to Chilkur Balaji"))
    assert_test(res_day.success, "Chilkur 1-day budget executes successfully")
    assert_test("General Darshan: FREE" in res_day.answer or "General Darshan: FREE" in res_day.answer.replace("**", ""), "Chilkur recognizes free general darshan")
    assert_test("Accommodation" not in res_day.answer.split("### Costs Not Available")[1].split("### Total")[0], "Day trip without room request does NOT list accommodation under Costs Not Available")

    print("\n" + "=" * 70)
    print(f"TEST RESULTS: {passed} PASSED, {failed} FAILED (TOTAL: {passed + failed})")
    print("=" * 70)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
