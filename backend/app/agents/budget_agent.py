"""
PilgrimAI - BudgetAgent (Phase O4)

Specialist agent calculating grounded, deterministic pilgrimage costs from verified
temple records and explicit user-provided inputs.

Core Principles:
- 100% Grounded Arithmetic: Calculations derive strictly from verified temple records
  (sevas, accommodation, prasadam, timings, restaurants) and user-provided costs.
- Cost Provenance Classification: Every cost is explicitly tagged:
  VERIFIED, USER_PROVIDED, CALCULATED, ESTIMATE, or UNAVAILABLE.
- Absolute No-Hallucination: Missing prices are flagged as UNAVAILABLE; never guessed or
  silently substituted with generic amounts.
- Unit Safety: Prices are multiplied by people or nights only when the pricing unit
  logically supports it (e.g., 'per person', 'per night', 'per room').
- Range Preservation: Minimum and maximum bounds are strictly preserved throughout calculation.
- RAGTool Facade: Accesses temple facts exclusively via read-only RAGTool interface
  (get_temple_category_data). Zero direct database or raw JSON file imports.
- Zero External API / Credentials: ₹0 cost, zero API keys required.
"""

import re
import html
import time
import logging
import urllib.parse
from enum import Enum
from typing import Dict, Any, Optional, List, Tuple, Union
from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState, AgentResponse

logger = logging.getLogger(__name__)


# =====================================================================
# Provenance Model
# =====================================================================

class CostProvenance(str, Enum):
    """Explicit provenance classification for all pilgrimage expenditure items."""
    VERIFIED = "VERIFIED"             # Directly from verified temple records
    USER_PROVIDED = "USER_PROVIDED"   # Explicitly supplied by the user
    CALCULATED = "CALCULATED"         # Mathematically derived from verified/user values
    ESTIMATE = "ESTIMATE"             # Clearly identified approximation grounded in data
    UNAVAILABLE = "UNAVAILABLE"       # Price not in records and not supplied by user


class BudgetItem(BaseModel):
    """Structured representation of a single pilgrimage expense line item."""
    category: str = Field(..., description="Category (sevas, accommodation, prasadam, travel, entry, restaurants)")
    item_name: str = Field(..., description="Name of the service, room, or expense")
    min_cost: Optional[float] = Field(default=None, description="Minimum numeric cost in INR")
    max_cost: Optional[float] = Field(default=None, description="Maximum numeric cost in INR")
    currency: str = Field(default="INR", description="Currency identifier")
    unit: str = Field(default="per service", description="Pricing basis (per person, per room, per night, per item, fixed)")
    is_free: bool = Field(default=False, description="Whether the item is confirmed free of charge")
    is_range: bool = Field(default=False, description="Whether the cost represents a variable range")
    is_quantified: bool = Field(default=True, description="Whether numeric cost bounds are established")
    provenance: CostProvenance = Field(default=CostProvenance.VERIFIED, description="Data provenance")
    raw_price_str: str = Field(default="", description="Original raw price text from source or user")
    source_path: str = Field(default="", description="Source file or origin identifier")
    notes: str = Field(default="", description="Qualifying notes or conditions")
    property_type: Optional[str] = Field(default=None, description="Property or room type")
    distance: Optional[str] = Field(default=None, description="Distance from temple")
    tier: Optional[str] = Field(default=None, description="Budget classification tier: Budget, Standard / Comfort, Premium")
    stay_cost_min: Optional[float] = Field(default=None, description="Full stay minimum cost")
    stay_cost_max: Optional[float] = Field(default=None, description="Full stay maximum cost")
    stay_nights: Optional[int] = Field(default=None, description="Overnight stays accounted for")
    stay_rooms: Optional[int] = Field(default=None, description="Rooms accounted for")
    temple: Optional[str] = Field(default=None, description="Associated canonical temple identifier")
    destination: Optional[str] = Field(default=None, description="Display name of the destination")
    is_recommended: bool = Field(default=False, description="Whether this property is the recommended option for this destination")
    recommendation_label: Optional[str] = Field(default=None, description="Label e.g. Recommended for Dharmapuri")


# =====================================================================
# Canonical Temple Mapping & Aliases (Aligned with KnowledgeRegistry)
# =====================================================================

TEMPLE_CANONICAL_MAP = {
    "ahobilam": "Ahobilam",
    "ahobila": "Ahobilam",
    "badrachalam": "Badrachalam",
    "bhadrachalam": "Badrachalam",
    "balkampet": "Balkampet",
    "basara": "Basara",
    "basar": "Basara",
    "basara_gnana_saraswathi": "Basara",
    "gnana saraswathi": "Basara",
    "birla mandir": "Birla Mandir",
    "birla": "Birla Mandir",
    "chilkur": "Chilkur",
    "chilkur balaji": "Chilkur",
    "visa balaji": "Chilkur",
    "dharmapuri": "Dharmapuri",
    "dharmapuri_lakshmi_narasimha": "Dharmapuri",
    "edupayal": "Edupayal",
    "edupayala": "Edupayal",
    "edupayala_durga_bhavani": "Edupayal",
    "jogulamba": "Jogulamba(New)",
    "jogulamba(new)": "Jogulamba(New)",
    "alampur": "Jogulamba(New)",
    "kaleshvaram": "Kaleshvaram",
    "kaleshwaram": "Kaleshvaram",
    "mukteshwara": "Kaleshvaram",
    "karmanghat": "Karmanghat",
    "medaram": "Medaram",
    "ramappa": "Ramappa",
    "srisaila": "Srisaila",
    "srisailam": "Srisaila",
    "thousand pillar": "Thousand Pillar",
    "thousand pillars": "Thousand Pillar",
    "ttd": "Ttd",
    "tirupati": "Ttd",
    "tirumala": "Ttd",
    "ujjaini": "Ujjaini",
    "ujjaini mahakali": "Ujjaini",
    "ujjaini mahankali": "Ujjaini",
    "veera satyanarayana": "Veera Satyanarayana",
    "annavaram": "Veera Satyanarayana",
    "vemulavada": "Vemulavada",
    "vemulawada": "Vemulavada",
    "yadadri": "Yadadri",
    "yadagirigutta": "Yadadri"
}

TEMPLE_DISPLAY_NAMES = {
    "Ahobilam": "Ahobilam Narasimha Swamy",
    "Badrachalam": "Bhadrachalam Sree Seetha Ramachandra Swamy",
    "Balkampet": "Balkampet Yellamma",
    "Basara": "Basara Gnana Saraswathi",
    "Birla Mandir": "Birla Mandir",
    "Chilkur": "Chilkur Balaji",
    "Dharmapuri": "Dharmapuri Lakshmi Narasimha",
    "Edupayal": "Edupayala Vana Durga Bhavani",
    "Jogulamba(New)": "Alampur Jogulamba",
    "Kaleshvaram": "Kaleshwaram Mukteshwara Swamy",
    "Karmanghat": "Karmanghat Hanuman",
    "Medaram": "Medaram Sammakka Saralamma",
    "Ramappa": "Ramappa Temple",
    "Srisaila": "Srisailam Mallikarjuna",
    "Thousand Pillar": "Thousand Pillar Temple",
    "Ttd": "Tirumala Tirupati Devasthanam",
    "Ujjaini": "Ujjaini Mahakali",
    "Veera Satyanarayana": "Annavaram Veera Venkata Satyanarayana",
    "Vemulavada": "Vemulawada Raja Rajeshwara",
    "Yadadri": "Yadadri Lakshmi Narasimha"
}


# =====================================================================
# Deterministic Price Parser
# =====================================================================

def parse_price_text(
    price_str: str,
    category: str = "general"
) -> Tuple[Optional[float], Optional[float], str, bool, bool, bool, str]:
    """
    Deterministically parses human-readable price strings into structured pricing bounds.
    
    Returns:
        (min_value, max_value, unit_text, is_free, is_range, is_quantified, notes)
    """
    if not price_str or not isinstance(price_str, str):
        return (None, None, "per service", False, False, False, "Price not specified")

    clean_str = price_str.strip()
    s_lower = clean_str.lower()

    # 1. Check for explicit confirmed free
    has_free_word = any(w in s_lower for w in ["free", "no ticket required", "0/-", "zero", "complimentary"])
    if has_free_word:
        # Verify it is not "free general, ₹500 special"
        if not re.search(r"[1-9]\d{1,6}", s_lower):
            return (0.0, 0.0, "per person", True, False, True, "Free of charge")

    # 2. Check if string solely conveys distance, transit, or physical metrics without currency
    is_distance_only = bool(re.search(r'\b(?:km|kms|k\.m\.|kilometer|kilometers|meter|meters|mtr|mtrs|miles?|ft|feet)\b', s_lower)) and not bool(re.search(r'(?:₹|rs\.?|inr|/-|rupees?|\bfree\b)', s_lower))
    if is_distance_only:
        return (None, None, "per room per night" if category == "accommodation" else "per service", False, False, False, f"Distance measurement ({clean_str}), not a quantified tariff")

    # 3. Check for explicit unquantified/variable indicators without concrete numbers
    unquantified_markers = ["varies", "nominal fee", "contact office", "not specified", "endowment fund", "subject to change", "variable contribution"]
    has_unquantified_marker = any(m in s_lower for m in unquantified_markers)

    # Clean commas inside numbers: e.g. 1,000 -> 1000
    num_clean = re.sub(r'(?<=\d),(?=\d)', '', s_lower)

    # 4. Detect pricing unit
    unit_text = "per service"
    if "per person" in s_lower or "per head" in s_lower or "each person" in s_lower or "/person" in s_lower:
        unit_text = "per person"
    elif "per couple" in s_lower or "for couple" in s_lower or "2 persons" in s_lower:
        unit_text = "per couple"
    elif "per room" in s_lower and ("night" in s_lower or "/night" in s_lower):
        unit_text = "per room per night"
    elif "per night" in s_lower or "/night" in s_lower or "a night" in s_lower:
        unit_text = "per room per night"
    elif "per room" in s_lower:
        unit_text = "per room"
    elif category.lower() == "accommodation":
        if "per person" in s_lower or "per bed" in s_lower or "per head" in s_lower:
            unit_text = "per person"
        elif "per hour" in s_lower or "/hour" in s_lower:
            unit_text = "per hour"
        else:
            unit_text = "per room per night"
    elif category.lower() == "prasadam" or "per packet" in s_lower or "per laddu" in s_lower or "per piece" in s_lower:
        unit_text = "per item"
    elif "per vehicle" in s_lower:
        unit_text = "per vehicle"

    # 5. Extract numeric values, carefully stripping out non-currency units (distance, time, weight, count)
    num_clean_for_pricing = re.sub(
        r'\b\d+(?:\.\d+)?\s*(?:km|kms|k\.m\.|kilometer|kilometers|meter|meters|mtr|mtrs|miles?|ft|feet|bed|beds|hour|hours|hr|hrs|am|pm|min|mins|minutes?|kg|g|gm|people|person|persons)\b',
        ' ',
        num_clean
    )
    found_nums = [float(n) for n in re.findall(r'\b\d+(?:\.\d+)?\b', num_clean_for_pricing)]

    # Filter out extraneous numbers like times or stray non-pricing numbers
    filtered_nums = []
    for n in found_nums:
        # Avoid stray single digits in non-currency contexts
        filtered_nums.append(n)

    if not filtered_nums:
        if has_unquantified_marker:
            return (None, None, unit_text, False, False, False, clean_str)
        return (None, None, unit_text, False, False, False, "Price unquantified in records")

    if len(filtered_nums) == 1:
        val = filtered_nums[0]
        if has_free_word and category == "entry":
            return (0.0, val, unit_text, False, True, True, clean_str)
        return (val, val, unit_text, val == 0.0, False, True, clean_str)

    # Two or more numbers: evaluate if it represents a range (e.g. 100 - 300, 100 to 300)
    range_match = re.search(
        r'(\d+(?:\.\d+)?)\s*(?:-|–|—|to)\s*(?:rs\.?|inr|₹)?\s*(\d+(?:\.\d+)?)',
        num_clean_for_pricing
    )
    if range_match:
        val1 = float(range_match.group(1))
        val2 = float(range_match.group(2))
        min_v = 0.0 if (has_free_word and category == "entry") else min(val1, val2)
        max_v = max(val1, val2)
        return (min_v, max_v, unit_text, False, True, True, clean_str)

    # Fallback for multiple numbers without explicit range syntax
    min_v = 0.0 if (has_free_word and category == "entry") else min(filtered_nums)
    max_v = max(filtered_nums)
    return (min_v, max_v, unit_text, False, min_v != max_v, True, clean_str)



# =====================================================================
# Parameter Extraction
# =====================================================================

def normalize_accommodation_tier(val: Optional[str]) -> Optional[str]:
    """
    Normalizes accommodation tier preference to one of:
    'Budget', 'Standard / Comfort', 'Premium', 'none', or None.
    """
    if not val or not isinstance(val, str):
        return None
    v = val.strip().lower()
    if v in ["none", "no accommodation", "no_accommodation", "without accommodation", "no stay", "no hotel", "without stay", "no lodging"]:
        return "none"
    if any(k in v for k in ["budget", "economy", "dharamshala", "satram", "choultry"]):
        return "Budget"
    if any(k in v for k in ["standard", "comfort", "guest house"]):
        return "Standard / Comfort"
    if any(k in v for k in ["premium", "luxury", "vip", "resort", "cottage"]):
        return "Premium"
    if v in ["any", "all", "no preference", ""]:
        return None
    return None


def extract_budget_parameters(
    query: str,
    structured_constraints: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Deterministically extracts user parameters:
    - group size / persons (default: 1)
    - duration / days (default: 1)
    - nights count (distinguished from days)
    - room count (default: 1)
    - user-provided costs (e.g. travel, hotel, food)
    - specific seva requests (dynamically or from query)
    - accommodation requests & preference (Budget, Standard / Comfort, Premium, none)
    """
    q_norm = query.lower()

    # 1. Group size / Persons
    pax = 1
    pax_assumed = True
    if structured_constraints and structured_constraints.get("pax"):
        try:
            pax = max(1, int(structured_constraints["pax"]))
            pax_assumed = False
        except (ValueError, TypeError):
            pass

    pax_match = re.search(r"\b(\d+)\s*(?:people|persons?|devotees?|members?|pilgrims?|adults?)\b", q_norm)
    if pax_match:
        pax = max(1, int(pax_match.group(1)))
        pax_assumed = False
    elif pax_assumed:
        family_match = re.search(r"\b(?:family of|group of)\s*(\d+)\b", q_norm)
        if family_match:
            pax = max(1, int(family_match.group(1)))
            pax_assumed = False
        elif any(w in q_norm for w in ["couple", "two of us", "for 2", "for two", "for 2 people", "for two devotees"]):
            pax = 2
            pax_assumed = False
        elif any(w in q_norm for w in ["for 3", "for three"]):
            pax = 3
            pax_assumed = False
        elif any(w in q_norm for w in ["for 4", "for four"]):
            pax = 4
            pax_assumed = False

    # 2. Duration / Days & Nights
    days = 1
    days_assumed = True
    nights = 0
    nights_explicit = False

    if structured_constraints:
        sc_days = structured_constraints.get("duration_days") or structured_constraints.get("days")
        if sc_days:
            try:
                days = max(1, int(sc_days))
                days_assumed = False
                nights = max(0, days - 1)
            except (ValueError, TypeError):
                pass
        if structured_constraints.get("nights") is not None:
            try:
                nights = max(0, int(structured_constraints["nights"]))
                nights_explicit = True
            except (ValueError, TypeError):
                pass

    # Check for accommodation-specific duration request e.g. "AC Deluxe Room accommodation at Yadadri for 2 days"
    is_accom_specific_duration = bool(
        re.search(r"\b(?:accommodation|hotel|stay|room|rooms|lodge|cottage)\b.*?\bfor\s+(\d+)\s*days?\b", q_norm) or
        re.search(r"\bfor\s+(\d+)\s*days?\b.*?\b(?:accommodation|hotel|stay|room|rooms|lodge|cottage)\b", q_norm)
    ) and not bool(re.search(r"\b(?:trip|tour|itinerary|visit|pilgrimage)\b", q_norm))

    # Check for explicit nights
    night_match = re.search(r"\b(\d+)\s*[- ]*(?:nights?|night)\b", q_norm)
    if night_match:
        nights = max(1, int(night_match.group(1)))
        nights_explicit = True
        days = nights + 1
        days_assumed = False
    elif is_accom_specific_duration:
        m_acc_days = re.search(r"\bfor\s+(\d+)\s*days?\b", q_norm) or re.search(r"\b(\d+)\s*days?\b", q_norm)
        if m_acc_days:
            days = max(1, int(m_acc_days.group(1)))
            nights = days
            nights_explicit = True
            days_assumed = False
    elif "weekend" in q_norm:
        days = 2
        nights = 1
        days_assumed = False
    else:
        day_match = re.search(r"\b(\d+)\s*[- ]*(?:days?|day)\b", q_norm)
        if day_match:
            days = max(1, int(day_match.group(1)))
            days_assumed = False
            nights = max(0, days - 1)
        elif any(w in q_norm for w in [
            "one day", "1 day", "single day", "one-day", "for 1 day", "for one day",
            "single-day", "1-day", "day visit", "day trip", "single day trip", "single day visit"
        ]):
            days = 1
            nights = 0
            days_assumed = False
        elif any(w in q_norm for w in ["two days", "2 days", "two day", "two-day", "for 2 days", "for two days", "2 day"]):
            days = 2
            nights = 1
            days_assumed = False
        elif any(w in q_norm for w in ["three days", "3 days", "three day", "three-day", "for 3 days", "for three days"]):
            days = 3
            nights = 2
            days_assumed = False
        elif any(w in q_norm for w in ["four days", "4 days", "four day", "four-day"]):
            days = 4
            nights = 3
            days_assumed = False

    # 3. Room count
    room_match = re.search(r"\b(\d+)\s*rooms?\b", q_norm)
    if room_match:
        rooms = max(1, int(room_match.group(1)))
        rooms_assumed = False
    else:
        # Standard pilgrimage room occupancy: up to 2 persons per room
        if pax >= 3:
            rooms = max(1, (pax + 1) // 2)
            rooms_assumed = True
        else:
            rooms = 1
            rooms_assumed = True

    # 4. Budget limit extraction
    budget_limit = None
    b_match = re.search(
        r"(?:budget\s+(?:of\s+|is\s+|limit\s+(?:is\s+|of\s+)?)?|under\s+(?:a\s+budget\s+of\s+)?|within\s+(?:a\s+budget\s+of\s+)?|below\s+(?:a\s+budget\s+of\s+)?|with\s+(?:a\s+)?budget\s+(?:of\s+)?|have\s+)(?:rs\.?|inr|₹)?\s*(\d+(?:,\d+)?(?:\.\d+)?)\b",
        q_norm
    )
    if b_match:
        budget_limit = float(b_match.group(1).replace(",", ""))
    else:
        b_match2 = re.search(
            r"(?:(?:rs\.?|inr|₹)\s*(\d+(?:,\d+)?(?:\.\d+)?)\s*(?:budget|limit)|(?:^|\s)with\s+(?:rs\.?|inr|₹)?\s*(\d+(?:,\d+)?(?:\.\d+)?)\s*budget)",
            q_norm
        )
        if b_match2:
            val_str = b_match2.group(1) or b_match2.group(2)
            if val_str:
                budget_limit = float(val_str.replace(",", ""))

    if budget_limit is None:
        # Check patterns like "with ₹3000", "with 3000 rupees", "with 3000", "within 3000", "under 3000"
        b_match3 = re.search(
            r"\b(?:with|under|within|around|upto|up\s+to|max|maximum|cap\s+of|budget\s+of)\s*(?:rs\.?|inr|₹|rupees?)?\s*(\d+(?:,\d+)?(?:\.\d+)?)\s*(?:rs\.?|inr|₹|rupees?)?\b",
            q_norm
        )
        if b_match3:
            budget_limit = float(b_match3.group(1).replace(",", ""))
        else:
            # Check standalone currency amount like "₹3000" or "3000 rupees" in budget query
            b_match4 = re.search(
                r"(?:(?:rs\.?|inr|₹)\s*(\d+(?:,\d+)?(?:\.\d+)?)|(\d+(?:,\d+)?(?:\.\d+)?)\s*(?:rs\.?|inr|₹|rupees))\b",
                q_norm
            )
            if b_match4:
                val_str = b_match4.group(1) or b_match4.group(2)
                if val_str:
                    budget_limit = float(val_str.replace(",", ""))

    if budget_limit is None and structured_constraints and structured_constraints.get("budget_limit") is not None:
        try:
            budget_limit = float(structured_constraints["budget_limit"])
        except (ValueError, TypeError):
            pass


    # 5. Accommodation requested & tier preference
    accom_tier_pref = None
    if structured_constraints and structured_constraints.get("accommodation_preference"):
        accom_tier_pref = normalize_accommodation_tier(structured_constraints.get("accommodation_preference"))

    if not accom_tier_pref:
        if re.search(r"\b(?:no\s+(?:accommodation|hotel|stay|room|rooms|lodging)|without\s+(?:accommodation|hotel|stay|room|rooms|lodging)|no\s+overnight\s+stay)\b", q_norm):
            accom_tier_pref = "none"
        elif re.search(r"\b(?:budget\s+(?:accommodation|hotel|stay|tier|room|lodge)|budget-friendly\s+(?:stay|hotel|accommodation)|economy\s+(?:stay|accommodation|hotel))\b", q_norm) or re.search(r"\bwith\s+budget\s+accommodation\b", q_norm):
            accom_tier_pref = "Budget"
        elif re.search(r"\b(?:standard\s*(?:/\s*comfort)?\s+(?:accommodation|hotel|stay|tier|room)|comfort\s+(?:accommodation|hotel|stay|tier|room))\b", q_norm) or re.search(r"\bwith\s+standard(?:\s*/\s*comfort)?\s+accommodation\b", q_norm):
            accom_tier_pref = "Standard / Comfort"
        elif re.search(r"\b(?:premium\s+(?:accommodation|hotel|stay|tier|room|cottage)|luxury\s+(?:accommodation|hotel|stay|tier|room)|vip\s+(?:cottage|accommodation|room))\b", q_norm) or re.search(r"\bwith\s+premium\s+accommodation\b", q_norm):
            accom_tier_pref = "Premium"

    no_accom = (accom_tier_pref == "none") or any(re.search(p, q_norm) for p in [
        r"\bno\s+(?:accommodation|hotel|stay|room|rooms|lodging)\b",
        r"\bwithout\s+(?:accommodation|hotel|stay|room|rooms|lodging)\b",
        r"\b(?:don'?t|do\s+not)\s+need\s+(?:accommodation|hotel|stay|room)\b",
        r"\b(?:1|one|single)?\s*day\s+visit\b",
        r"\b(?:1|one|single)?\s*day\s+trip\b" if days <= 1 else r"\b(?!x)x\b"
    ])

    if no_accom:
        accom_tier_pref = "none"
        nights = 0
        accom_requested = False
    else:
        accom_requested = nights_explicit or (nights > 0) or any(w in q_norm for w in [
            "stay", "room", "rooms", "hotel", "hotels", "accommodation",
            "cottage", "cottages", "choultry", "guest house", "night", "nights",
            "dormitory", "including accommodation", "with accommodation", "including stay"
        ]) or (accom_tier_pref in ["Budget", "Standard / Comfort", "Premium"])

    accom_type = None
    if "non-ac" in q_norm or "non ac" in q_norm or "non_ac" in q_norm:
        accom_type = "non_ac"
    elif re.search(r"\bac\b", q_norm) or "deluxe" in q_norm:
        accom_type = "ac"
    elif "cottage" in q_norm:
        accom_type = "cottage"
    elif "dormitory" in q_norm or "choultry" in q_norm:
        accom_type = "dormitory"

    # Transport and Food preferences
    transport_pref = None
    if structured_constraints and structured_constraints.get("transport_preference"):
        transport_pref = str(structured_constraints.get("transport_preference")).lower()
    elif "bus" in q_norm or "tsrtc" in q_norm:
        transport_pref = "bus"
    elif "train" in q_norm or "railway" in q_norm:
        transport_pref = "train"
    elif any(k in q_norm for k in ["car", "taxi", "cab", "driving"]):
        transport_pref = "car"

    food_pref = None
    if structured_constraints and structured_constraints.get("food_preference"):
        food_pref = str(structured_constraints.get("food_preference")).lower()
    elif "prasadam" in q_norm or "annadanam" in q_norm:
        food_pref = "prasadam"
    elif any(k in q_norm for k in ["restaurant", "dining", "outside food"]):
        food_pref = "dining"

    # Override budget limit / pax / origin from structured_constraints if explicitly provided
    if structured_constraints:
        if structured_constraints.get("budget_limit") is not None:
            budget_limit = float(structured_constraints["budget_limit"])
        if structured_constraints.get("pax"):
            pax = int(structured_constraints["pax"])
            pax_assumed = False
            if pax >= 3:
                rooms = max(1, (pax + 1) // 2)
            else:
                rooms = 1
        if structured_constraints.get("duration_days"):
            days = int(structured_constraints["duration_days"])
            days_assumed = False
            if not no_accom:
                nights = max(0, days - 1)
        if structured_constraints.get("origin"):
            origin = str(structured_constraints["origin"]).strip().title()

    # 6. Specific Seva extraction
    specific_seva = None
    known_sevas = [
        "nitya kalyanam", "kalyanotsavam", "kalyanam",
        "nijabhishekam", "abhishekam",
        "aksharabhyasam", "special aksharabhyasam",
        "sudarshana homam", "homam",
        "sahasranamarchana", "archana",
        "special darshan", "vip darshan", "sheegra darshanam", "seeghra darshanam"
    ]
    for ks in known_sevas:
        if re.search(r"\b" + re.escape(ks) + r"\b", q_norm):
            specific_seva = ks
            break

    # 7. User-provided explicit costs
    user_costs: List[BudgetItem] = []

    # Travel user cost
    travel_match = re.search(
        r"\b(?:my\s+)?(?:travel|transit|bus|train|cab|taxi|flight|transport|fare)(?:\s+(?:cost|expenses?|fare))?(?:\s+(?:is|will\s+be|estimated\s+at|=|:))?\s*(?:rs\.?|inr|₹)?\s*(\d+(?:,\d+)?(?:\.\d+)?)(?!\s*(?:km|kms|k\.m\.|kilometer|kilometers|meter|meters|miles?|ft|feet|hours?|hrs?|mins?|minutes?|days?|nights?))\b",
        q_norm
    )
    if travel_match:
        val = float(travel_match.group(1).replace(",", ""))
        user_costs.append(BudgetItem(
            category="travel",
            item_name="Travel / Transit (User Provided)",
            min_cost=val,
            max_cost=val,
            unit="fixed",
            is_free=val == 0.0,
            is_quantified=True,
            provenance=CostProvenance.USER_PROVIDED,
            raw_price_str=travel_match.group(0),
            notes="Explicitly supplied by user"
        ))

    # Hotel / Accommodation user cost
    hotel_match = re.search(
        r"\b(?:my\s+)?(?:hotel|room|accommodation|stay|lodge)(?:\s+(?:cost|tariff|rate|expense))?(?:\s+(?:is|will\s+be|=|:))?\s*(?:rs\.?|inr|₹)?\s*(\d+(?:,\d+)?(?:\.\d+)?)\b",
        q_norm
    )
    if hotel_match:
        val = float(hotel_match.group(1).replace(",", ""))
        user_costs.append(BudgetItem(
            category="accommodation",
            item_name="Accommodation / Stay (User Provided)",
            min_cost=val,
            max_cost=val,
            unit="fixed",
            is_free=val == 0.0,
            is_quantified=True,
            provenance=CostProvenance.USER_PROVIDED,
            raw_price_str=hotel_match.group(0),
            notes="Explicitly supplied by user"
        ))

    # Food user cost
    food_match = re.search(
        r"\b(?:my\s+)?(?:food|meals?|dining|prasadam|lunch|dinner|breakfast)(?:\s+(?:cost|expense))?(?:\s+(?:is|will\s+be|=|:))?\s*(?:rs\.?|inr|₹)?\s*(\d+(?:,\d+)?(?:\.\d+)?)\b",
        q_norm
    )
    if food_match:
        val = float(food_match.group(1).replace(",", ""))
        user_costs.append(BudgetItem(
            category="prasadam",
            item_name="Food / Meals (User Provided)",
            min_cost=val,
            max_cost=val,
            unit="fixed",
            is_free=val == 0.0,
            is_quantified=True,
            provenance=CostProvenance.USER_PROVIDED,
            raw_price_str=food_match.group(0),
            notes="Explicitly supplied by user"
        ))

    # 8. Origin extraction (if specified by user e.g. "from hyderabad", "from vijayawada, andhra pradesh to ...")
    origin = None
    from_to_match = re.search(r"\bfrom\s+(.+?)\s+to\s+", query, re.IGNORECASE)
    if from_to_match:
        cand_orig = from_to_match.group(1).strip()
        cand_clean = re.sub(r"^(?:the|a|an|my\s+home|my\s+place|my\s+city)\s+", "", cand_orig, flags=re.IGNORECASE).strip()
        cand_clean = cand_clean.rstrip(",;.").strip()
        if cand_clean and len(cand_clean.split()) <= 5:
            origin = cand_clean.title()
    if not origin:
        orig_match = re.search(r"\bfrom\s+([a-zA-Z]+(?:\s*,\s*[a-zA-Z]+|\s+[a-zA-Z]+)?)\b", query, re.IGNORECASE)
        if orig_match:
            cand_orig = orig_match.group(1).strip().rstrip(",;.")
            if cand_orig.lower() not in ["the", "a", "an", "this", "our", "my", "some", "any", "which", "me"]:
                origin = cand_orig.title()

    return {
        "pax": pax,
        "pax_assumed": pax_assumed,
        "days": days,
        "days_assumed": days_assumed,
        "nights": nights,
        "rooms": rooms,
        "rooms_assumed": rooms_assumed,
        "budget_limit": budget_limit,
        "accom_requested": accom_requested,
        "accom_type": accom_type,
        "accommodation_preference": accom_tier_pref,
        "transport_preference": transport_pref,
        "food_preference": food_pref,
        "no_accom": no_accom,
        "specific_seva": specific_seva,
        "user_costs": user_costs,
        "origin": origin
    }


# =====================================================================
# BudgetAgent Implementation
# =====================================================================

class BudgetAgent(BaseAgent):
    """
    Specialist agent providing deterministic, grounded pilgrimage budget estimation
    and itemized cost analysis across canonical pilgrimage temples.
    """

    def __init__(
        self,
        rag_tool: Optional[Any] = None,
        name: str = "budget",
        description: str = "Specialist agent calculating grounded pilgrimage budgets and itemized cost breakdowns using verified temple records and user-supplied parameters.",
        navigation_adapter: Optional[Any] = None,
        coordinate_registry: Optional[Any] = None
    ):
        super().__init__(name=name, description=description)
        self._rag_tool = rag_tool
        self._navigation_adapter = navigation_adapter
        self._coordinate_registry = coordinate_registry

    @property
    def rag_tool(self) -> Any:
        """Lazily initialize RAGTool to avoid circular instantiation loops."""
        if self._rag_tool is None:
            from app.agents.tools.rag_tool import RAGTool
            self._rag_tool = RAGTool()
        return self._rag_tool

    @rag_tool.setter
    def rag_tool(self, value: Any) -> None:
        self._rag_tool = value

    @property
    def navigation_adapter(self) -> Any:
        """Lazily initialize NavigationAdapter."""
        if self._navigation_adapter is None:
            from app.agents.adapters.navigation_adapter import NavigationAdapter
            self._navigation_adapter = NavigationAdapter()
        return self._navigation_adapter

    @navigation_adapter.setter
    def navigation_adapter(self, value: Any) -> None:
        self._navigation_adapter = value

    @property
    def coordinate_registry(self) -> Any:
        """Lazily initialize TempleCoordinateRegistry."""
        if self._coordinate_registry is None:
            from app.agents.coordinate_registry import TempleCoordinateRegistry
            self._coordinate_registry = TempleCoordinateRegistry()
        return self._coordinate_registry

    @coordinate_registry.setter
    def coordinate_registry(self, value: Any) -> None:
        self._coordinate_registry = value

    def _resolve_location(self, place_name: Optional[str]) -> Tuple[str, Optional[Tuple[float, float]], Optional[str]]:
        """Resolves place name to (display_name, coordinates, canonical_name)."""
        if not place_name:
            return "", None, None
        temple_coord = self.coordinate_registry.get_coordinate(place_name)
        if temple_coord is not None:
            return (
                temple_coord.display_name or temple_coord.canonical_name,
                (temple_coord.latitude, temple_coord.longitude),
                temple_coord.canonical_name
            )
        return place_name.strip().title(), None, None

    def _is_return_requested(self, query: str, origin: Optional[str] = None) -> bool:
        """Determines whether a return route was explicitly requested by user."""
        if not query:
            return False
        if re.search(r"\b(?:round[- ]*trip|roundtrip|both\s+ways|and\s+back)\b", query, re.IGNORECASE):
            return True
        if re.search(r"\b(?:return\s+(?:journey|trip|leg)|returning\s+home)\b", query, re.IGNORECASE):
            return True
        if re.search(r"\b(?:back|return|returning)\s+to\s+(?:the\s+)?(?:starting|origin|start)\s*(?:city|town|place|location|point)?\b", query, re.IGNORECASE):
            return True
        if origin:
            clean_origin = re.sub(r"[,;.]+", "", origin).strip()
            first_orig_word = clean_origin.split()[0] if clean_origin else origin
            if re.search(rf"\b(?:return|returning|back)\s+to\s+{re.escape(clean_origin)}\b", query, re.IGNORECASE):
                return True
            if re.search(rf"\b(?:return|returning|back)\s+to\s+{re.escape(first_orig_word)}\b", query, re.IGNORECASE):
                return True
            _, _, orig_canon = self._resolve_location(origin)
            if orig_canon and re.search(rf"\b(?:return|returning|back)\s+to\s+{re.escape(orig_canon)}\b", query, re.IGNORECASE):
                return True
            m_back = re.search(r"\b(?:back|return|returning)\s+to\s+([a-zA-Z\s]+?)(?:\s+(?:with|for|\d+|\b)|$)", query, re.IGNORECASE)
            if m_back:
                cand_dest = m_back.group(1).strip().lower()
                if cand_dest and (clean_origin.lower() in cand_dest or cand_dest in clean_origin.lower()):
                    return True
        return False

    @staticmethod
    def _parse_duration_seconds(duration_str: Any) -> Optional[float]:
        """Parses Google Routes API duration string (e.g. '1234s' or '123.4s') into float seconds."""
        if not duration_str:
            return None
        m = re.match(r"^([\d.]+)s$", str(duration_str).strip())
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                return None
        return None

    @staticmethod
    def _format_duration_human(minutes: Optional[float]) -> str:
        """Formats duration in minutes into a human-readable string."""
        if minutes is None:
            return "N/A"
        total_mins = int(round(minutes))
        if total_mins < 60:
            return f"{total_mins} min"
        hours = total_mins // 60
        rem_mins = total_mins % 60
        if rem_mins == 0:
            return f"{hours} hr"
        return f"{hours} hr {rem_mins} min"

    def process(self, state: AgentState) -> AgentResponse:
        """Alias to execute for consistent agent invocation across callers."""
        return self.execute(state)

    def _extract_parameters(self, query: str, structured_constraints: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Deterministically extracts user parameters via extract_budget_parameters."""
        return extract_budget_parameters(query, structured_constraints=structured_constraints)

    def _get_dynamic_canonical_map(self) -> Dict[str, str]:
        """
        Dynamically builds an alias-to-canonical mapping using registered temples
        from RAGTool / KnowledgeRegistry and query planner aliases, falling back
        to TEMPLE_CANONICAL_MAP. Automatically supports future temples.
        """
        combined: Dict[str, str] = dict(TEMPLE_CANONICAL_MAP)
        try:
            registered = self.rag_tool.get_registered_temples()
            for r in registered:
                combined[r.lower().strip()] = r
                clean_name = r.lower().replace(" ", "_").replace("-", "_").replace("(", "").replace(")", "")
                combined[clean_name] = r
            
            # Incorporate aliases from query planner
            planner = getattr(getattr(self.rag_tool, "_rag_service", None), "query_planner", None)
            if planner and hasattr(planner, "temple_aliases"):
                for c_id, a_list in planner.temple_aliases.items():
                    for alias in a_list:
                        combined[alias.lower().strip()] = c_id
        except Exception:
            pass
        return combined

    def _resolve_temples(self, state: AgentState) -> List[str]:
        """Resolves target canonical temple folder IDs from routing decision or query text dynamically."""
        canonical_map = self._get_dynamic_canonical_map()

        # 1. Inspect route decision metadata
        route_decision = state.intermediate_results.get("route_decision")
        raw_temples = []
        if route_decision:
            metadata = getattr(route_decision, "metadata", {}) or {}
            detected_temples = metadata.get("detected_temples")
            if detected_temples and isinstance(detected_temples, list):
                raw_temples = detected_temples
            elif metadata.get("detected_temple"):
                raw_temples = [metadata["detected_temple"]]

        # 2. Canonicalize raw temple names from routing metadata
        canonical_temples = []
        for t in raw_temples:
            t_clean = t.lower().strip()
            # Direct canonical map lookup
            if t_clean in canonical_map:
                c_id = canonical_map[t_clean]
                if c_id not in canonical_temples:
                    canonical_temples.append(c_id)
            else:
                for k, v in canonical_map.items():
                    if k in t_clean or t_clean in k:
                        if v not in canonical_temples:
                            canonical_temples.append(v)
                        break

        if canonical_temples:
            return canonical_temples

        # 3. Extract directly from user query
        query = state.user_query or ""
        clean_query = query
        from_to_match = re.search(r"\bfrom\s+(.+?)\s+to\s+", clean_query, re.IGNORECASE)
        orig_cand = from_to_match.group(1).strip() if from_to_match else None
        if not orig_cand:
            m_orig = re.search(r"\bfrom\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)?)\b", clean_query, re.IGNORECASE)
            if m_orig and m_orig.group(1).lower() not in ["the", "a", "an", "this", "our", "my", "some", "any", "which", "me"]:
                orig_cand = m_orig.group(1).strip()
        if orig_cand:
            clean_query = re.sub(rf"\b(?:from|starting\s+(?:from|at)|leaving\s+from|start\s+from)\s+{re.escape(orig_cand)}\b", " ", clean_query, flags=re.IGNORECASE)
            clean_query = re.sub(rf"\bfrom\s+[A-Za-z\s,]+?\s+to\b", " to ", clean_query, flags=re.IGNORECASE)

        q_norm = clean_query.lower()

        matched = []
        # Check longest keys first
        for alias in sorted(canonical_map.keys(), key=len, reverse=True):
            pattern = r'\b' + re.escape(alias) + r'\b'
            if re.search(pattern, q_norm):
                c_id = canonical_map[alias]
                if c_id not in matched:
                    matched.append(c_id)

        if matched:
            return matched

        # 4. Fallback to query planner temple detection if available
        try:
            planner = getattr(getattr(self.rag_tool, "_rag_service", None), "query_planner", None)
            if planner and hasattr(planner, "detect_temple"):
                det = planner.detect_temple(query)
                if det:
                    return [det]
        except Exception:
            pass

        return []

    def _fetch_category(self, temple: str, category: str) -> Optional[Any]:
        """Fetches category data from RAGTool with canonical and dynamic fallback key lookup."""
        # 1. Direct query
        data = self.rag_tool.get_temple_category_data(temple, category)
        if data is not None:
            return data

        canonical_map = self._get_dynamic_canonical_map()

        # 2. Canonical mapping lookup
        t_clean = temple.strip().lower()
        if t_clean in canonical_map:
            c_name = canonical_map[t_clean]
            data = self.rag_tool.get_temple_category_data(c_name, category)
            if data is not None:
                return data

        # 3. Try case variants
        for variant in [temple.title(), temple.lower(), temple.capitalize()]:
            data = self.rag_tool.get_temple_category_data(variant, category)
            if data is not None:
                return data

        # 4. Try aliases matching
        for k, v in canonical_map.items():
            if k in t_clean or t_clean in k:
                data = self.rag_tool.get_temple_category_data(v, category)
                if data is not None:
                    return data
                data = self.rag_tool.get_temple_category_data(k, category)
                if data is not None:
                    return data

        return None

    def _fetch_verified_costs(
        self,
        temple: str,
        query: str,
        params: Dict[str, Any]
    ) -> Tuple[List[BudgetItem], List[BudgetItem]]:
        """
        Fetches relevant category data via RAGTool and constructs verified BudgetItem list.
        Returns (verified_items, unquantified_items).
        """
        verified: List[BudgetItem] = []
        unquantified: List[BudgetItem] = []
        q_norm = query.lower()

        # 1. Entry / Darshan from timings
        timings_data = self._fetch_category(temple, "timings")
        if timings_data and isinstance(timings_data, dict):
            entry_fee = timings_data.get("entry_fee") or timings_data.get("entry_ticket")
            if entry_fee:
                min_v, max_v, unit_t, is_free, is_rng, is_q, notes = parse_price_text(str(entry_fee), category="entry")
                if is_q:
                    verified.append(BudgetItem(
                        category="entry",
                        item_name="General Darshan / Entry",
                        min_cost=min_v,
                        max_cost=max_v,
                        unit=unit_t,
                        is_free=is_free,
                        is_range=is_rng,
                        is_quantified=True,
                        provenance=CostProvenance.VERIFIED,
                        raw_price_str=str(entry_fee),
                        source_path=f"{temple.lower()}/timings.json",
                        notes="Temple Entry"
                    ))

        # 2. Sevas
        sevas_data = self._fetch_category(temple, "sevas")
        sevas_list = []
        if isinstance(sevas_data, list):
            sevas_list = sevas_data
        elif isinstance(sevas_data, dict):
            for v in sevas_data.values():
                if isinstance(v, list):
                    sevas_list.extend(v)

        if sevas_list:
            for s in sevas_list:
                s_name = s.get("name") or s.get("seva_name") or s.get("title") or ""
                if not s_name:
                    continue
                s_lower = s_name.lower().strip()
                p_str = s.get("price") or s.get("price_status") or s.get("cost") or ""
                min_v, max_v, unit_t, is_free, is_rng, is_q, notes = parse_price_text(str(p_str), category="sevas")

                # Dynamic match against user query
                is_match = False
                if s_lower in q_norm:
                    is_match = True
                elif params.get("specific_seva") and params["specific_seva"] in s_lower:
                    is_match = True
                else:
                    # Multi-word match
                    s_words = [w for w in re.split(r'\W+', s_lower) if len(w) >= 4 and w not in ["seva", "pooja", "puja", "darshan", "swamy", "temple"]]
                    if s_words and all(w in q_norm for w in s_words):
                        is_match = True

                item = BudgetItem(
                    category="sevas",
                    item_name=s_name,
                    min_cost=min_v,
                    max_cost=max_v,
                    unit=unit_t,
                    is_free=is_free,
                    is_range=is_rng,
                    is_quantified=is_q,
                    provenance=CostProvenance.VERIFIED if is_q else CostProvenance.UNAVAILABLE,
                    raw_price_str=str(p_str),
                    source_path=f"{temple.lower()}/sevas.json",
                    notes="Selected Seva" if is_match else "Optional Seva"
                )
                if is_q:
                    verified.append(item)
                elif is_match:
                    unquantified.append(item)

        # 3. Accommodation
        accom_data = self._fetch_category(temple, "accommodation")
        accom_list = []
        if isinstance(accom_data, list):
            accom_list = accom_data
        elif isinstance(accom_data, dict):
            for v in accom_data.values():
                if isinstance(v, list):
                    accom_list.extend(v)

        if accom_list:
            specific_room_requested = False
            for r in accom_list:
                r_name = r.get("name") or r.get("type") or r.get("room_type") or "Accommodation"
                if r_name.lower() in q_norm:
                    specific_room_requested = True
                    break

            for r in accom_list:
                r_name = r.get("name") or r.get("type") or r.get("room_type") or "Accommodation"
                p_str = r.get("price") or r.get("tariff") or r.get("rate") or r.get("cost") or ""
                if not p_str:
                    continue
                min_v, max_v, unit_t, is_free, is_rng, is_q, notes = parse_price_text(str(p_str), category="accommodation")
                is_this_requested = (r_name.lower() in q_norm) if specific_room_requested else False

                prop_type = r.get("type") or r.get("room_type") or "Lodge / Hotel"
                dist_str = r.get("distance") or "Near Temple"

                # Classify Tier:
                # Budget: <= 1000/night (or devasthanam guest house / choultry with min <= 600)
                # Standard / Comfort: 1000 - 2500/night
                # Premium: > 2500/night (or high-end property / resort / villa / max >= 3200)
                if (max_v is not None and max_v <= 1000) or (min_v is not None and min_v <= 600 and max_v is not None and max_v <= 1500) or "devasthanam" in str(prop_type).lower() or "choultry" in r_name.lower() or "satralu" in r_name.lower():
                    tier = "Budget"
                elif (min_v is not None and min_v >= 2500) or (max_v is not None and max_v >= 3200) or any(w in r_name.lower() or w in str(prop_type).lower() for w in ["resort", "villa", "vvip"]):
                    tier = "Premium"
                else:
                    tier = "Standard / Comfort"

                item = BudgetItem(
                    category="accommodation",
                    item_name=r_name,
                    min_cost=min_v,
                    max_cost=max_v,
                    unit=unit_t,
                    is_free=is_free,
                    is_range=is_rng,
                    is_quantified=is_q,
                    provenance=CostProvenance.VERIFIED if is_q else CostProvenance.UNAVAILABLE,
                    raw_price_str=str(p_str),
                    source_path=f"{temple.lower()}/accommodation.json",
                    notes="Selected Accommodation" if is_this_requested else "Alternative Stay Tier",
                    property_type=prop_type,
                    distance=dist_str,
                    tier=tier,
                    temple=temple.title(),
                    destination=temple.title(),
                    stay_nights=params.get("nights", 0),
                    stay_rooms=params.get("rooms", 1)
                )
                if is_q:
                    verified.append(item)

        needs_accom = bool(params.get("accom_requested") or params.get("days", 1) > 1 or params.get("nights", 0) > 0)
        has_quantified_accom = any(it.category == "accommodation" and it.is_quantified for it in verified)
        if needs_accom and not has_quantified_accom:
            unquantified.append(BudgetItem(
                category="accommodation",
                item_name="Accommodation / Stay",
                min_cost=None,
                max_cost=None,
                unit="per room per night",
                is_free=False,
                is_range=False,
                is_quantified=False,
                provenance=CostProvenance.UNAVAILABLE,
                raw_price_str="Tariffs unquantified in devasthanam records",
                source_path=f"{temple.lower()}/accommodation.json",
                notes="Requires direct devasthanam counter verification"
            ))

        # 4. Prasadam
        prasadam_data = self._fetch_category(temple, "prasadam")
        prasadam_list = []
        if isinstance(prasadam_data, list):
            prasadam_list = prasadam_data
        elif isinstance(prasadam_data, dict):
            for v in prasadam_data.values():
                if isinstance(v, list):
                    prasadam_list.extend(v)

        if prasadam_list:
            added_p = 0
            for pr in prasadam_list:
                p_name = pr.get("item") or pr.get("name") or pr.get("item_name") or "Prasadam"
                p_str = pr.get("price") or pr.get("price_status") or pr.get("cost") or ""
                if not p_str:
                    continue
                min_v, max_v, unit_t, is_free, is_rng, is_q, notes = parse_price_text(str(p_str), category="prasadam")
                item = BudgetItem(
                    category="prasadam",
                    item_name=p_name,
                    min_cost=min_v,
                    max_cost=max_v,
                    unit=unit_t,
                    is_free=is_free,
                    is_range=is_rng,
                    is_quantified=is_q,
                    provenance=CostProvenance.VERIFIED if is_q else CostProvenance.UNAVAILABLE,
                    raw_price_str=str(p_str),
                    source_path=f"{temple.lower()}/prasadam.json",
                    notes="Prasadam / Food"
                )
                if is_q:
                    if added_p < 2:
                        verified.append(item)
                        added_p += 1
                else:
                    if len(unquantified) < 2:
                        unquantified.append(item)

        # 5. Restaurants / Dining (only included if user explicitly requested food/dining or specified dining costs)
        user_wants_food = bool(
            re.search(r"\b(food|dining|lunch|dinner|meals?|restaurants?|breakfast)\b", q_norm) or
            any(u.category in ["food", "restaurants", "dining"] for u in params.get("user_costs", []))
        )
        if user_wants_food:
            rest_data = self._fetch_category(temple, "restaurants")
            rest_list = []
            if isinstance(rest_data, list):
                rest_list = rest_data
            elif isinstance(rest_data, dict):
                for v in rest_data.values():
                    if isinstance(v, list):
                        rest_list.extend(v)

            if rest_list:
                for r in rest_list[:2]:
                    r_name = r.get("name") or r.get("restaurant_name") or "Dining"
                    p_str = r.get("avg_cost") or r.get("price") or r.get("cost") or r.get("price_range") or ""
                    if not p_str:
                        continue
                    min_v, max_v, unit_t, is_free, is_rng, is_q, notes = parse_price_text(str(p_str), category="restaurants")
                    if is_q:
                        item = BudgetItem(
                            category="restaurants",
                            item_name=r_name,
                            min_cost=min_v,
                            max_cost=max_v,
                            unit=unit_t,
                            is_free=is_free,
                            is_range=is_rng,
                            is_quantified=True,
                            provenance=CostProvenance.VERIFIED,
                            raw_price_str=str(p_str),
                            source_path=f"{temple.lower()}/restaurants.json",
                            notes="Dining"
                        )
                        verified.append(item)

        return verified, unquantified

    def _calculate_totals(
        self,
        verified_items: List[BudgetItem],
        user_items: List[BudgetItem],
        params: Dict[str, Any]
    ) -> Tuple[Optional[float], Optional[float], List[str], bool]:
        """
        Deterministically selects a feasible accommodation and calculates total expenditures.
        Returns (min_total, max_total, notes_list, is_quantified).
        """
        pax = params.get("pax", 1)
        days = params.get("days", 1)
        accom_pref = params.get("accommodation_preference")
        if accom_pref == "none" or params.get("no_accom"):
            nights = 0
        elif "nights" in params:
            nights = max(0, params["nights"])
        else:
            nights = max(0, days - 1) if days > 1 else (1 if params.get("accom_requested") else 0)
        rooms = params.get("rooms", 1)

        all_items = verified_items + user_items
        quantified_items = [it for it in all_items if it.is_quantified and it.min_cost is not None and it.max_cost is not None]

        if not quantified_items:
            is_complete = not (nights > 0 or params.get("accom_requested", False))
            return None, None, ["No quantified tariff records available in knowledge base."], False, is_complete, []

        notes = []

        # 1. Base required costs: Entry + User Costs + Explicitly requested Sevas
        base_min = 0.0
        base_max = 0.0

        # User expenses
        for u in user_items:
            if u.is_quantified and u.min_cost is not None and u.max_cost is not None:
                base_min += u.min_cost
                base_max += u.max_cost

        # Entry fees
        entry_items = [it for it in verified_items if it.category == "entry" and it.is_quantified]
        for e in entry_items:
            e_min = e.min_cost if e.min_cost is not None else 0.0
            e_max = e.max_cost if e.max_cost is not None else 0.0
            if e.unit == "per person":
                e_min *= pax
                e_max *= pax
            base_min += e_min
            base_max += e_max

        # Specific user-selected sevas
        selected_sevas = [it for it in verified_items if it.category == "sevas" and it.notes == "Selected Seva" and it.is_quantified]
        for s in selected_sevas:
            s_min = s.min_cost if s.min_cost is not None else 0.0
            s_max = s.max_cost if s.max_cost is not None else 0.0
            if s.unit == "per person":
                s_min *= pax
                s_max *= pax
            base_min += s_min
            base_max += s_max

        # 2. Accommodation Selection
        accom_items = [it for it in verified_items if it.category == "accommodation" and it.is_quantified]
        budget_limit = params.get("budget_limit")

        selected_stay_min = 0.0
        selected_stay_max = 0.0
        options_eval = []

        if nights > 0 and accom_items and accom_pref != "none":
            # Score and evaluate each accommodation alternative
            for a in accom_items:
                # Multiplier
                if a.unit == "per person":
                    mult = nights * pax if nights > 0 else pax
                elif a.unit in ["per room per night", "per night", "per room"] or a.category == "accommodation":
                    mult = nights * rooms
                else:
                    mult = 1
                opt_min = (a.min_cost or 0.0) * mult
                opt_max = (a.max_cost or 0.0) * mult
                tot_min = base_min + opt_min
                tot_max = base_max + opt_max

                a.stay_cost_min = opt_min
                a.stay_cost_max = opt_max
                a.stay_nights = nights
                a.stay_rooms = rooms

                matches_pref = True
                if accom_pref in ["Budget", "Standard / Comfort", "Premium"]:
                    matches_pref = (getattr(a, "tier", "") == accom_pref)

                options_eval.append({
                    "item": a,
                    "opt_min": opt_min,
                    "opt_max": opt_max,
                    "tot_min": tot_min,
                    "tot_max": tot_max,
                    "is_explicit": a.notes == "Selected Accommodation",
                    "matches_preference": matches_pref
                })

            # Check if user explicitly requested a specific room or property
            explicit_choice = next((o for o in options_eval if o["is_explicit"]), None)

            if explicit_choice:
                chosen = explicit_choice
            elif accom_pref in ["Budget", "Standard / Comfort", "Premium"]:
                matching_tier_opts = [o for o in options_eval if o["matches_preference"]]
                if matching_tier_opts:
                    if budget_limit is not None:
                        feasible_matching = [o for o in matching_tier_opts if o["tot_min"] <= budget_limit]
                        if feasible_matching:
                            chosen = max(feasible_matching, key=lambda x: x["opt_min"])
                        else:
                            chosen = min(matching_tier_opts, key=lambda x: x["opt_min"])
                            shortfall = chosen["tot_min"] - budget_limit
                            notes.append(f"Budget shortfall: {chosen['item'].item_name} ({accom_pref} tier) stay starts from ₹{chosen['opt_min']:,.0f}, exceeding your budget of ₹{budget_limit:,.0f} by ₹{shortfall:,.0f}.")
                    else:
                        chosen = min(matching_tier_opts, key=lambda x: x["opt_min"])
                else:
                    notes.append(f"No verified accommodation options found in '{accom_pref}' tier in devasthanam records.")
                    chosen = min(options_eval, key=lambda x: x["opt_min"])
            elif budget_limit is not None:
                # Filter options where minimum cost fits within budget
                feasible = [o for o in options_eval if o["tot_min"] <= budget_limit]
                if not feasible:
                    # None fit: choose least expensive option to show shortfall
                    chosen = min(options_eval, key=lambda x: x["opt_min"])
                    shortfall = chosen["tot_min"] - budget_limit
                    notes.append(f"Budget shortfall: minimum accommodation starts from ₹{chosen['opt_min']:,.0f}, exceeding your budget of ₹{budget_limit:,.0f} by ₹{shortfall:,.0f}.")
                else:
                    budget_opts = [o for o in feasible if getattr(o["item"], "tier", "") == "Budget"]
                    standard_opts = [o for o in feasible if getattr(o["item"], "tier", "") == "Standard / Comfort"]
                    premium_opts = [o for o in feasible if getattr(o["item"], "tier", "") == "Premium"]

                    daily_budget = budget_limit / max(1, days)
                    if daily_budget <= 2500:
                        candidates = budget_opts or feasible
                        chosen = max(candidates, key=lambda x: x["opt_min"])
                    elif daily_budget <= 8000:
                        candidates = standard_opts or budget_opts or feasible
                        chosen = max(candidates, key=lambda x: x["opt_min"])
                    else:
                        candidates = premium_opts or standard_opts or feasible
                        chosen = max(candidates, key=lambda x: x["opt_min"])
            else:
                # Default: standard tier preferred if available, else lowest
                standard_opts = [o for o in options_eval if getattr(o["item"], "tier", "") == "Standard / Comfort"]
                chosen = min(standard_opts, key=lambda x: x["opt_min"]) if standard_opts else min(options_eval, key=lambda x: x["opt_min"])

            selected_stay_min = chosen["opt_min"]
            selected_stay_max = chosen["opt_max"]

            # Tag the chosen item and alternatives
            for a in accom_items:
                if a is chosen["item"]:
                    a.notes = "Selected Accommodation"
                else:
                    a.notes = "Alternative Stay Tier"

            for o in options_eval:
                is_this_chosen = (o["item"] is chosen["item"])
                t_name = getattr(o["item"], "temple", "")
                dest_name = getattr(o["item"], "destination", "") or (t_name.title() if t_name else "")
                o["temple"] = dest_name
                o["destination"] = dest_name
                o["nights"] = nights
                o["rooms"] = rooms
                o["is_recommended"] = is_this_chosen
                o["is_selected"] = is_this_chosen
                rec_lbl = f"Recommended for {dest_name}" if dest_name else "Recommended"
                o["recommendation_label"] = rec_lbl
                setattr(o["item"], "destination", dest_name)
                setattr(o["item"], "is_recommended", is_this_chosen)
                setattr(o["item"], "recommendation_label", rec_lbl)

            notes.append(f"Accommodation: Selected {chosen['item'].item_name} (₹{selected_stay_min:,.0f} to ₹{selected_stay_max:,.0f} for {nights} night(s), {rooms} room(s))")

        needs_accom = (nights > 0 or params.get("accom_requested", False)) and (accom_pref != "none")
        has_quantified_accom = bool(accom_items)
        accom_missing = needs_accom and not has_quantified_accom

        if accom_missing:
            notes.append(f"Accommodation is required for {nights} night(s) but no quantified tariff records are available in devasthanam records.")

        calc_min = base_min + selected_stay_min
        calc_max = base_max + selected_stay_max
        is_complete = not accom_missing

        return calc_min, calc_max, notes, True, is_complete, options_eval

    def _run(self, state: AgentState) -> AgentResponse:
        """
        Main execution lifecycle for BudgetAgent.
        """
        t0 = time.perf_counter()
        query = (state.user_query or "").strip()

        # 1. Empty / Whitespace Query validation
        if not query:
            return AgentResponse(
                success=False,
                agent_name=self.name,
                answer="Please provide a valid question regarding pilgrimage budget or costs.",
                sources=[],
                error="Empty or whitespace query provided.",
                latency_ms=0.0,
                metadata={"error_type": "EmptyQuery"}
            )

        # 2. Extract User Parameters & Injected Expenses
        sc_input = getattr(state, "structured_constraints", None)
        params = self._extract_parameters(query, structured_constraints=sc_input)

        # Merge structured constraints if passed from upstream pipeline
        if sc_input:
            sc = sc_input
            if "duration_days" in sc and not sc.get("days_assumed", True):
                params["days"] = sc["duration_days"]
                params["days_assumed"] = False
                params["nights"] = max(0, params["days"] - 1)
            elif "duration_days" in sc and params.get("days_assumed", True):
                params["days"] = sc["duration_days"]
                params["days_assumed"] = sc.get("days_assumed", False)
                params["nights"] = max(0, params["days"] - 1)
            if "budget_limit" in sc and sc["budget_limit"] is not None:
                params["budget_limit"] = sc["budget_limit"]
            if sc.get("accommodation_required"):
                params["accom_requested"] = True
                if params.get("nights", 0) == 0:
                    params["nights"] = max(1, params.get("days", 1) - 1) if params.get("days", 1) > 1 else 1
            if not sc.get("pax_assumed", True) and "pax" in sc:
                params["pax"] = sc["pax"]
                params["pax_assumed"] = False
            if sc.get("accommodation_preference"):
                norm_tier = normalize_accommodation_tier(sc["accommodation_preference"])
                params["accommodation_preference"] = norm_tier
                if norm_tier == "none":
                    params["no_accom"] = True
                    params["accom_requested"] = False
                    params["nights"] = 0
            if sc.get("transport_preference"):
                params["transport_preference"] = str(sc["transport_preference"]).lower()
            if sc.get("food_preference"):
                params["food_preference"] = str(sc["food_preference"]).lower()
            if sc.get("origin"):
                params["origin"] = str(sc["origin"]).strip().title()

        # 3. Resolve Target Temple(s)
        detected_temples = self._resolve_temples(state)
        if not detected_temples:
            latency_ms = (time.perf_counter() - t0) * 1000.0

            # Check for explicitly named unregistered temple
            unreg_temple = None
            for famous in ["golden temple", "meenakshi", "somnath", "kedarnath", "badrinath", "vaishno devi", "kashi vishwanath", "jagannath"]:
                if famous in query.lower():
                    unreg_temple = famous.title()
                    break
            if not unreg_temple:
                m = re.search(r"\b([A-Za-z]+(?:\s+[A-Za-z]+)?)\s+(temple|mandir|kovil|devasthanam)\b", query, re.IGNORECASE)
                if m and m.group(1).lower() not in ["the", "a", "this", "which", "what", "how", "any"]:
                    unreg_temple = f"{m.group(1).title()} {m.group(2).title()}"

            if unreg_temple:
                return AgentResponse(
                    success=False,
                    agent_name=self.name,
                    answer=f"'{unreg_temple}' is not currently in the registered pilgrimage knowledge base. BudgetAgent supports verified records for the 20 Telangana pilgrimage devasthanams.",
                    sources=[],
                    error=f"Unregistered temple '{unreg_temple}'.",
                    latency_ms=latency_ms,
                    metadata={"supported": False, "unregistered_temple": unreg_temple}
                )

            return AgentResponse(
                success=False,
                agent_name=self.name,
                answer="Please specify which temple you are planning to visit (e.g., Yadadri, Basara, Dharmapuri) so that verified tariffs and seva rates can be calculated.",
                sources=[],
                error="No registered temple detected.",
                latency_ms=latency_ms,
                metadata={"missing_temple": True}
            )

        # 4. Process Temple(s)
        all_sources = set()
        grand_min: Optional[float] = 0.0
        grand_max: Optional[float] = 0.0
        all_verified: List[BudgetItem] = []
        all_unquantified: List[BudgetItem] = []
        all_options_eval: List[Dict[str, Any]] = []
        overall_quantified = False
        is_complete_estimate = True
        any_accom_missing = False

        # Multi-destination overnight distribution
        total_trip_nights = params.get("nights", 0)
        temple_allocated_nights: Dict[str, int] = {}
        if len(detected_temples) > 1 and total_trip_nights > 0:
            num_temples = len(detected_temples)
            base_n = total_trip_nights // num_temples
            rem_n = total_trip_nights % num_temples
            for idx, tm in enumerate(detected_temples):
                temple_allocated_nights[tm] = base_n + (1 if idx < rem_n else 0)
        else:
            for tm in detected_temples:
                temple_allocated_nights[tm] = total_trip_nights

        for temple in detected_temples:
            t_params = dict(params)
            t_params["nights"] = temple_allocated_nights.get(temple, total_trip_nights)

            verified_items, unquantified_items = self._fetch_verified_costs(temple, query, t_params)
            all_verified.extend(verified_items)
            all_unquantified.extend(unquantified_items)

            for it in verified_items:
                if it.source_path:
                    all_sources.add(it.source_path)

            # If accommodation was requested/required and unquantified, cite accommodation.json as checked
            if (t_params.get("nights", 0) > 0 or t_params.get("accom_requested")) and not any(it.category == "accommodation" for it in verified_items):
                try:
                    folder = self.rag_tool._rag_service.knowledge_registry.get_temple_folder(temple)
                    if folder is not None:
                        all_sources.add(f"{folder.name}/accommodation.json")
                    else:
                        all_sources.add(f"{temple.lower()}/accommodation.json")
                except Exception:
                    all_sources.add(f"{temple.lower()}/accommodation.json")

            calc_res = self._calculate_totals(
                verified_items,
                params.get("user_costs", []) if len(detected_temples) == 1 else [],
                t_params
            )
            t_opts = []
            if len(calc_res) == 6:
                t_min, t_max, t_notes, t_quantified, t_complete, t_opts = calc_res
            elif len(calc_res) == 5:
                t_min, t_max, t_notes, t_quantified, t_complete = calc_res
            else:
                t_min, t_max, t_notes, t_quantified = calc_res
                t_complete = True
            all_options_eval.extend(t_opts)

            if not t_complete:
                is_complete_estimate = False
                if t_params.get("nights", 0) > 0 or t_params.get("accom_requested"):
                    any_accom_missing = True

            if t_quantified and t_min is not None and t_max is not None:
                overall_quantified = True
                grand_min = (grand_min or 0.0) + t_min
                grand_max = (grand_max or 0.0) + t_max

        # Add user-provided costs to grand total if multi-temple
        if len(detected_temples) > 1 and params.get("user_costs"):
            u_min = sum(u.min_cost for u in params["user_costs"] if u.min_cost is not None)
            u_max = sum(u.max_cost for u in params["user_costs"] if u.max_cost is not None)
            grand_min = (grand_min or 0.0) + u_min
            grand_max = (grand_max or 0.0) + u_max

        # Day trip completeness evaluation: day trips without user-provided transit/food are partial estimates
        is_day_trip = (params.get("nights", 0) == 0 and not params.get("accom_requested", False))
        has_user_travel = any(u.category == "travel" for u in params.get("user_costs", []))
        has_user_dining = any(u.category in ["food", "restaurants", "dining"] for u in params.get("user_costs", []))
        has_verified_dining = any(it.category == "restaurants" for it in all_verified)

        if is_day_trip:
            if not has_user_travel:
                orig_txt = f" from {params['origin']}" if params.get("origin") else ""
                raw_trv = (
                    f"Unquantified (transit fare{orig_txt} varies by chosen transport mode: bus/train/cab; not in temple records)"
                    if params.get("origin")
                    else "Unquantified (varies by starting origin and travel mode; not supplied in query)"
                )
                all_unquantified.append(BudgetItem(
                    category="travel",
                    item_name="Personal Travel / Transit",
                    min_cost=None,
                    max_cost=None,
                    unit="per person",
                    is_free=False,
                    is_range=False,
                    is_quantified=False,
                    provenance=CostProvenance.UNAVAILABLE,
                    raw_price_str=raw_trv,
                    source_path="",
                    notes=f"Starting origin{orig_txt} transport mode not specified"
                ))
            if not has_user_dining and not has_verified_dining:
                all_unquantified.append(BudgetItem(
                    category="dining",
                    item_name="Personal Meals / Food",
                    min_cost=None,
                    max_cost=None,
                    unit="per person",
                    is_free=False,
                    is_range=False,
                    is_quantified=False,
                    provenance=CostProvenance.UNAVAILABLE,
                    raw_price_str="Unquantified (personal dining expenses outside temple)",
                    source_path="",
                    notes="Personal dining expenses outside temple records"
                ))

        if is_day_trip and (not has_user_travel or (grand_min == 0 and grand_max == 0)):
            is_complete_estimate = False

        if not overall_quantified:
            grand_min = None
            grand_max = None

        # Display names for title
        temple_titles = [TEMPLE_DISPLAY_NAMES.get(t, t.title()) for t in detected_temples]

        # 5. Build Final Structured Markdown Response
        lines = [f"## 💰 Pilgrimage Budget — {', '.join(temple_titles)}", ""]

        # Categorize verified records
        selected_accom_items = [it for it in all_verified if it.category == "accommodation" and it.notes == "Selected Accommodation"]
        alt_accom_items = [it for it in all_verified if it.category == "accommodation" and it.notes == "Alternative Stay Tier"]
        selected_seva_items = [it for it in all_verified if it.category == "sevas" and it.notes == "Selected Seva"]
        opt_seva_items = [it for it in all_verified if it.category == "sevas" and it.notes == "Optional Seva"]
        entry_items = [it for it in all_verified if it.category == "entry"]
        discretionary_items = [it for it in all_verified if it.category in ["prasadam", "restaurants", "facilities"] or (it.category not in ["accommodation", "sevas", "entry"])]

        # 5a. Trip Budget Summary
        pax_cnt = params.get("pax", 1)
        days_cnt = params.get("days", 1)
        nights_cnt = params.get("nights", 0)
        rooms_cnt = params.get("rooms", 1)
        r_note = " (assumed 2 persons/room)" if params.get("rooms_assumed") and pax_cnt > 2 else ""

        lines.append("### 📋 Trip Budget Summary")
        lines.append(f"- **Pilgrims**: {pax_cnt} devotee(s) | **Rooms**: {rooms_cnt} room(s){r_note}")
        accom_pref = params.get("accommodation_preference")
        if nights_cnt > 0 and accom_pref != "none":
            lines.append(f"- **Trip Duration**: {days_cnt} day(s) ({nights_cnt} overnight stay(s))")
        elif accom_pref == "none":
            lines.append(f"- **Trip Duration**: {days_cnt} day(s) (Day visit / No accommodation requested)")
            lines.append("- **Accommodation**: Zero lodging charges (Plan requested without accommodation)")
        else:
            lines.append(f"- **Trip Duration**: {days_cnt} day(s) (Day visit)")

        if params.get("budget_limit") is not None:
            blim = params["budget_limit"]
            lines.append(f"- **User Budget Limit**: ₹{blim:,.0f}")
            if not overall_quantified:
                lines.append(f"- **Budget Feasibility**: ℹ️ **Feasibility cannot be determined**")
            elif any_accom_missing:
                lines.append(f"- **Budget Feasibility**: ℹ️ **Feasibility Cannot Be Confirmed**")
            elif grand_min == 0 and grand_max == 0:
                lines.append(f"- **Budget Feasibility**: ℹ️ **Mandatory Entry is Free (₹0) — Feasibility Incomplete**")
            elif not is_complete_estimate and is_day_trip:
                if grand_max is not None and grand_max <= blim:
                    lines.append(f"- **Budget Feasibility**: ℹ️ **Partial Baseline Within Budget** (Selected items fit ₹{blim:,.0f}, but full trip unconfirmed)")
                else:
                    shortfall = (grand_min or 0.0) - blim
                    lines.append(f"- **Budget Feasibility**: ⚠️ **Exceeds Budget** (Shortfall of ₹{shortfall:,.0f})")
            elif grand_max is not None and grand_max <= blim:
                surplus = blim - grand_max
                lines.append(f"- **Budget Feasibility**: ✅ **Within Budget** (Surplus of ₹{surplus:,.0f} available for travel & meals)")
            elif grand_min is not None and grand_min <= blim:
                excess = grand_max - blim
                lines.append(f"- **Budget Feasibility**: ⚠️ **Partially Within Budget** (Baseline fits; upper tier exceeds by ₹{excess:,.0f})")
            elif grand_min is not None:
                shortfall = grand_min - blim
                lines.append(f"- **Budget Feasibility**: ⚠️ **Exceeds Budget** (Shortfall of ₹{shortfall:,.0f}; see lower tier options below)")
        lines.append("")

        # 5b. Recommended Accommodation / Complete Stay Plan
        if selected_accom_items and nights_cnt > 0 and accom_pref != "none":
            if len(detected_temples) > 1:
                lines.append("### 🏨 Recommended Stay Plan")
                lines.append("")
                stay_idx = 1
                for tm in detected_temples:
                    tm_nights = temple_allocated_nights.get(tm, 0)
                    tm_display = TEMPLE_DISPLAY_NAMES.get(tm, tm.title())
                    if tm_nights <= 0:
                        continue
                    tm_sel = next((it for it in selected_accom_items if getattr(it, "temple", "") == tm), None)
                    lines.append(f"**Stay {stay_idx} — {tm_display}**")
                    if tm_sel:
                        p_type = getattr(tm_sel, "property_type", None) or "Hotel / Lodge"
                        dist_t = getattr(tm_sel, "distance", None) or "Near Temple"
                        tier_t = getattr(tm_sel, "tier", None) or "Standard / Comfort"
                        tar_str = f"₹{tm_sel.min_cost:,.0f}" if tm_sel.min_cost == tm_sel.max_cost else f"₹{tm_sel.min_cost:,.0f} – ₹{tm_sel.max_cost:,.0f}"
                        stay_min_val = getattr(tm_sel, "stay_cost_min", None) or ((tm_sel.min_cost or 0) * tm_nights * rooms_cnt)
                        stay_max_val = getattr(tm_sel, "stay_cost_max", None) or ((tm_sel.max_cost or 0) * tm_nights * rooms_cnt)
                        stay_str = f"₹{stay_min_val:,.0f}" if stay_min_val == stay_max_val else f"₹{stay_min_val:,.0f} – ₹{stay_max_val:,.0f}"
                        lines.append(f"- **Recommended Property**: **{tm_sel.item_name}**")
                        lines.append(f"- **Accommodation Tier & Type**: {tier_t} | {p_type}")
                        lines.append(f"- **Number of Nights**: {tm_nights} overnight stay(s) ({rooms_cnt} room(s))")
                        lines.append(f"- **Location**: {dist_t} (Near {tm_display})")
                        lines.append(f"- **Nightly Tariff**: {tar_str} per room per night")
                        lines.append(f"- **Calculated Stay Cost**: {stay_str}")
                        lines.append(f"- **Recommendation Label**: Recommended for {tm_display}")
                    else:
                        lines.append(f"- **Recommended Property**: No verified accommodation records found for {tm_display} in devasthanam database.")
                        lines.append(f"- **Accommodation Charges**: ₹0 (Lodging not charged in selected plan)")
                    lines.append("")
                    stay_idx += 1
            else:
                sel_a = selected_accom_items[0]
                lines.append(f"### 🏨 Recommended Accommodation: {sel_a.item_name}")
                p_type = getattr(sel_a, "property_type", None) or "Hotel / Lodge"
                dist_t = getattr(sel_a, "distance", None) or "Near Temple"
                tier_t = getattr(sel_a, "tier", None) or "Standard / Comfort"
                lines.append(f"- **Property Type**: {p_type} | **Tier**: {tier_t}")
                lines.append(f"- **Location & Distance**: {dist_t}")
                tar_str = f"₹{sel_a.min_cost:,.0f}" if sel_a.min_cost == sel_a.max_cost else f"₹{sel_a.min_cost:,.0f} – ₹{sel_a.max_cost:,.0f}"
                lines.append(f"- **Nightly Tariff**: {tar_str} per room per night")
                stay_min_val = getattr(sel_a, "stay_cost_min", None) or ((sel_a.min_cost or 0) * nights_cnt * rooms_cnt)
                stay_max_val = getattr(sel_a, "stay_cost_max", None) or ((sel_a.max_cost or 0) * nights_cnt * rooms_cnt)
                stay_str = f"₹{stay_min_val:,.0f}" if stay_min_val == stay_max_val else f"₹{stay_min_val:,.0f} – ₹{stay_max_val:,.0f}"
                lines.append(f"- **Calculated Stay Cost**: {stay_str} (for {nights_cnt} night(s), {rooms_cnt} room(s))")
                if accom_pref in ["Budget", "Standard / Comfort", "Premium"]:
                    if tier_t == accom_pref:
                        lines.append(f"- **Preference Alignment**: ✅ Matches your requested **{accom_pref}** tier preference.")
                    else:
                        lines.append(f"- **Preference Alignment**: ⚠️ No verified options found in requested '{accom_pref}' tier; showing closest available alternative.")
                else:
                    lines.append(f"- **Why This Option**: Grounded recommendation matching your budget allocation, balancing proximity and lodging comfort.")
                lines.append(f"- **Recommendation Label**: Recommended for {temple_titles[0]}")
                lines.append("")

        # 5c. Accommodation Comparison Cards (if multiple options available)
        if all_options_eval and nights_cnt > 0 and accom_pref != "none":
            rooms_cnt = params.get("rooms", 1)
            if len(detected_temples) > 1:
                lines.append("### 🏨 Accommodation Comparison & Alternatives by Destination")
                lines.append("")
                for tm in detected_temples:
                    tm_nights = temple_allocated_nights.get(tm, 0)
                    if tm_nights <= 0:
                        continue
                    tm_display = TEMPLE_DISPLAY_NAMES.get(tm, tm.title())
                    tm_opts = [o for o in all_options_eval if o.get("temple") == tm or getattr(o.get("item"), "temple", "") == tm]
                    if not tm_opts:
                        continue
                    lines.append(f"#### {tm_display} Options")
                    for opt in tm_opts:
                        item = opt["item"]
                        is_sel = (item.notes == "Selected Accommodation")
                        name_disp = f"**{item.item_name}** *(Selected)*" if is_sel else f"**{item.item_name}**"
                        p_type = getattr(item, 'property_type', 'Hotel')
                        dist_val = getattr(item, 'distance', f'Near {tm_display}')
                        tar_disp = f"₹{item.min_cost:,.0f}" if item.min_cost == item.max_cost else f"₹{item.min_cost:,.0f} – ₹{item.max_cost:,.0f}"
                        tot_disp = f"₹{opt['opt_min']:,.0f}" if opt['opt_min'] == opt['opt_max'] else f"₹{opt['opt_min']:,.0f} – ₹{opt['opt_max']:,.0f}"
                        tier_disp = getattr(item, "tier", "Standard / Comfort")
                        if params.get("budget_limit") is not None:
                            blim = params["budget_limit"]
                            if opt["tot_min"] <= blim:
                                left = blim - opt["tot_min"]
                                fit_disp = f"✅ Fits (+₹{left:,.0f} left)"
                            else:
                                over = opt["tot_min"] - blim
                                fit_disp = f"⚠️ Exceeds by ₹{over:,.0f}"
                        else:
                            fit_disp = "✅ Available"
                        status_badge = "✅ Selected Property" if is_sel else "⚪ Alternative Option"
                        maps_s = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote((item.item_name + ' ' + tm_display).strip())}"
                        maps_d = f"https://www.google.com/maps/dir/?api=1&origin={urllib.parse.quote(tm_display.strip())}&destination={urllib.parse.quote(item.item_name.strip())}&travelmode=driving"

                        lines.append(f"- {name_disp} ({tier_disp} · {p_type})")
                        lines.append(f"  - **Distance**: {dist_val}")
                        lines.append(f"  - **Tariff**: {tar_disp}/night ({tm_nights} night(s), {rooms_cnt} room(s))")
                        lines.append(f"  - **Stay Total**: {tot_disp}")
                        lines.append(f"  - **Destination**: {tm_display}")
                        lines.append(f"  - **Budget Fit**: {fit_disp}")
                        lines.append(f"  - **Status**: {status_badge}")
                        lines.append(f"  - **Google Maps**: [🗺️ View on Google Maps]({maps_s}) | [🧭 Get Directions]({maps_d})")
                    lines.append("")
            elif accom_pref in ["Budget", "Standard / Comfort", "Premium"]:
                matching_opts = [o for o in all_options_eval if getattr(o["item"], "tier", "") == accom_pref]
                other_opts = [o for o in all_options_eval if getattr(o["item"], "tier", "") != accom_pref]
                single_tm = detected_temples[0] if detected_temples else "Temple"
                single_tm_disp = TEMPLE_DISPLAY_NAMES.get(single_tm, single_tm.title())

                if matching_opts:
                    lines.append(f"### 🏨 Accommodation Comparison & Alternatives ({accom_pref} Tier)")
                    for opt in matching_opts:
                        item = opt["item"]
                        is_sel = (item.notes == "Selected Accommodation")
                        name_disp = f"**{item.item_name}** *(Selected)*" if is_sel else f"**{item.item_name}**"
                        p_type = getattr(item, 'property_type', 'Hotel')
                        dist_val = getattr(item, 'distance', f'Near {single_tm_disp}')
                        tar_disp = f"₹{item.min_cost:,.0f}" if item.min_cost == item.max_cost else f"₹{item.min_cost:,.0f} – ₹{item.max_cost:,.0f}"
                        tot_disp = f"₹{opt['opt_min']:,.0f}" if opt['opt_min'] == opt['opt_max'] else f"₹{opt['opt_min']:,.0f} – ₹{opt['opt_max']:,.0f}"
                        tier_disp = getattr(item, "tier", "Standard / Comfort")
                        if params.get("budget_limit") is not None:
                            blim = params["budget_limit"]
                            if opt["tot_min"] <= blim:
                                left = blim - opt["tot_min"]
                                fit_disp = f"✅ Fits (+₹{left:,.0f} left)"
                            else:
                                over = opt["tot_min"] - blim
                                fit_disp = f"⚠️ Exceeds by ₹{over:,.0f}"
                        else:
                            fit_disp = "✅ Available"
                        status_badge = "✅ Selected Property" if is_sel else "⚪ Alternative Option"
                        maps_s = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote((item.item_name + ' ' + single_tm_disp).strip())}"
                        maps_d = f"https://www.google.com/maps/dir/?api=1&origin={urllib.parse.quote(single_tm_disp.strip())}&destination={urllib.parse.quote(item.item_name.strip())}&travelmode=driving"

                        lines.append(f"- {name_disp} ({tier_disp} · {p_type})")
                        lines.append(f"  - **Distance**: {dist_val}")
                        lines.append(f"  - **Tariff**: {tar_disp}/night ({nights_cnt} night(s), {rooms_cnt} room(s))")
                        lines.append(f"  - **Stay Total**: {tot_disp}")
                        lines.append(f"  - **Budget Fit**: {fit_disp}")
                        lines.append(f"  - **Status**: {status_badge}")
                        lines.append(f"  - **Google Maps**: [🗺️ View on Google Maps]({maps_s}) | [🧭 Get Directions]({maps_d})")
                    lines.append("")

                if other_opts:
                    lines.append("#### Other Available Tiers (Alternatives)")
                    lines.append("> ℹ️ *Note: The following properties belong to different tiers and do not satisfy your selected preference.*")
                    for opt in other_opts:
                        item = opt["item"]
                        is_sel = (item.notes == "Selected Accommodation")
                        name_disp = f"**{item.item_name}** *(Selected)*" if is_sel else f"**{item.item_name}**"
                        p_type = getattr(item, 'property_type', 'Hotel')
                        dist_val = getattr(item, 'distance', f'Near {single_tm_disp}')
                        tar_disp = f"₹{item.min_cost:,.0f}" if item.min_cost == item.max_cost else f"₹{item.min_cost:,.0f} – ₹{item.max_cost:,.0f}"
                        tot_disp = f"₹{opt['opt_min']:,.0f}" if opt['opt_min'] == opt['opt_max'] else f"₹{opt['opt_min']:,.0f} – ₹{opt['opt_max']:,.0f}"
                        tier_disp = getattr(item, "tier", "Standard / Comfort")
                        if params.get("budget_limit") is not None:
                            blim = params["budget_limit"]
                            if opt["tot_min"] <= blim:
                                left = blim - opt["tot_min"]
                                fit_disp = f"✅ Fits (+₹{left:,.0f} left)"
                            else:
                                over = opt["tot_min"] - blim
                                fit_disp = f"⚠️ Exceeds by ₹{over:,.0f}"
                        else:
                            fit_disp = "✅ Available"
                        status_badge = "✅ Selected Property" if is_sel else "⚪ Alternative Option"
                        maps_s = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote((item.item_name + ' ' + single_tm_disp).strip())}"
                        maps_d = f"https://www.google.com/maps/dir/?api=1&origin={urllib.parse.quote(single_tm_disp.strip())}&destination={urllib.parse.quote(item.item_name.strip())}&travelmode=driving"

                        lines.append(f"- {name_disp} ({tier_disp} · {p_type})")
                        lines.append(f"  - **Distance**: {dist_val}")
                        lines.append(f"  - **Tariff**: {tar_disp}/night ({nights_cnt} night(s), {rooms_cnt} room(s))")
                        lines.append(f"  - **Stay Total**: {tot_disp}")
                        lines.append(f"  - **Budget Fit**: {fit_disp}")
                        lines.append(f"  - **Status**: {status_badge}")
                        lines.append(f"  - **Google Maps**: [🗺️ View on Google Maps]({maps_s}) | [🧭 Get Directions]({maps_d})")
                    lines.append("")
            else:
                lines.append("### 🏨 Accommodation Comparison & Alternatives")
                single_tm = detected_temples[0] if detected_temples else "Temple"
                single_tm_disp = TEMPLE_DISPLAY_NAMES.get(single_tm, single_tm.title())
                for opt in all_options_eval:
                    item = opt["item"]
                    is_sel = (item.notes == "Selected Accommodation")
                    name_disp = f"**{item.item_name}** *(Selected)*" if is_sel else f"**{item.item_name}**"
                    p_type = getattr(item, 'property_type', 'Hotel')
                    dist_val = getattr(item, 'distance', f'Near {single_tm_disp}')
                    tar_disp = f"₹{item.min_cost:,.0f}" if item.min_cost == item.max_cost else f"₹{item.min_cost:,.0f} – ₹{item.max_cost:,.0f}"
                    tot_disp = f"₹{opt['opt_min']:,.0f}" if opt['opt_min'] == opt['opt_max'] else f"₹{opt['opt_min']:,.0f} – ₹{opt['opt_max']:,.0f}"
                    tier_disp = getattr(item, "tier", "Standard / Comfort")
                    if params.get("budget_limit") is not None:
                        blim = params["budget_limit"]
                        if opt["tot_min"] <= blim:
                            left = blim - opt["tot_min"]
                            fit_disp = f"✅ Fits (+₹{left:,.0f} left)"
                        else:
                            over = opt["tot_min"] - blim
                            fit_disp = f"⚠️ Exceeds by ₹{over:,.0f}"
                    else:
                        fit_disp = "✅ Available"
                    status_badge = "✅ Selected Property" if is_sel else "⚪ Alternative Option"
                    maps_s = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote((item.item_name + ' ' + single_tm_disp).strip())}"
                    maps_d = f"https://www.google.com/maps/dir/?api=1&origin={urllib.parse.quote(single_tm_disp.strip())}&destination={urllib.parse.quote(item.item_name.strip())}&travelmode=driving"

                    lines.append(f"- {name_disp} ({tier_disp} · {p_type})")
                    lines.append(f"  - **Distance**: {dist_val}")
                    lines.append(f"  - **Tariff**: {tar_disp}/night ({nights_cnt} night(s), {rooms_cnt} room(s))")
                    lines.append(f"  - **Stay Total**: {tot_disp}")
                    lines.append(f"  - **Budget Fit**: {fit_disp}")
                    lines.append(f"  - **Status**: {status_badge}")
                    lines.append(f"  - **Google Maps**: [🗺️ View on Google Maps]({maps_s}) | [🧭 Get Directions]({maps_d})")
                lines.append("")

        # 5d. Mandatory & Selected Services Section (Verified Costs)
        lines.append("### Verified Costs & Mandatory Services")
        if entry_items:
            for e in entry_items:
                cost_str = "FREE" if e.is_free else (
                    f"₹{e.min_cost:,.0f} – ₹{e.max_cost:,.0f}" if e.is_range else f"₹{e.min_cost:,.0f}"
                )
                unit_suffix = f" ({e.unit})" if e.unit and e.unit != "fixed" else ""
                lines.append(f"- **{e.item_name}**: {cost_str}{unit_suffix} *(Source: verified temple record)*")
        elif not selected_seva_items and not selected_accom_items:
            lines.append("- **General Darshan**: FREE *(Source: verified temple record)*")

        for s in selected_seva_items:
            cost_str = "FREE" if s.is_free else (
                f"₹{s.min_cost:,.0f} – ₹{s.max_cost:,.0f}" if s.is_range else f"₹{s.min_cost:,.0f}"
            )
            unit_suffix = f" ({s.unit})" if s.unit and s.unit != "fixed" else ""
            lines.append(f"- **{s.item_name}**: {cost_str}{unit_suffix} *(Source: verified temple record)* *(Selected Seva)*")

        for sa in selected_accom_items:
            cost_str = "FREE" if sa.is_free else (
                f"₹{sa.min_cost:,.0f} – ₹{sa.max_cost:,.0f}" if sa.is_range else f"₹{sa.min_cost:,.0f}"
            )
            unit_suffix = f" ({sa.unit})" if sa.unit and sa.unit != "fixed" else ""
            lines.append(f"- **Selected Accommodation — {sa.item_name}**: {cost_str}{unit_suffix} *(Source: verified temple record)*")

        if not (entry_items or selected_seva_items or selected_accom_items):
            lines.append("- No mandatory entry fees or pre-booked sevas required.")
        lines.append("")

        # Discretionary Offerings & Prasadam Section (informational, not added to subtotal)
        if discretionary_items:
            lines.append("### Discretionary Temple Offerings & Prasadam (Counter Rates)")
            for d in discretionary_items[:5]:
                cost_str = "FREE" if d.is_free else (
                    f"₹{d.min_cost:,.0f} – ₹{d.max_cost:,.0f}" if d.is_range else f"₹{d.min_cost:,.0f}"
                )
                unit_suffix = f" ({d.unit})" if d.unit and d.unit != "fixed" else ""
                lines.append(f"- **{d.item_name}**: {cost_str}{unit_suffix} *(Optional counter purchase; not included in baseline subtotal)*")
            lines.append("")

        # Alternative Accommodation Options (if any)
        if alt_accom_items:
            lines.append("### Alternative Accommodation Options")
            for alt in alt_accom_items:
                cost_str = "FREE" if alt.is_free else (
                    f"₹{alt.min_cost:,.0f} – ₹{alt.max_cost:,.0f}" if alt.is_range else f"₹{alt.min_cost:,.0f}"
                )
                unit_suffix = f" ({alt.unit})" if alt.unit and alt.unit != "fixed" else ""
                lines.append(f"- **{alt.item_name}**: {cost_str}{unit_suffix} *(Alternative option)*")
            lines.append("")

        # Optional Sevas (if any)
        if opt_seva_items:
            lines.append("### Optional Sevas")
            for opt in opt_seva_items[:4]:
                cost_str = "FREE" if opt.is_free else (
                    f"₹{opt.min_cost:,.0f} – ₹{opt.max_cost:,.0f}" if opt.is_range else f"₹{opt.min_cost:,.0f}"
                )
                unit_suffix = f" ({opt.unit})" if opt.unit and opt.unit != "fixed" else ""
                lines.append(f"- **{opt.item_name}**: {cost_str}{unit_suffix} *(Optional)*")
            lines.append("")

        # User-Provided Costs Section
        if params.get("user_costs"):
            lines.append("### User-Provided Costs")
            for u in params["user_costs"]:
                cost_str = f"₹{u.min_cost:,.0f}" if u.min_cost == u.max_cost else f"₹{u.min_cost:,.0f} – ₹{u.max_cost:,.0f}"
                lines.append(f"- **{u.item_name}**: {cost_str} *(Source: user-provided)*")
            lines.append("")

        # Calculated Costs / Total Section
        lines.append("### Calculated Costs")
        if overall_quantified and grand_min is not None and grand_max is not None:
            if any_accom_missing:
                if grand_min == 0 and grand_max == 0:
                    lines.append(f"- **Mandatory Entry Subtotal**: **₹0** *(General darshan is free; accommodation tariff for {params.get('nights', 1)} night(s) is unquantified in records)*")
                elif grand_min == grand_max:
                    lines.append(f"- **Mandatory & Selected Costs Subtotal (Excluding Accommodation)**: **₹{grand_min:,.0f}** *(Accommodation tariff for {params.get('nights', 1)} night(s) is unquantified in records)*")
                else:
                    lines.append(f"- **Mandatory & Selected Costs Subtotal (Excluding Accommodation)**: **₹{grand_min:,.0f} – ₹{grand_max:,.0f}** *(Accommodation tariff for {params.get('nights', 1)} night(s) is unquantified in records)*")
            elif grand_min == 0 and grand_max == 0:
                pax_str = f" for {params['pax']} pilgrim(s)" if params.get("pax", 1) > 1 else ""
                lines.append(f"- **Mandatory Temple Entry Subtotal**: **₹0 (Free general darshan{pax_str})**")
                lines.append("- **Partial Known Direct Temple Costs**: **₹0** *(General darshan has no mandatory ticket fee; optional paid sevas not selected)*")
            elif grand_min == grand_max:
                if not is_complete_estimate and is_day_trip:
                    lines.append(f"- **Mandatory & Selected Costs Subtotal**: **₹{grand_min:,.0f}** *(Partial known baseline)*")
                else:
                    lines.append(f"- **Mandatory & Selected Costs Subtotal**: **₹{grand_min:,.0f}**")
            else:
                lines.append(f"- **Mandatory & Selected Costs Subtotal**: **₹{grand_min:,.0f} – ₹{grand_max:,.0f}**")
        else:
            lines.append("- **Mandatory & Selected Costs Subtotal**: *A complete quantified subtotal cannot be calculated from the available static records.*")

        if params.get("budget_limit") is not None:
            blim = params["budget_limit"]
            lines.append(f"- **User Budget Limit**: **₹{blim:,.0f}**")
            if not overall_quantified:
                lines.append(f"- **Budget Status**: ℹ️ **Feasibility cannot be determined** (No quantified tariff records available in knowledge base to compare against ₹{blim:,.0f})")
            elif any_accom_missing:
                lines.append(f"- **Budget Status**: ℹ️ **Incomplete Estimate / Feasibility Cannot Be Confirmed** (Mandatory temple entry is free or known, but accommodation tariffs for {params.get('nights', 1)} night(s) are unquantified in devasthanam records. Cannot confirm if your ₹{blim:,.0f} budget is sufficient until room rates are verified directly with the temple.)")
            elif grand_min == 0 and grand_max == 0:
                lines.append(f"- **Budget Status**: ℹ️ **Mandatory Entry is Free (₹0) — Total Trip Feasibility Incomplete** (Temple general darshan has no mandatory ticket fee, leaving your full ₹{blim:,.0f} budget available for transport, meals, and discretionary sevas. Full trip cost cannot be confirmed within budget because variable travel and meals are unquantified in temple records.)")
            elif not is_complete_estimate and is_day_trip:
                if grand_max <= blim:
                    lines.append(f"- **Budget Status**: ℹ️ **Partial Baseline Within Budget** (Known selected services of ₹{grand_min:,.0f} – ₹{grand_max:,.0f} fit within your ₹{blim:,.0f} budget, but complete trip affordability cannot be confirmed because transport and meals are unquantified.)")
                else:
                    shortfall = (grand_min or 0.0) - blim
                    lines.append(f"- **Budget Status**: ⚠️ **Exceeds Budget** (Selected items start from ₹{grand_min:,.0f}, exceeding your budget of ₹{blim:,.0f} by ₹{shortfall:,.0f})")
            elif grand_max is not None and grand_max <= blim:
                lines.append(f"- **Budget Status**: ✅ **Within Budget** (Mandatory & selected baseline costs ₹{grand_min:,.0f} – ₹{grand_max:,.0f} are fully within your ₹{blim:,.0f} budget. Note that local travel and personal meals are excluded.)")
            elif grand_min is not None and grand_min <= blim:
                excess = (grand_max or 0.0) - blim
                lines.append(f"- **Budget Status**: ⚠️ **Partially Within Budget** (Baseline option starting from ₹{grand_min:,.0f} fits within ₹{blim:,.0f}, but upper room/tariff range up to ₹{grand_max:,.0f} exceeds budget by ₹{excess:,.0f})")
            else:
                shortfall = (grand_min or 0.0) - blim
                lines.append(f"- **Budget Status**: ⚠️ **Exceeds Budget** (Selected plan starts from ₹{grand_min:,.0f}, exceeding your budget of ₹{blim:,.0f} by ₹{shortfall:,.0f})")

        if overall_quantified and params["pax"] > 1 and grand_max is not None and grand_max > 0 and not any_accom_missing:
            per_pax_min = (grand_min or 0.0) / params["pax"]
            per_pax_max = grand_max / params["pax"]
            if per_pax_min == per_pax_max:
                lines.append(f"- **Per Pilgrim**: Approx. ₹{per_pax_min:,.0f}")
            else:
                lines.append(f"- **Per Pilgrim Range**: Approx. ₹{per_pax_min:,.0f} – ₹{per_pax_max:,.0f}")
        lines.append("")

        # Costs Not Available Section
        lines.append("### Costs Not Available")
        if all_unquantified:
            for unq in all_unquantified:
                if unq.category in ["travel", "dining"]:
                    lines.append(f"- **{unq.item_name}**: {unq.raw_price_str}")
                else:
                    lines.append(f"- **{unq.item_name}**: {unq.raw_price_str} *(Unavailable / requires current devasthanam verification)*")
        else:
            lines.append("- None (all requested categories have verified records).")
        lines.append("")

        # Total Section
        lines.append("### Total")
        if overall_quantified and grand_min is not None and grand_max is not None:
            if any_accom_missing:
                lines.append(f"- **Incomplete estimate: ₹{grand_min:,.0f} baseline only** (Mandatory temple entry is known, but accommodation for {params.get('nights', 1)} night(s), local transit, and food are unquantified in records)")
            elif grand_min == 0 and grand_max == 0:
                lines.append("- **Incomplete Estimate: Known baseline is ₹0 (Free General Darshan)**\n*(Total trip expenses cannot be represented as ₹0 because personal travel and food are unquantified. Mandatory temple entry itself is free).*")
            elif not is_complete_estimate and is_day_trip:
                cost_disp = f"₹{grand_min:,.0f}" if grand_min == grand_max else f"₹{grand_min:,.0f} – ₹{grand_max:,.0f}"
                lines.append(f"- **Incomplete Estimate: Partial known baseline is {cost_disp}**\n*(Excludes personal travel and meals which are unquantified in records).*")
            elif grand_min == grand_max:
                lines.append(f"- **₹{grand_min:,.0f}**")
            else:
                lines.append(f"- **₹{grand_min:,.0f} – ₹{grand_max:,.0f}**")
        else:
            if any_accom_missing:
                lines.append(f"- **Incomplete estimate: Verified baseline not available** (Accommodation tariffs for {params.get('nights', 1)} night(s), transport, and food are unquantified in devasthanam records)")
            else:
                lines.append("- **Verified quantified total: Not available**")

        # Excluded items note
        excluded = []
        if not params.get("accom_requested") and params.get("days", 1) <= 1 and params.get("nights", 0) == 0:
            excluded.append("accommodation (day trip query)")
        elif params.get("accom_requested") and not any(it.category == "accommodation" and it.is_quantified for it in all_verified):
            excluded.append("accommodation (no verified accommodation price was available)")
        if not any(u.category == "travel" for u in params.get("user_costs", [])):
            excluded.append("travel (varies by transport provider / not supplied)")
        if not any(u.category == "prasadam" for u in params.get("user_costs", [])) and not any(it.category == "restaurants" for it in all_verified):
            excluded.append("personal dining / food (unless specified)")
        excluded.append("discretionary counter prasadam & optional seva purchases")

        lines.append(f"\n*(Total represents mandatory & selected baseline costs; excludes {', '.join(excluded)}).*")
        lines.append("")

        # Assumptions Section
        lines.append("### Assumptions")
        if params.get("pax", 1) == 1 and params.get("pax_assumed"):
            lines.append("- Group size: 1 person (default assumption)")
        else:
            lines.append(f"- Group size: {params['pax']} pilgrim(s)")

        nights_cnt = params.get("nights", 0)
        if params.get("days", 1) == 1 and params.get("days_assumed") and nights_cnt == 0:
            lines.append("- Duration: 1 day visit (default assumption)")
        elif nights_cnt > 0:
            lines.append(f"- Duration: {params['days']} day(s) ({nights_cnt} overnight stay(s))")
        else:
            lines.append(f"- Duration: {params['days']} day(s)")

        if len(detected_temples) > 1 and nights_cnt > 0:
            dist_desc = ", ".join(f"{TEMPLE_DISPLAY_NAMES.get(t, t.title())}: {temple_allocated_nights.get(t, 0)} night(s)" for t in detected_temples)
            lines.append(f"- Multi-destination stay allocation: Total {nights_cnt} night(s) distributed across destinations ({dist_desc})")

        if params.get("rooms", 1) > 1:
            lines.append(f"- Rooms: {params['rooms']} room(s)")
        lines.append("")

        # Route computation if origin is specified
        origin = params.get("origin")
        route_legs: List[Dict[str, Any]] = []
        is_return_requested = False
        if origin and detected_temples:
            is_return_requested = self._is_return_requested(query, origin)
            first_temple = detected_temples[0]
            legs_spec: List[Tuple[str, str, bool]] = []
            legs_spec.append((origin, first_temple, False))
            for idx in range(len(detected_temples) - 1):
                legs_spec.append((detected_temples[idx], detected_temples[idx + 1], False))
            if is_return_requested:
                legs_spec.append((detected_temples[-1], origin, True))

            for l_idx, (l_orig, l_dest, l_is_return) in enumerate(legs_spec, start=1):
                orig_name, orig_coords, orig_canon = self._resolve_location(l_orig)
                dest_name, dest_coords, dest_canon = self._resolve_location(l_dest)

                orig_waypoint = orig_coords if orig_coords else orig_name
                dest_waypoint = dest_coords if dest_coords else dest_name

                leg_entry: Dict[str, Any] = {
                    "leg_index": l_idx,
                    "origin": l_orig,
                    "destination": l_dest,
                    "origin_canonical": orig_canon,
                    "destination_canonical": dest_canon,
                    "journey_label": f"Return Journey: {l_orig} to {l_dest}" if l_is_return else f"Journey {l_idx}: {l_orig} to {l_dest}",
                    "is_return": l_is_return,
                    "status": "unavailable",
                    "error": None,
                    "distance_km": None,
                    "duration_minutes": None,
                    "traffic_duration_minutes": None,
                    "polyline": None,
                    "viewport": None,
                    "speed_reading_intervals": None,
                }

                try:
                    if not self.navigation_adapter.has_credentials and self.navigation_adapter.transport is None:
                        leg_entry["error"] = "Live route calculation is currently unavailable (navigation provider credential not configured)."
                    else:
                        route_data = self.navigation_adapter.compute_route(
                            origin=orig_waypoint,
                            destination=dest_waypoint,
                            travel_mode="driving"
                        )
                        routes = route_data.get("routes", []) if isinstance(route_data, dict) else []
                        if routes:
                            primary_route = routes[0]
                            dist_km = None
                            if "distanceMeters" in primary_route:
                                try:
                                    dist_km = round(float(primary_route["distanceMeters"]) / 1000.0, 1)
                                except (ValueError, TypeError):
                                    dist_km = None

                            dur_mins = None
                            dur_raw = primary_route.get("duration")
                            if dur_raw:
                                dur_sec = self._parse_duration_seconds(dur_raw)
                                if dur_sec is not None:
                                    dur_mins = round(dur_sec / 60.0, 1)

                            traffic_dur_mins = None
                            static_dur_raw = primary_route.get("staticDuration")
                            if static_dur_raw:
                                static_sec = self._parse_duration_seconds(static_dur_raw)
                                if static_sec is not None and dur_mins is not None:
                                    static_mins = round(static_sec / 60.0, 1)
                                    if abs(dur_mins - static_mins) >= 0.5:
                                        traffic_dur_mins = dur_mins
                                        dur_mins = static_mins

                            polyline = None
                            if "polyline" in primary_route and isinstance(primary_route["polyline"], dict):
                                polyline = primary_route["polyline"].get("encodedPolyline")

                            viewport = primary_route.get("viewport")
                            speed_intervals = None
                            if "travelAdvisory" in primary_route and isinstance(primary_route["travelAdvisory"], dict):
                                speed_intervals = primary_route["travelAdvisory"].get("speedReadingIntervals")

                            leg_entry.update({
                                "status": "success",
                                "distance_km": dist_km,
                                "duration_minutes": dur_mins,
                                "traffic_duration_minutes": traffic_dur_mins,
                                "polyline": polyline,
                                "viewport": viewport,
                                "speed_reading_intervals": speed_intervals,
                            })
                        else:
                            leg_entry["error"] = f"No route found between '{l_orig}' and '{l_dest}'."
                except Exception as e:
                    logger.warning(f"Failed to compute route from {l_orig} to {l_dest}: {e}")
                    leg_entry["error"] = f"Route calculation unavailable: {str(e)}"

                route_legs.append(leg_entry)

            # Insert travel routes presentation in markdown answer
            lines.append(f"### 🚗 Travel & Journey Routes from {origin}")
            for leg in route_legs:
                l_idx = leg["leg_index"]
                orig_l = leg["origin"]
                dest_l = leg["destination"]
                is_ret = leg["is_return"]
                j_title = leg.get("journey_label") or (f"Return Journey: {orig_l} to {dest_l}" if is_ret else f"Journey {l_idx}: {orig_l} to {dest_l}")
                lines.append(f"#### {j_title}")
                lines.append(f"- **Starting Point**: {orig_l}")
                lines.append(f"- **Destination**: {dest_l}")
                if leg["status"] == "success":
                    if leg.get("distance_km") is not None:
                        lines.append(f"- **Driving Distance**: {leg['distance_km']} km")
                    if leg.get("duration_minutes") is not None:
                        dur_lbl = self._format_duration_human(leg["duration_minutes"])
                        lines.append(f"- **Estimated Driving Duration**: {dur_lbl}")
                    if leg.get("traffic_duration_minutes") is not None:
                        traf_lbl = self._format_duration_human(leg["traffic_duration_minutes"])
                        lines.append(f"- **Live Traffic Estimate**: {traf_lbl}")
                else:
                    err_m = leg.get("error") or "Route calculation unavailable"
                    lines.append(f"- **Route Status**: Route details could not be calculated ({err_m}).")
                lines.append("")
            if not is_return_requested:
                lines.append(f"> ℹ️ **Return Journey**: A return leg to {origin} was not requested and is not included in this route schedule.")
                lines.append("")

        # Notes Section
        lines.extend([
            "### Notes",
            "- Verified prices are from the project's static records.",
            "- Prices may change; verify current temple tariffs before payment.",
            "- Official devasthanam tickets and room bookings should be confirmed at the temple enquiry counter."
        ])

        answer_text = html.unescape("\n".join(lines))
        latency_ms = (time.perf_counter() - t0) * 1000.0

        # Metadata
        meta_temples = list(detected_temples)
        for t in detected_temples:
            t_lower = t.lower()
            if t_lower not in meta_temples:
                meta_temples.append(t_lower)
            for k, v in self._get_dynamic_canonical_map().items():
                if v == t and k not in meta_temples:
                    meta_temples.append(k)

        metadata = {
            "temples": meta_temples,
            "parameters": {
                "pax": params["pax"],
                "pax_assumed": params["pax_assumed"],
                "days": params["days"],
                "days_assumed": params["days_assumed"],
                "nights": params.get("nights", 0),
                "rooms": params.get("rooms", 1),
                "budget_limit": params.get("budget_limit"),
                "accom_requested": params["accom_requested"],
                "accommodation_preference": accom_pref,
                "transport_preference": params.get("transport_preference"),
                "food_preference": params.get("food_preference"),
                "origin": params.get("origin")
            },
            "calculated_total": {
                "min": grand_min if grand_min is not None else 0.0,
                "max": grand_max if grand_max is not None else 0.0,
                "currency": "INR",
                "is_quantified": overall_quantified and not any_accom_missing,
                "is_complete_estimate": is_complete_estimate,
                "estimate_type": "complete_trip" if is_complete_estimate else "baseline_subtotal",
                "notes": "Complete estimated trip total" if is_complete_estimate else "Known mandatory/selected baseline subtotal (excludes unquantified personal travel and meals)"
            },
            "verified_item_count": len(all_verified),
            "unquantified_item_count": len(all_unquantified),
            "user_item_count": len(params.get("user_costs", []))
        }

        # Structured accommodation options for frontend comparison & switching
        accom_options_meta = []
        if accom_pref != "none":
            for opt in all_options_eval:
                item = opt["item"]
                is_sel = (item.notes == "Selected Accommodation")
                is_rec = getattr(item, "is_recommended", is_sel)
                dest_name = getattr(item, "destination", None) or getattr(item, "temple", "Trip")
                fit = "within" if (params.get("budget_limit") is None or opt["tot_min"] <= params["budget_limit"]) else "exceeds"
                rem = (params["budget_limit"] - opt["tot_min"]) if params.get("budget_limit") is not None else None
                matches_p = True
                if accom_pref in ["Budget", "Standard / Comfort", "Premium"]:
                    matches_p = (getattr(item, "tier", "") == accom_pref)
                raw_dist = getattr(item, "distance", None)
                if raw_dist:
                    if any(k in raw_dist.lower() for k in [dest_name.lower(), "temple", "near", "ghat"]):
                        clean_dist = raw_dist
                    else:
                        clean_dist = f"Near {dest_name} Temple ({raw_dist})"
                else:
                    clean_dist = f"Near {dest_name} Temple"

                accom_options_meta.append({
                    "name": item.item_name,
                    "destination": dest_name,
                    "temple": getattr(item, "temple", None) or dest_name,
                    "property_type": getattr(item, "property_type", None) or "Lodge / Hotel",
                    "distance": clean_dist,
                    "tier": getattr(item, "tier", None) or "Standard / Comfort",
                    "tariff_min": item.min_cost,
                    "tariff_max": item.max_cost,
                    "stay_cost_min": opt["opt_min"],
                    "stay_cost_max": opt["opt_max"],
                    "nights": getattr(item, "stay_nights", params.get("nights", 1)),
                    "rooms": getattr(item, "stay_rooms", params.get("rooms", 1)),
                    "is_selected": is_sel,
                    "is_recommended": is_rec,
                    "recommendation_label": getattr(item, "recommendation_label", f"Recommended for {dest_name}"),
                    "matches_preference": matches_p,
                    "budget_fit": fit,
                    "remaining_budget": rem,
                    "booking_method": getattr(item, "booking_method", "Direct Counter / Front Desk")
                })

        metadata["accommodation_options"] = accom_options_meta

        # Distinct recommended stays per overnight destination
        recommended_stays_meta = []
        for sa in selected_accom_items:
            dest_name = getattr(sa, "destination", None) or getattr(sa, "temple", "Trip")
            raw_dist_sa = getattr(sa, "distance", None)
            if raw_dist_sa:
                if any(k in raw_dist_sa.lower() for k in [dest_name.lower(), "temple", "near", "ghat"]):
                    clean_dist_sa = raw_dist_sa
                else:
                    clean_dist_sa = f"Near {dest_name} Temple ({raw_dist_sa})"
            else:
                clean_dist_sa = f"Near {dest_name} Temple"

            recommended_stays_meta.append({
                "destination": dest_name,
                "property_name": sa.item_name,
                "tier": getattr(sa, "tier", None) or "Standard / Comfort",
                "property_type": getattr(sa, "property_type", None) or "Lodge / Hotel",
                "distance": clean_dist_sa,
                "tariff_min": sa.min_cost,
                "tariff_max": sa.max_cost,
                "nights": getattr(sa, "stay_nights", 1),
                "rooms": getattr(sa, "stay_rooms", 1),
                "stay_cost_min": getattr(sa, "stay_cost_min", sa.min_cost),
                "stay_cost_max": getattr(sa, "stay_cost_max", sa.max_cost),
                "booking_method": getattr(sa, "booking_method", "Direct Counter / Front Desk"),
                "recommendation_label": f"Recommended for {dest_name}"
            })
        metadata["recommended_stays"] = recommended_stays_meta

        # Category breakdown
        entry_cost_min = sum((e.min_cost or 0.0) * (params["pax"] if e.unit == "per person" else 1) for e in entry_items)
        entry_cost_max = sum((e.max_cost or 0.0) * (params["pax"] if e.unit == "per person" else 1) for e in entry_items)
        sevas_cost_min = sum((s.min_cost or 0.0) * (params["pax"] if s.unit == "per person" else 1) for s in selected_seva_items)
        sevas_cost_max = sum((s.max_cost or 0.0) * (params["pax"] if s.unit == "per person" else 1) for s in selected_seva_items)
        stay_cost_min = sum((sa.stay_cost_min or 0.0) for sa in selected_accom_items)
        stay_cost_max = sum((sa.stay_cost_max or 0.0) for sa in selected_accom_items)
        travel_cost_min = sum((u.min_cost or 0.0) for u in params.get("user_costs", []) if u.category == "travel")
        travel_cost_max = sum((u.max_cost or 0.0) for u in params.get("user_costs", []) if u.category == "travel")
        food_cost_min = sum((u.min_cost or 0.0) for u in params.get("user_costs", []) if u.category in ["food", "prasadam"])
        food_cost_max = sum((u.max_cost or 0.0) for u in params.get("user_costs", []) if u.category in ["food", "prasadam"])

        b_status = "unknown"
        if params.get("budget_limit") is not None:
            blim = params["budget_limit"]
            if grand_max is not None and grand_max <= blim:
                b_status = "within"
            elif grand_min is not None and grand_min <= blim:
                b_status = "partially_within"
            else:
                b_status = "exceeds"

        metadata["budget_breakdown"] = {
            "entry_min": entry_cost_min,
            "entry_max": entry_cost_max,
            "sevas_min": sevas_cost_min,
            "sevas_max": sevas_cost_max,
            "accommodation_min": stay_cost_min,
            "accommodation_max": stay_cost_max,
            "travel_min": travel_cost_min,
            "travel_max": travel_cost_max,
            "food_min": food_cost_min,
            "food_max": food_cost_max,
            "total_min": grand_min if grand_min is not None else 0.0,
            "total_max": grand_max if grand_max is not None else 0.0,
            "budget_limit": params.get("budget_limit"),
            "status": b_status
        }

        if origin and route_legs:
            metadata["origin"] = origin
            metadata["destination"] = detected_temples[0] if detected_temples else None
            metadata["return_leg_requested"] = is_return_requested
            metadata["route_legs"] = route_legs
            first_leg_res = route_legs[0]
            if first_leg_res.get("origin_canonical"):
                metadata["origin_canonical"] = first_leg_res["origin_canonical"]
            if first_leg_res.get("destination_canonical"):
                metadata["destination_canonical"] = first_leg_res["destination_canonical"]
            if first_leg_res.get("distance_km") is not None:
                metadata["distance_km"] = first_leg_res["distance_km"]
            if first_leg_res.get("duration_minutes") is not None:
                metadata["duration_minutes"] = first_leg_res["duration_minutes"]
            if first_leg_res.get("traffic_duration_minutes") is not None:
                metadata["traffic_duration_minutes"] = first_leg_res["traffic_duration_minutes"]
            if first_leg_res.get("polyline"):
                metadata["polyline"] = first_leg_res["polyline"]
            if first_leg_res.get("viewport"):
                metadata["viewport"] = first_leg_res["viewport"]
            if first_leg_res.get("speed_reading_intervals"):
                metadata["speed_reading_intervals"] = first_leg_res["speed_reading_intervals"]
            if len(route_legs) > 1:
                succ_distances = [l["distance_km"] for l in route_legs if l.get("distance_km") is not None]
                if succ_distances:
                    metadata["total_distance_km"] = round(sum(succ_distances), 1)
                succ_durations = [l["duration_minutes"] for l in route_legs if l.get("duration_minutes") is not None]
                if succ_durations:
                    metadata["total_duration_minutes"] = round(sum(succ_durations), 1)

        return AgentResponse(
            success=True,
            agent_name=self.name,
            answer=answer_text,
            sources=sorted(list(all_sources)),
            latency_ms=latency_ms,
            metadata=metadata
        )

