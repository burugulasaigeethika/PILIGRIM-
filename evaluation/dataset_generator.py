import os
import sys
import json
import random
from pathlib import Path
from typing import List, Dict, Any

# Ensure project root is in sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.rag.loader import TempleDatasetLoader
from app.rag.config import settings

RANDOM_SEED = 42

def extract_string_value(val: Any) -> str:
    """Safely format string from json value without hallucinating."""
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, (int, float, bool)):
        return str(val)
    if isinstance(val, list):
        items = [extract_string_value(x) for x in val if x]
        return ", ".join(items[:5])
    if isinstance(val, dict):
        parts = []
        for k, v in list(val.items())[:4]:
            if isinstance(v, (str, int, float, bool)):
                parts.append(f"{k}: {v}")
            elif isinstance(v, dict):
                sub_parts = [f"{sk}: {sv}" for sk, sv in list(v.items())[:2] if isinstance(sv, (str, int, float))]
                if sub_parts:
                    parts.append(f"{k} ({', '.join(sub_parts)})")
        return "; ".join(parts)
    return str(val)

def build_temple_questions(temple_name: str, folder_path: Path, temple_idx: int) -> List[Dict[str, Any]]:
    """Extract grounded questions directly from temple JSON files."""
    questions = []
    t_name = temple_name.title()
    t_id = folder_path.name.lower()
    
    # 1. temple.json
    p_temple = folder_path / "temple.json"
    if p_temple.exists():
        with open(p_temple, "r", encoding="utf-8") as f:
            d_temple = json.load(f)
        
        # Main Deity
        deity = d_temple.get("main_deity")
        if deity:
            deity_str = extract_string_value(deity)
            questions.append({
                "id": f"q_{t_id}_01",
                "temple_id": t_id,
                "temple_name": t_name,
                "category": "basic_factual",
                "question": f"Who is the main deity worshipped at {t_name} temple?",
                "expected_answer": f"The main deity of {t_name} temple is {deity_str}.",
                "source_files": [f"{t_id}/temple.json"],
                "source_fields": ["main_deity"],
                "answerable": True,
                "difficulty": "easy",
                "test_type": "single_field"
            })
        
        # Location / Village / District
        loc_parts = []
        if d_temple.get("village"):
            loc_parts.append(f"Village: {d_temple.get('village')}")
        if d_temple.get("district"):
            loc_parts.append(f"District: {d_temple.get('district')}")
        if d_temple.get("state"):
            loc_parts.append(f"State: {d_temple.get('state')}")
        if loc_parts:
            questions.append({
                "id": f"q_{t_id}_02",
                "temple_id": t_id,
                "temple_name": t_name,
                "category": "basic_factual",
                "question": f"Where is {t_name} temple located?",
                "expected_answer": f"{t_name} temple is located at {', '.join(loc_parts)}.",
                "source_files": [f"{t_id}/temple.json"],
                "source_fields": ["village", "district", "state"],
                "answerable": True,
                "difficulty": "easy",
                "test_type": "multi_field"
            })
            
        # History / Mythology
        hist = d_temple.get("history") or d_temple.get("mythology")
        if hist:
            hist_str = extract_string_value(hist)[:200]
            questions.append({
                "id": f"q_{t_id}_03",
                "temple_id": t_id,
                "temple_name": t_name,
                "category": "basic_factual",
                "question": f"What is the historical or mythological background of {t_name} temple?",
                "expected_answer": hist_str,
                "source_files": [f"{t_id}/temple.json"],
                "source_fields": ["history", "mythology"],
                "answerable": True,
                "difficulty": "medium",
                "test_type": "single_field"
            })

    # 2. timings.json
    p_timings = folder_path / "timings.json"
    if p_timings.exists():
        with open(p_timings, "r", encoding="utf-8") as f:
            d_timings = json.load(f)
        
        op = d_timings.get("opening_time")
        cl = d_timings.get("closing_time")
        brk = d_timings.get("afternoon_break")
        if op and cl:
            ans = f"{t_name} temple opens at {op} and closes at {cl}."
            if brk:
                ans += f" Afternoon break is {brk}."
            questions.append({
                "id": f"q_{t_id}_04",
                "temple_id": t_id,
                "temple_name": t_name,
                "category": "basic_factual",
                "question": f"What are the daily opening and closing timings of {t_name} temple?",
                "expected_answer": ans,
                "source_files": [f"{t_id}/timings.json"],
                "source_fields": ["opening_time", "closing_time", "afternoon_break"],
                "answerable": True,
                "difficulty": "easy",
                "test_type": "single_field"
            })
            
        # Natural variation for timings
        questions.append({
            "id": f"q_{t_id}_05",
            "temple_id": t_id,
            "temple_name": t_name,
            "category": "basic_factual",
            "question": f"When can devotees visit {t_name} temple for darshan during the day?",
            "expected_answer": f"Devotees can visit between opening time {op} and closing time {cl}." if op and cl else "Check daily schedule in timings.",
            "source_files": [f"{t_id}/timings.json"],
            "source_fields": ["opening_time", "closing_time", "daily_schedule"],
            "answerable": True,
            "difficulty": "medium",
            "test_type": "query_variation"
        })

    # 3. sevas.json
    p_sevas = folder_path / "sevas.json"
    if p_sevas.exists():
        with open(p_sevas, "r", encoding="utf-8") as f:
            d_sevas = json.load(f)
        if isinstance(d_sevas, list) and d_sevas:
            s_sample = d_sevas[:3]
            s_names = [s.get("seva_name") or s.get("name") or s.get("title") for s in s_sample if isinstance(s, dict)]
            s_names = [x for x in s_names if x]
            if s_names:
                questions.append({
                    "id": f"q_{t_id}_06",
                    "temple_id": t_id,
                    "temple_name": t_name,
                    "category": "service",
                    "question": f"What sevas or poojas are performed at {t_name} temple?",
                    "expected_answer": f"Sevas performed at {t_name} include: {', '.join(s_names)}.",
                    "source_files": [f"{t_id}/sevas.json"],
                    "source_fields": ["sevas", "seva_name", "name"],
                    "answerable": True,
                    "difficulty": "medium",
                    "test_type": "single_field"
                })
        elif isinstance(d_sevas, dict) and d_sevas:
            k_names = list(d_sevas.keys())[:3]
            questions.append({
                "id": f"q_{t_id}_06",
                "temple_id": t_id,
                "temple_name": t_name,
                "category": "service",
                "question": f"What sevas are conducted at {t_name} temple?",
                "expected_answer": f"Sevas at {t_name} include: {', '.join(k_names)}.",
                "source_files": [f"{t_id}/sevas.json"],
                "source_fields": ["sevas"],
                "answerable": True,
                "difficulty": "medium",
                "test_type": "single_field"
            })

    # 4. facilities.json
    p_fac = folder_path / "facilities.json"
    if p_fac.exists():
        with open(p_fac, "r", encoding="utf-8") as f:
            d_fac = json.load(f)
        fac_items = []
        if isinstance(d_fac, dict):
            if "facilities" in d_fac and isinstance(d_fac["facilities"], dict):
                fac_items = list(d_fac["facilities"].keys())
            else:
                fac_items = [k for k, v in d_fac.items() if v]
        if fac_items:
            questions.append({
                "id": f"q_{t_id}_07",
                "temple_id": t_id,
                "temple_name": t_name,
                "category": "service",
                "question": f"What facilities and amenities are available for pilgrims at {t_name} temple?",
                "expected_answer": f"Facilities at {t_name} include: {', '.join(fac_items[:5])}.",
                "source_files": [f"{t_id}/facilities.json"],
                "source_fields": ["facilities"],
                "answerable": True,
                "difficulty": "easy",
                "test_type": "single_field"
            })

    # 5. festivals.json
    p_fest = folder_path / "festivals.json"
    if p_fest.exists():
        with open(p_fest, "r", encoding="utf-8") as f:
            d_fest = json.load(f)
        fest_names = []
        if isinstance(d_fest, list):
            for itm in d_fest[:3]:
                if isinstance(itm, dict):
                    fn = itm.get("festival_name") or itm.get("name") or itm.get("title")
                    if fn:
                        fest_names.append(fn)
        elif isinstance(d_fest, dict):
            fest_names = list(d_fest.keys())[:3]
        if fest_names:
            questions.append({
                "id": f"q_{t_id}_08",
                "temple_id": t_id,
                "temple_name": t_name,
                "category": "festivals",
                "question": f"What major festivals and annual celebrations take place at {t_name} temple?",
                "expected_answer": f"Major festivals celebrated at {t_name} include: {', '.join(fest_names)}.",
                "source_files": [f"{t_id}/festivals.json"],
                "source_fields": ["festivals", "festival_name"],
                "answerable": True,
                "difficulty": "medium",
                "test_type": "single_field"
            })

    # 6. rules.json
    p_rules = folder_path / "rules.json"
    if p_rules.exists():
        with open(p_rules, "r", encoding="utf-8") as f:
            d_rules = json.load(f)
        dress = d_rules.get("dress_code")
        dos = d_rules.get("dos")
        donts = d_rules.get("donts")
        ans_parts = []
        if dress:
            ans_parts.append(f"Dress Code: {extract_string_value(dress)}")
        if dos:
            ans_parts.append(f"Do's: {extract_string_value(dos)[:100]}")
        if donts:
            ans_parts.append(f"Don'ts: {extract_string_value(donts)[:100]}")
        if ans_parts:
            questions.append({
                "id": f"q_{t_id}_09",
                "temple_id": t_id,
                "temple_name": t_name,
                "category": "rules",
                "question": f"What are the dress codes and code of conduct rules for visiting {t_name} temple?",
                "expected_answer": "; ".join(ans_parts),
                "source_files": [f"{t_id}/rules.json"],
                "source_fields": ["dress_code", "dos", "donts"],
                "answerable": True,
                "difficulty": "easy",
                "test_type": "single_field"
            })

    # 7. how_to_reach.json or maps.json
    p_reach = folder_path / "how_to_reach.json"
    p_maps = folder_path / "maps.json"
    reach_data = {}
    source_f = []
    if p_reach.exists():
        with open(p_reach, "r", encoding="utf-8") as f:
            reach_data.update(json.load(f))
        source_f.append(f"{t_id}/how_to_reach.json")
    elif p_maps.exists():
        with open(p_maps, "r", encoding="utf-8") as f:
            reach_data.update(json.load(f))
        source_f.append(f"{t_id}/maps.json")
    
    if reach_data:
        ans_r = []
        if reach_data.get("nearest_railway_station") or reach_data.get("railway"):
            ans_r.append(f"Nearest Railway: {extract_string_value(reach_data.get('nearest_railway_station') or reach_data.get('railway'))}")
        if reach_data.get("nearest_airport"):
            ans_r.append(f"Nearest Airport: {extract_string_value(reach_data.get('nearest_airport'))}")
        if reach_data.get("road_routes") or reach_data.get("bus_station"):
            ans_r.append(f"Road/Bus: {extract_string_value(reach_data.get('road_routes') or reach_data.get('bus_station'))[:100]}")
        if ans_r:
            questions.append({
                "id": f"q_{t_id}_10",
                "temple_id": t_id,
                "temple_name": t_name,
                "category": "travel",
                "question": f"How can devotees travel to {t_name} temple by train, bus, or flight?",
                "expected_answer": "; ".join(ans_r),
                "source_files": source_f,
                "source_fields": ["nearest_railway_station", "nearest_airport", "road_routes"],
                "answerable": True,
                "difficulty": "medium",
                "test_type": "single_field"
            })

    # 8. emergency_nos.json or contacts.json
    p_em = folder_path / "emergency_nos.json"
    p_con = folder_path / "contacts.json"
    con_data = {}
    con_src = []
    if p_em.exists():
        with open(p_em, "r", encoding="utf-8") as f:
            con_data.update(json.load(f))
        con_src.append(f"{t_id}/emergency_nos.json")
    if p_con.exists():
        with open(p_con, "r", encoding="utf-8") as f:
            con_data.update(json.load(f))
        con_src.append(f"{t_id}/contacts.json")
    if con_data:
        em_parts = []
        for k in ["police", "medical", "ambulance", "temple_office", "helpline", "phones"]:
            if con_data.get(k):
                em_parts.append(f"{k.replace('_', ' ').title()}: {extract_string_value(con_data.get(k))}")
        if em_parts:
            questions.append({
                "id": f"q_{t_id}_11",
                "temple_id": t_id,
                "temple_name": t_name,
                "category": "travel",
                "question": f"What are the emergency contact and helpline numbers for {t_name} temple?",
                "expected_answer": "; ".join(em_parts[:4]),
                "source_files": con_src,
                "source_fields": ["police", "medical", "helpline", "phones"],
                "answerable": True,
                "difficulty": "easy",
                "test_type": "single_field"
            })

    # 9. Multi-field question (Combines timings + rules/dress code)
    if p_timings.exists() and p_rules.exists():
        questions.append({
            "id": f"q_{t_id}_12",
            "temple_id": t_id,
            "temple_name": t_name,
            "category": "multi_field",
            "question": f"What are the darshan timings and required dress code guidelines at {t_name} temple?",
            "expected_answer": f"Timings: {op} to {cl}. Dress code: {extract_string_value(d_rules.get('dress_code'))[:80]}.",
            "source_files": [f"{t_id}/timings.json", f"{t_id}/rules.json"],
            "source_fields": ["opening_time", "closing_time", "dress_code"],
            "answerable": True,
            "difficulty": "hard",
            "test_type": "multi_field"
        })

    # 10. Multi-hop question (Combines deity + history/architecture + location)
    if p_temple.exists() and (reach_data or p_reach.exists() or p_maps.exists()):
        questions.append({
            "id": f"q_{t_id}_13",
            "temple_id": t_id,
            "temple_name": t_name,
            "category": "multi_hop",
            "question": f"Tell me about the presiding deity of {t_name} temple and how to reach the temple premises.",
            "expected_answer": f"Deity: {extract_string_value(deity)}. Location & Travel: {', '.join(loc_parts)}.",
            "source_files": [f"{t_id}/temple.json"] + source_f,
            "source_fields": ["main_deity", "village", "nearest_railway_station"],
            "answerable": True,
            "difficulty": "hard",
            "test_type": "multi_hop"
        })

    return questions

def generate_evaluation_dataset() -> Dict[str, Any]:
    """Scans all 20 temples, generates questions, includes negative tests, and saves evaluation_dataset.json."""
    random.seed(RANDOM_SEED)
    
    loader = TempleDatasetLoader(dataset_dir=settings.DATASET_DIR)
    temple_folders = loader.discover_temple_folders()
    temple_folders = sorted(temple_folders, key=lambda x: x.name)
    
    all_questions = []
    temple_metadata = []
    
    for idx, folder in enumerate(temple_folders):
        t_id = folder.name.lower()
        t_name = folder.name.title()
        
        jsons = list(folder.rglob("*.json"))
        categories = sorted([j.stem for j in jsons])
        
        temple_metadata.append({
            "temple_id": t_id,
            "temple_name": t_name,
            "dataset_directory": str(folder),
            "total_json_files": len(jsons),
            "available_categories": categories
        })
        
        t_questions = build_temple_questions(t_name, folder, idx)
        all_questions.extend(t_questions)

    # Add ~14 negative / unanswerable questions (1 per selected temple)
    negative_templates = [
        ("basara", "Basara", "What is the ticket price for a space rocket launch from Basara temple?"),
        ("chilkur", "Chilkur", "How much does a helicopter airport shuttle ticket cost at Chilkur Balaji temple?"),
        ("yadadri", "Yadadri", "What are the timings of the indoor snow skiing resort at Yadadri temple?"),
        ("dharmapuri", "Dharmapuri", "Where is the scuba diving training center located inside Dharmapuri temple?"),
        ("edupayal", "Edupayal", "Can visitors book submarine rides at Edupayal temple?"),
        ("vemulavada", "Vemulavada", "What is the entry fee for the roller coaster theme park at Vemulawada temple?"),
        ("badrachalam", "Badrachalam", "How to rent luxury yachts for private parties at Bhadrachalam temple?"),
        ("ramappa", "Ramappa", "What are the booking prices for hot air balloon safari over Ramappa temple?"),
        ("thousand pillar", "Thousand Pillar", "Where can I buy tickets for the underwater aquarium at Thousand Pillar temple?"),
        ("birla mandir", "Birla Mandir", "What is the schedule of Formula 1 car racing around Birla Mandir?"),
        ("karmanghat", "Karmanghat", "What is the fee for ice skating rink at Karmanghat Hanuman temple?"),
        ("ujjaini", "Ujjaini", "How to book private jet landing permissions inside Ujjaini Mahakali temple?"),
        ("medaram", "Medaram", "What is the tariff for presidential suites in the 7-star casino hotel at Medaram?"),
        ("ahobilam", "Ahobilam", "Where is the bungee jumping platform located at Ahobilam temple?")
    ]
    
    for n_id, n_temple, n_q in negative_templates:
        all_questions.append({
            "id": f"neg_{n_id}",
            "temple_id": n_id,
            "temple_name": n_temple,
            "category": "negative_unanswerable",
            "question": n_q,
            "expected_answer": "Information not available in temple records. The temple does not provide this facility.",
            "source_files": [],
            "source_fields": [],
            "answerable": False,
            "difficulty": "medium",
            "test_type": "negative_unanswerable"
        })

    # Summary stats
    cat_counts = {}
    diff_counts = {}
    temple_counts = {}
    
    for q in all_questions:
        cat = q["category"]
        diff = q["difficulty"]
        tid = q["temple_id"]
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        diff_counts[diff] = diff_counts.get(diff, 0) + 1
        temple_counts[tid] = temple_counts.get(tid, 0) + 1

    dataset_payload = {
        "metadata": {
            "random_seed": RANDOM_SEED,
            "total_temples": len(temple_folders),
            "total_questions": len(all_questions),
            "answerable_questions": len([q for q in all_questions if q["answerable"]]),
            "unanswerable_questions": len([q for q in all_questions if not q["answerable"]]),
            "category_distribution": cat_counts,
            "difficulty_distribution": diff_counts,
            "temple_question_counts": temple_counts,
            "temple_metadata": temple_metadata
        },
        "questions": all_questions
    }
    
    out_dir = root_dir / "evaluation"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    out_file = out_dir / "evaluation_dataset.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(dataset_payload, f, indent=2, ensure_ascii=False)
        
    meta_file = out_dir / "metadata.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(temple_metadata, f, indent=2, ensure_ascii=False)
        
    print(f"[OK] Generated {len(all_questions)} evaluation questions across {len(temple_folders)} temples.")
    print(f"Saved dataset to: {out_file}")
    return dataset_payload

if __name__ == "__main__":
    generate_evaluation_dataset()
