import sys
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

# Setup root paths
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.rag.knowledge_registry import knowledge_registry
from app.rag.category_registry import category_registry
from app.rag.completeness_validator import completeness_validator, CONFIRMED_AVAILABLE, CONFIRMED_UNAVAILABLE, INFORMATION_NOT_AVAILABLE

def generate_benchmark_dataset() -> List[Dict[str, Any]]:
    print("Generating comprehensive 300+ question benchmark dataset from verified knowledge base...")
    temples = knowledge_registry.get_temples()
    dataset: List[Dict[str, Any]] = []
    q_id = 1

    # -------------------------------------------------------------
    # 1. Targeted Factual Questions (120 Questions: 20 Temples x 6 Topics)
    # -------------------------------------------------------------
    targeted_topics = [
        ("timings", "What are the temple timings at {temple}?", "timings"),
        ("contacts", "What is the contact number of {temple} temple?", "contacts"),
        ("history", "What is the history of {temple} temple?", "temple"),
        ("rules", "What is the dress code and rules at {temple}?", "rules"),
        ("wheelchair", "Does {temple} have wheelchair facilities?", "wheelchair"),
        ("travel", "How can I travel to {temple}?", "travel")
    ]

    for t in temples:
        for topic_key, query_template, cat_key in targeted_topics:
            query = query_template.format(temple=t)
            raw_data = knowledge_registry.get_temple_raw_data(t, cat_key)
            status, ev, _ = completeness_validator.evaluate_availability(raw_data, cat_key)
            
            dataset.append({
                "id": f"TARGETED_{q_id:03d}",
                "query": query,
                "archetype": "targeted",
                "temple": t,
                "category": cat_key,
                "expected_route": "targeted",
                "expected_scope": "single_temple",
                "expected_temples": [t],
                "expected_categories": [cat_key],
                "exhaustive": False,
                "expected_status": status,
                "expected_evidence_preview": ev or ""
            })
            q_id += 1

    # -------------------------------------------------------------
    # 2. Complete Category Questions (40 Questions: 20 Temples x 2 List Categories)
    # -------------------------------------------------------------
    list_topics = [
        ("sevas", "What are all the sevas in {temple}?", "sevas"),
        ("festivals", "List all festivals celebrated at {temple}.", "festivals")
    ]

    for t in temples:
        for topic_key, query_template, cat_key in list_topics:
            query = query_template.format(temple=t)
            raw_data = knowledge_registry.get_temple_raw_data(t, cat_key)
            item_count = len(raw_data) if isinstance(raw_data, list) else (len(raw_data.keys()) if isinstance(raw_data, dict) else 0)

            dataset.append({
                "id": f"COMPLETE_{q_id:03d}",
                "query": query,
                "archetype": "complete_category",
                "temple": t,
                "category": cat_key,
                "expected_route": "complete_category",
                "expected_scope": "single_temple",
                "expected_temples": [t],
                "expected_categories": [cat_key],
                "exhaustive": True,
                "expected_item_count": item_count
            })
            q_id += 1

    # -------------------------------------------------------------
    # 3. Cross-Temple Positive Aggregation (25 Questions)
    # -------------------------------------------------------------
    pos_agg_templates = [
        ("river_bank", "List all temples that have a river bank.", "river_bank"),
        ("river_bank", "Which temples are situated near a river or water body?", "river_bank"),
        ("accommodation", "Which temples have accommodation?", "accommodation"),
        ("accommodation", "List all temples offering rooms or cottages for stay.", "accommodation"),
        ("restaurants", "Which temples have restaurants or food nearby?", "restaurants"),
        ("restaurants", "List all temples with nearby dining facilities.", "restaurants"),
        ("wheelchair", "Which temples have wheelchair access?", "wheelchair"),
        ("wheelchair", "List all temples that provide wheelchair ramps.", "wheelchair"),
        ("facilities", "Which temples provide vehicle parking facilities?", "facilities"),
        ("prasadam", "Which temples offer free Annadanam meals?", "prasadam"),
        ("sevas", "Which temples perform daily sevas?", "sevas"),
        ("festivals", "Which temples celebrate annual Brahmotsavams or festivals?", "festivals"),
        ("donations", "Which temples accept online e-hundi donations?", "donations")
    ]

    for cat_key, query, prop_name in pos_agg_templates:
        # Determine exact matching temples dynamically
        matching_temples = []
        for t in temples:
            data = knowledge_registry.get_temple_raw_data(t, cat_key)
            st, _, _ = completeness_validator.evaluate_availability(data, cat_key)
            if st == CONFIRMED_AVAILABLE:
                matching_temples.append(t)

        dataset.append({
            "id": f"CROSS_POS_{q_id:03d}",
            "query": query,
            "archetype": "cross_temple_positive",
            "category": cat_key,
            "expected_route": "cross_temple_aggregation",
            "expected_scope": "cross_temple",
            "expected_condition": "positive",
            "expected_temples": matching_temples,
            "expected_match_count": len(matching_temples),
            "exhaustive": True
        })
        q_id += 1

    # -------------------------------------------------------------
    # 4. Cross-Temple Negative Aggregation (25 Questions)
    # -------------------------------------------------------------
    neg_agg_templates = [
        ("wheelchair", "List all temples that don't have wheelchair facilities.", "wheelchair"),
        ("wheelchair", "Which temples lack wheelchair ramps or disabled access?", "wheelchair"),
        ("wheelchair", "Which temples are not wheelchair accessible?", "wheelchair"),
        ("restaurants", "Which temples don't have restaurants?", "restaurants"),
        ("accommodation", "Which temples don't have accommodation?", "accommodation"),
        ("facilities", "Which temples don't have dedicated parking?", "facilities")
    ]

    for cat_key, query, prop_name in neg_agg_templates:
        unavail_temples = []
        info_missing_temples = []
        for t in temples:
            data = knowledge_registry.get_temple_raw_data(t, cat_key)
            st, _, _ = completeness_validator.evaluate_availability(data, cat_key)
            if st == CONFIRMED_UNAVAILABLE:
                unavail_temples.append(t)
            elif st == INFORMATION_NOT_AVAILABLE:
                info_missing_temples.append(t)

        dataset.append({
            "id": f"CROSS_NEG_{q_id:03d}",
            "query": query,
            "archetype": "cross_temple_negative",
            "category": cat_key,
            "expected_route": "cross_temple_aggregation",
            "expected_condition": "negative",
            "expected_scope": "cross_temple",
            "expected_confirmed_unavailable": unavail_temples,
            "expected_information_missing": info_missing_temples,
            "exhaustive": True
        })
        q_id += 1

    # -------------------------------------------------------------
    # 5. Multi-Category Questions (30 Questions)
    # -------------------------------------------------------------
    multi_templates = [
        ("What accommodation and restaurants are available near {temple}?", ["accommodation", "restaurants"]),
        ("What are the timings, sevas and festivals at {temple}?", ["timings", "sevas", "festivals"]),
        ("Tell me about facilities and travel options for {temple}.", ["facilities", "travel"]),
        ("What are the rules and timings at {temple}?", ["rules", "timings"]),
        ("What prasadams and sevas are offered at {temple}?", ["prasadam", "sevas"])
    ]

    for t in temples[:6]: # Across 6 major temples x 5 combinations = 30
        for q_tmpl, cats in multi_templates:
            query = q_tmpl.format(temple=t)
            dataset.append({
                "id": f"MULTI_{q_id:03d}",
                "query": query,
                "archetype": "multi_category",
                "temple": t,
                "categories": cats,
                "expected_route": "multi_category",
                "expected_scope": "single_temple",
                "expected_temples": [t],
                "expected_categories": cats,
                "exhaustive": True
            })
            q_id += 1

    # -------------------------------------------------------------
    # 6. Broad Temple Overview Questions (20 Questions: All 20 Temples)
    # -------------------------------------------------------------
    for t in temples:
        query = f"Tell me everything about {t} Temple."
        dataset.append({
            "id": f"BROAD_{q_id:03d}",
            "query": query,
            "archetype": "broad_temple",
            "temple": t,
            "expected_route": "broad_temple",
            "expected_scope": "single_temple",
            "expected_temples": [t],
            "expected_categories": ["*"],
            "exhaustive": True
        })
        q_id += 1

    # -------------------------------------------------------------
    # 7. Grounded Refusal Questions (30 Questions)
    # -------------------------------------------------------------
    fictitious_topics = [
        ("Does {temple} have a helicopter launch pad?", "helicopter"),
        ("Does {temple} have a metro train station inside the sanctum?", "metro"),
        ("Does {temple} offer submarine boat rides?", "submarine"),
        ("Is there an indoor ski resort at {temple}?", "ski resort"),
        ("Does {temple} have an international airport inside the complex?", "airport"),
        ("What is the ticket price for roller coaster rides at {temple}?", "roller coaster")
    ]

    for t in temples[:5]: # 5 temples x 6 fictitious topics = 30
        for q_tmpl, fake_topic in fictitious_topics:
            query = q_tmpl.format(temple=t)
            dataset.append({
                "id": f"REFUSAL_{q_id:03d}",
                "query": query,
                "archetype": "grounded_refusal",
                "temple": t,
                "fake_entity": fake_topic,
                "expected_route": "targeted",
                "expected_scope": "single_temple",
                "expected_refusal": True,
                "exhaustive": False
            })
            q_id += 1

    # -------------------------------------------------------------
    # 8. Colloquial / Natural Language Variations (40 Questions)
    # -------------------------------------------------------------
    colloquial_cases = [
        ("Can I crash near {temple} for the night?", "accommodation", "targeted"),
        ("Where can I grab good food around {temple}?", "restaurants", "targeted"),
        ("What time does the main darshan start at {temple}?", "timings", "targeted"),
        ("Do they have wheelchair help for old people at {temple}?", "wheelchair", "targeted"),
        ("How to reach {temple} by train or bus?", "travel", "targeted"),
        ("What poojas are done at {temple}?", "sevas", "targeted")
    ]
    for q_tmpl, cat_k, exp_r in colloquial_cases:
        for t in temples[:8]: # 8 temples x 6 templates = 48 questions
            q_str = q_tmpl.format(temple=t)
            dataset.append({
                "id": f"COLLOQUIAL_{q_id:03d}",
                "query": q_str,
                "archetype": "colloquial",
                "temple": t,
                "category": cat_k,
                "expected_route": exp_r,
                "expected_scope": "single_temple",
                "expected_temples": [t],
                "expected_categories": [cat_k],
                "exhaustive": False
            })
            q_id += 1

    out_file = Path(__file__).resolve().parent / "benchmark_dataset.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2)

    print(f"Generated {len(dataset)} verified benchmark questions in {out_file}")
    return dataset

if __name__ == "__main__":
    generate_benchmark_dataset()
