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
import time
import logging
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


# =====================================================================
# Canonical Temple Mapping
# =====================================================================

TEMPLE_CANONICAL_MAP = {
    "ahobilam": "ahobilam",
    "badrachalam": "badrachalam",
    "bhadrachalam": "badrachalam",
    "balkampet": "balkampet",
    "basara": "basara_gnana_saraswathi",
    "basar": "basara_gnana_saraswathi",
    "basara_gnana_saraswathi": "basara_gnana_saraswathi",
    "birla mandir": "birla_mandir",
    "birla": "birla_mandir",
    "chilkur": "chilkur_balaji",
    "chilkur balaji": "chilkur_balaji",
    "dharmapuri": "dharmapuri_lakshmi_narasimha",
    "dharmapuri_lakshmi_narasimha": "dharmapuri_lakshmi_narasimha",
    "edupayal": "edupayala_durga_bhavani",
    "edupayala": "edupayala_durga_bhavani",
    "jogulamba": "jogulamba",
    "jogulamba(new)": "jogulamba",
    "kaleshvaram": "kaleshwaram_mukteshwara",
    "kaleshwaram": "kaleshwaram_mukteshwara",
    "karmanghat": "karmanghat_hanuman",
    "medaram": "medaram_sammakka_saralamma",
    "ramappa": "ramappa",
    "srisaila": "srisailam",
    "srisailam": "srisailam",
    "thousand pillar": "thousand_pillar",
    "ttd": "tirumala_tirupati",
    "tirupati": "tirumala_tirupati",
    "tirumala": "tirumala_tirupati",
    "ujjaini": "ujjaini_mahakali",
    "veera satyanarayana": "veera_venkata_satyanarayana",
    "annavaram": "veera_venkata_satyanarayana",
    "vemulavada": "vemulawada_rajarajeshwara",
    "vemulawada": "vemulawada_rajarajeshwara",
    "yadadri": "yadadri"
}

TEMPLE_DISPLAY_NAMES = {
    "ahobilam": "Ahobilam",
    "badrachalam": "Bhadrachalam",
    "balkampet": "Balkampet Yellamma",
    "basara_gnana_saraswathi": "Basara Gnana Saraswathi",
    "birla_mandir": "Birla Mandir",
    "chilkur_balaji": "Chilkur Balaji",
    "dharmapuri_lakshmi_narasimha": "Dharmapuri Lakshmi Narasimha",
    "edupayala_durga_bhavani": "Edupayala Vana Durga Bhavani",
    "jogulamba": "Alampur Jogulamba",
    "kaleshwaram_mukteshwara": "Kaleshwaram Mukteshwara Swamy",
    "karmanghat_hanuman": "Karmanghat Hanuman",
    "medaram_sammakka_saralamma": "Medaram Sammakka Saralamma",
    "ramappa": "Ramappa Temple",
    "srisailam": "Srisailam Mallikarjuna",
    "thousand_pillar": "Thousand Pillar Temple",
    "tirumala_tirupati": "Tirumala Tirupati Devasthanam",
    "ujjaini_mahakali": "Ujjaini Mahakali",
    "veera_venkata_satyanarayana": "Annavaram Veera Venkata Satyanarayana",
    "vemulawada_rajarajeshwara": "Vemulawada Raja Rajeshwara",
    "yadadri": "Yadadri Lakshmi Narasimha"
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
    if any(w in s_lower for w in ["free", "no ticket required", "0/-", "zero", "complimentary"]):
        # Verify it is not "free general, ₹500 special"
        if not re.search(r"[1-9]\d{1,6}", s_lower):
            return (0.0, 0.0, "per person", True, False, True, "Free of charge")

    # 2. Check for explicit unquantified/variable indicators without concrete numbers
    unquantified_markers = ["varies", "nominal fee", "contact office", "not specified", "endowment fund", "subject to change", "variable contribution"]
    has_unquantified_marker = any(m in s_lower for m in unquantified_markers)

    # Clean commas inside numbers: e.g. 1,000 -> 1000
    num_clean = re.sub(r'(?<=\d),(?=\d)', '', s_lower)

    # 3. Detect pricing unit
    unit_text = "per service"
    if "per person" in s_lower or "per head" in s_lower or "each person" in s_lower or "/person" in s_lower:
        unit_text = "per person"
    elif "per couple" in s_lower or "for couple" in s_lower or "2 persons" in s_lower:
        unit_text = "per couple"
    elif "per room" in s_lower and ("night" in s_lower or "/night" in s_lower):
        unit_text = "per room per night"
    elif "per room" in s_lower:
        unit_text = "per room"
    elif "per night" in s_lower or "/night" in s_lower:
        unit_text = "per room per night"
    elif category.lower() == "accommodation" and ("room" in s_lower or "suite" in s_lower or "cottage" in s_lower):
        unit_text = "per room per night"
    elif category.lower() == "prasadam" or "per packet" in s_lower or "per laddu" in s_lower or "per piece" in s_lower:
        unit_text = "per item"
    elif "per vehicle" in s_lower:
        unit_text = "per vehicle"

    # 4. Extract numeric values
    found_nums = [float(n) for n in re.findall(r'\b\d+(?:\.\d+)?\b', num_clean)]

    # Filter out extraneous numbers like times (04:30 AM) or bed counts (2 beds -> 2)
    filtered_nums = []
    for n in found_nums:
        if re.search(r'\b' + re.escape(str(int(n))) + r'\s*(?:bed|beds|hour|hours|am|pm|kg|g|gm)\b', s_lower):
            continue
        filtered_nums.append(n)

    if not filtered_nums:
        if has_unquantified_marker:
            return (None, None, unit_text, False, False, False, clean_str)
        return (None, None, unit_text, False, False, False, "Price unquantified in records")

    if len(filtered_nums) == 1:
        val = filtered_nums[0]
        return (val, val, unit_text, val == 0.0, False, True, clean_str)

    # Two or more numbers: evaluate if it represents a range (e.g. 100 - 300, 100 to 300)
    range_match = re.search(
        r'(\d+(?:\.\d+)?)\s*(?:-|–|—|to)\s*(?:rs\.?|inr|₹)?\s*(\d+(?:\.\d+)?)',
        num_clean
    )
    if range_match:
        val1 = float(range_match.group(1))
        val2 = float(range_match.group(2))
        min_v = min(val1, val2)
        max_v = max(val1, val2)
        return (min_v, max_v, unit_text, False, True, True, clean_str)

    # Fallback for multiple numbers without explicit range syntax
    min_v = min(filtered_nums)
    max_v = max(filtered_nums)
    return (min_v, max_v, unit_text, False, min_v != max_v, True, clean_str)


# =====================================================================
# Parameter Extraction
# =====================================================================

def extract_budget_parameters(query: str) -> Dict[str, Any]:
    """
    Deterministically extracts user parameters:
    - group size / persons (default: 1)
    - duration / days (default: 1)
    - user-provided costs (e.g. travel, hotel, food)
    - specific seva requests (e.g. nitya kalyanam, abhishekam, kalyanotsavam, aksharabhyasam)
    - accommodation requests & preference (ac, non_ac, cottage, dormitory)
    """
    q_norm = query.lower()

    # 1. Group size / Persons
    pax = 1
    pax_assumed = True
    pax_match = re.search(r"\b(\d+)\s*(?:people|persons?|devotees?|members?|pilgrims?|adults?)\b", q_norm)
    if pax_match:
        pax = max(1, int(pax_match.group(1)))
        pax_assumed = False
    else:
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

    # 2. Duration / Days
    days = 1
    days_assumed = True
    day_match = re.search(r"\b(\d+)\s*[- ]*(?:days?|day)\b", q_norm)
    if day_match:
        days = max(1, int(day_match.group(1)))
        days_assumed = False
    elif "weekend" in q_norm:
        days = 2
        days_assumed = False
    elif any(w in q_norm for w in ["one day", "1 day", "single day", "one-day", "for 1 day", "for one day"]):
        days = 1
        days_assumed = False
    elif any(w in q_norm for w in ["two days", "2 days", "two day", "two-day", "for 2 days", "for two days", "2 day"]):
        days = 2
        days_assumed = False
    elif any(w in q_norm for w in ["three days", "3 days", "three day", "three-day", "for 3 days", "for three days"]):
        days = 3
        days_assumed = False
    elif any(w in q_norm for w in ["four days", "4 days", "four day", "four-day"]):
        days = 4
        days_assumed = False

    # Budget limit extraction
    budget_limit = None
    b_match = re.search(
        r"\b(?:budget\s+(?:of\s+)?|under\s+(?:a\s+budget\s+of\s+)?|within\s+(?:a\s+budget\s+of\s+)?|below\s+(?:a\s+budget\s+of\s+)?)(?:rs\.?|inr|₹)?\s*(\d+(?:,\d+)?(?:\.\d+)?)\b",
        q_norm
    )
    if b_match:
        budget_limit = float(b_match.group(1).replace(",", ""))
    else:
        b_match2 = re.search(
            r"\b(?:rs\.?|inr|₹)\s*(\d+(?:,\d+)?(?:\.\d+)?)\s*(?:budget|limit)\b",
            q_norm
        )
        if b_match2:
            budget_limit = float(b_match2.group(1).replace(",", ""))

    # 3. Accommodation requested & type
    accom_requested = any(w in q_norm for w in [
        "stay", "room", "rooms", "hotel", "hotels", "accommodation",
        "cottage", "cottages", "choultry", "guest house", "night", "nights",
        "dormitory", "including accommodation", "with accommodation", "including stay"
    ])
    accom_type = None
    if "non-ac" in q_norm or "non ac" in q_norm or "non_ac" in q_norm:
        accom_type = "non_ac"
    elif re.search(r"\bac\b", q_norm) or "deluxe" in q_norm:
        accom_type = "ac"
    elif "cottage" in q_norm:
        accom_type = "cottage"
    elif "dormitory" in q_norm or "choultry" in q_norm:
        accom_type = "dormitory"

    # 4. Specific Seva extraction
    specific_seva = None
    known_sevas = [
        "nitya kalyanam", "kalyanotsavam", "kalyanam",
        "nijabhishekam", "abhishekam",
        "aksharabhyasam", "special aksharabhyasam",
        "sudarshana homam", "homam",
        "sahasranamarchana", "archana",
        "special darshan", "vip darshan", "darshan"
    ]
    for ks in known_sevas:
        if re.search(r"\b" + re.escape(ks) + r"\b", q_norm):
            specific_seva = ks
            break

    # 5. User-provided explicit costs
    user_costs: List[BudgetItem] = []

    # Travel user cost
    travel_match = re.search(
        r"\b(?:my\s+)?(?:travel|transit|bus|train|cab|taxi|flight|transport|fare)\s*(?:cost|is|will\s+be|estimated\s+at)?\s*(?:rs\.?|inr|₹)?\s*(\d+(?:,\d+)?(?:\.\d+)?)\b",
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
        r"\b(?:my\s+)?(?:hotel|room|accommodation|stay|lodge)\s*(?:cost|is|will\s+be)?\s*(?:rs\.?|inr|₹)?\s*(\d+(?:,\d+)?(?:\.\d+)?)\b",
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
        r"\b(?:my\s+)?(?:food|meals?|dining|prasadam|lunch|dinner|breakfast)\s*(?:cost|is|will\s+be)?\s*(?:rs\.?|inr|₹)?\s*(\d+(?:,\d+)?(?:\.\d+)?)\b",
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

    return {
        "pax": pax,
        "pax_assumed": pax_assumed,
        "days": days,
        "days_assumed": days_assumed,
        "budget_limit": budget_limit,
        "accom_requested": accom_requested,
        "accom_type": accom_type,
        "specific_seva": specific_seva,
        "user_costs": user_costs
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
        description: str = "Specialist agent calculating grounded pilgrimage budgets and itemized cost breakdowns using verified temple records and user-supplied parameters."
    ):
        super().__init__(name=name, description=description)
        self._rag_tool = rag_tool

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

    def process(self, state: AgentState) -> AgentResponse:
        """Alias to execute for consistent agent invocation across callers."""
        return self.execute(state)

    def _extract_parameters(self, query: str) -> Dict[str, Any]:
        """Deterministically extracts user parameters via extract_budget_parameters."""
        return extract_budget_parameters(query)

    def _resolve_temples(self, state: AgentState) -> List[str]:
        """Resolves target canonical temple folder IDs from routing decision or query text."""
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
            if t_clean in TEMPLE_CANONICAL_MAP:
                c_id = TEMPLE_CANONICAL_MAP[t_clean]
                if c_id not in canonical_temples:
                    canonical_temples.append(c_id)
            else:
                for k, v in TEMPLE_CANONICAL_MAP.items():
                    if k in t_clean or t_clean in k:
                        if v not in canonical_temples:
                            canonical_temples.append(v)
                        break

        if canonical_temples:
            return canonical_temples

        # 3. Extract directly from user query
        query = state.user_query or ""
        q_norm = query.lower()

        matched = []
        # Check longest keys first
        for alias in sorted(TEMPLE_CANONICAL_MAP.keys(), key=len, reverse=True):
            pattern = r'\b' + re.escape(alias) + r'\b'
            if re.search(pattern, q_norm):
                c_id = TEMPLE_CANONICAL_MAP[alias]
                if c_id not in matched:
                    matched.append(c_id)

        return matched

    def _fetch_category(self, temple: str, category: str) -> Optional[Any]:
        """Fetches category data from RAGTool with canonical and fallback key lookup."""
        data = self.rag_tool.get_temple_category_data(temple, category)
        if data:
            return data
        # Fallback to display name or short name
        display_name = TEMPLE_DISPLAY_NAMES.get(temple, temple.split("_")[0].capitalize())
        data = self.rag_tool.get_temple_category_data(display_name, category)
        if data:
            return data
        short_name = temple.split("_")[0].capitalize()
        return self.rag_tool.get_temple_category_data(short_name, category)

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
        # Add entry fee if general query, or if fee / ticket / entry / darshan fee is requested
        if not params.get("specific_seva") or any(w in q_norm for w in ["general", "entry", "fee", "ticket", "darshan fee"]) or params.get("specific_seva") == "darshan":
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
                            source_path=f"{temple}/timings.json"
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
            specific_seva_found = False
            for s in sevas_list:
                s_name = s.get("name") or s.get("seva_name") or s.get("title") or ""
                if not s_name:
                    continue
                name_words = [w.lower() for w in s_name.split() if len(w) >= 4]
                is_match = (s_name.lower() in q_norm) or any(w in q_norm for w in name_words)
                if is_match:
                    p_str = s.get("price") or s.get("price_status") or s.get("cost") or ""
                    min_v, max_v, unit_t, is_free, is_rng, is_q, notes = parse_price_text(str(p_str), category="sevas")
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
                        source_path=f"{temple}/sevas.json",
                        notes=notes
                    )
                    if is_q:
                        verified.append(item)
                    else:
                        unquantified.append(item)
                    specific_seva_found = True
                    break

            if not specific_seva_found:
                added_count = 0
                for s in sevas_list:
                    s_name = s.get("name") or s.get("seva_name") or s.get("title") or ""
                    p_str = s.get("price") or s.get("price_status") or s.get("cost") or ""
                    if not p_str or not s_name:
                        continue
                    min_v, max_v, unit_t, is_free, is_rng, is_q, notes = parse_price_text(str(p_str), category="sevas")
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
                        source_path=f"{temple}/sevas.json",
                        notes=notes
                    )
                    if is_q:
                        if added_count < 2:
                            verified.append(item)
                            added_count += 1
                    else:
                        if len(unquantified) < 1:
                            unquantified.append(item)

        # 3. Accommodation (if requested, or user mentions stay, or overnight)
        if params.get("accom_requested") or params.get("days", 1) > 1:
            accom_data = self._fetch_category(temple, "accommodation")
            accom_list = []
            if isinstance(accom_data, list):
                accom_list = accom_data
            elif isinstance(accom_data, dict):
                for v in accom_data.values():
                    if isinstance(v, list):
                        accom_list.extend(v)

            if accom_list:
                added_rooms = 0
                pref = params.get("accom_type")
                if pref == "ac":
                    accom_list = [r for r in accom_list if "ac" in (r.get("type") or r.get("name", "")).lower() and "non" not in (r.get("type") or r.get("name", "")).lower()] + [r for r in accom_list if "ac" not in (r.get("type") or r.get("name", "")).lower()]
                elif pref == "non_ac":
                    accom_list = [r for r in accom_list if "non" in (r.get("type") or r.get("name", "")).lower()] + [r for r in accom_list if "non" not in (r.get("type") or r.get("name", "")).lower()]
                elif pref == "cottage":
                    accom_list = [r for r in accom_list if "cottage" in (r.get("type") or r.get("name", "")).lower()] + [r for r in accom_list if "cottage" not in (r.get("type") or r.get("name", "")).lower()]

                for r in accom_list:
                    r_name = r.get("type") or r.get("name") or r.get("room_type") or "Accommodation"
                    p_str = r.get("tariff") or r.get("price") or r.get("rate") or r.get("cost") or ""
                    if not p_str:
                        continue
                    min_v, max_v, unit_t, is_free, is_rng, is_q, notes = parse_price_text(str(p_str), category="accommodation")
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
                        source_path=f"{temple}/accommodation.json",
                        notes=notes
                    )
                    if is_q:
                        if added_rooms < (1 if pref else 2):
                            verified.append(item)
                            added_rooms += 1
                    else:
                        unquantified.append(item)
            else:
                # Accommodation was requested but temple has no verified accommodation records
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
                    raw_price_str="Not specified in temple devasthanam records",
                    source_path=f"{temple}/accommodation.json",
                    notes="Requires direct devasthanam counter verification"
                ))

        # 4. Prasadam
        include_prasadam = any(w in q_norm for w in ["prasadam", "laddu", "food", "budget", "cost of trip", "visit", "trip", "tour"]) or not params.get("specific_seva")
        if include_prasadam:
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
                        source_path=f"{temple}/prasadam.json",
                        notes=notes
                    )
                    if is_q:
                        if added_p < 2:
                            verified.append(item)
                            added_p += 1
                    else:
                        if len(unquantified) < 2:
                            unquantified.append(item)

        # 5. Restaurants / Dining (if requested or user asks for food/meals)
        if any(w in q_norm for w in ["food", "meal", "meals", "restaurant", "restaurants", "dining", "lunch", "dinner"]):
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
                    item = BudgetItem(
                        category="restaurants",
                        item_name=r_name,
                        min_cost=min_v,
                        max_cost=max_v,
                        unit=unit_t,
                        is_free=is_free,
                        is_range=is_rng,
                        is_quantified=is_q,
                        provenance=CostProvenance.VERIFIED if is_q else CostProvenance.UNAVAILABLE,
                        raw_price_str=str(p_str),
                        source_path=f"{temple}/restaurants.json",
                        notes=notes
                    )
                    if is_q:
                        verified.append(item)
                    else:
                        unquantified.append(item)

        return verified, unquantified

    def _calculate_totals(
        self,
        verified_items: List[BudgetItem],
        user_items: List[BudgetItem],
        params: Dict[str, Any]
    ) -> Tuple[float, float, List[str]]:
        """
        Deterministically calculates min and max total expenditures.
        Multiplies by person count or nights only when the pricing unit supports it.
        Treats multiple accommodation room tiers as alternative options rather than additive costs.
        Returns (min_total, max_total, notes_list).
        """
        min_total = 0.0
        max_total = 0.0
        notes = []

        pax = params.get("pax", 1)
        nights = max(1, params.get("days", 1) - 1) if params.get("days", 1) > 1 else 1

        all_items = verified_items + user_items

        # Separate accommodation items (mutually exclusive room tiers) from other expenses
        accom_items = [
            it for it in all_items
            if it.category == "accommodation" and it.is_quantified and it.min_cost is not None and it.max_cost is not None
        ]
        other_items = [
            it for it in all_items
            if it.category != "accommodation" and it.is_quantified and it.min_cost is not None and it.max_cost is not None
        ]

        for item in other_items:
            item_min = item.min_cost
            item_max = item.max_cost

            # Unit multiplication rules
            if item.unit == "per person":
                item_min *= pax
                item_max *= pax
                if pax > 1:
                    notes.append(f"{item.item_name}: scaled for {pax} pilgrims")

            min_total += item_min
            max_total += item_max

        # Process accommodation alternatives
        if accom_items:
            scaled_accom: List[Tuple[float, float]] = []
            for item in accom_items:
                item_min = item.min_cost
                item_max = item.max_cost
                if params.get("days", 1) > 1:
                    item_min *= nights
                    item_max *= nights
                    notes.append(f"{item.item_name}: scaled for {nights} night(s)")
                scaled_accom.append((item_min, item_max))

            min_accom = min(sa[0] for sa in scaled_accom)
            max_accom = max(sa[1] for sa in scaled_accom)

            min_total += min_accom
            max_total += max_accom

            if len(accom_items) > 1:
                notes.append(f"Accommodation: evaluated as alternative room choices (₹{min_accom:,.0f} to ₹{max_accom:,.0f})")

        return min_total, max_total, notes

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
        params = self._extract_parameters(query)

        # Merge structured constraints if passed from upstream pipeline
        if getattr(state, "structured_constraints", None):
            sc = state.structured_constraints
            if "duration_days" in sc and not sc.get("days_assumed", True):
                params["days"] = sc["duration_days"]
                params["days_assumed"] = False
            elif "duration_days" in sc and params.get("days_assumed", True):
                params["days"] = sc["duration_days"]
                params["days_assumed"] = sc.get("days_assumed", False)
            if "budget_limit" in sc and sc["budget_limit"] is not None:
                params["budget_limit"] = sc["budget_limit"]
            if sc.get("accommodation_required"):
                params["accom_requested"] = True
            if not sc.get("pax_assumed", True) and "pax" in sc:
                params["pax"] = sc["pax"]
                params["pax_assumed"] = False

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
        grand_min = 0.0
        grand_max = 0.0
        all_verified: List[BudgetItem] = []
        all_unquantified: List[BudgetItem] = []

        for temple in detected_temples:
            verified_items, unquantified_items = self._fetch_verified_costs(temple, query, params)
            all_verified.extend(verified_items)
            all_unquantified.extend(unquantified_items)

            for it in verified_items:
                if it.source_path:
                    all_sources.add(it.source_path)

            t_min, t_max, t_notes = self._calculate_totals(
                verified_items,
                params.get("user_costs", []) if len(detected_temples) == 1 else [],
                params
            )
            grand_min += t_min
            grand_max += t_max

        # Add user-provided costs to grand total if multi-temple
        if len(detected_temples) > 1 and params.get("user_costs"):
            u_min = sum(u.min_cost for u in params["user_costs"] if u.min_cost is not None)
            u_max = sum(u.max_cost for u in params["user_costs"] if u.max_cost is not None)
            grand_min += u_min
            grand_max += u_max

        # Display names for title
        temple_titles = [TEMPLE_DISPLAY_NAMES.get(t, t.title()) for t in detected_temples]

        # 5. Build Final Markdown Response (Section 16 Specification)
        lines = [f"## 💰 Pilgrimage Budget — {', '.join(temple_titles)}", ""]

        # Verified Costs Section
        lines.append("### Verified Costs")
        if all_verified:
            accom_count = sum(1 for it in all_verified if it.category == "accommodation")
            for it in all_verified:
                cost_str = "FREE" if it.is_free else (
                    f"₹{it.min_cost:,.0f} – ₹{it.max_cost:,.0f}" if it.is_range else f"₹{it.min_cost:,.0f}"
                )
                unit_suffix = f" ({it.unit})" if it.unit and it.unit != "fixed" else ""
                alt_suffix = " *(Alternative option)*" if it.category == "accommodation" and accom_count > 1 else ""
                lines.append(f"- **{it.item_name}**: {cost_str}{unit_suffix} *(Source: verified temple record)*{alt_suffix}")
        else:
            lines.append("- No specific quantified tariff records found for requested categories.")
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
        if grand_min == grand_max:
            lines.append(f"- **Calculated Total**: **₹{grand_min:,.0f}**")
        else:
            lines.append(f"- **Calculated Total Range**: **₹{grand_min:,.0f} – ₹{grand_max:,.0f}**")

        if params.get("budget_limit") is not None:
            blim = params["budget_limit"]
            lines.append(f"- **User Budget Limit**: **₹{blim:,.0f}**")
            if grand_max <= blim:
                lines.append(f"- **Budget Status**: ✅ **Within Budget** (Calculated total ₹{grand_min:,.0f} – ₹{grand_max:,.0f} is within ₹{blim:,.0f})")
            elif grand_min <= blim < grand_max:
                lines.append(f"- **Budget Status**: ⚠️ **Partially Within Budget** (Minimum options ₹{grand_min:,.0f} fit within ₹{blim:,.0f}, while higher tiers reach ₹{grand_max:,.0f})")
            else:
                lines.append(f"- **Budget Status**: ⚠️ **Exceeds Budget** (Calculated verified baseline ₹{grand_min:,.0f} exceeds ₹{blim:,.0f})")

        if params["pax"] > 1 and grand_max > 0:
            per_pax_min = grand_min / params["pax"]
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
                lines.append(f"- **{unq.item_name}**: {unq.raw_price_str} *(Unavailable / requires current devasthanam verification)*")
        else:
            lines.append("- None (all requested categories have verified records).")
        lines.append("")

        # Total Section
        lines.append("### Total")
        if grand_min == grand_max:
            lines.append(f"- **₹{grand_min:,.0f}**")
        else:
            lines.append(f"- **₹{grand_min:,.0f} – ₹{grand_max:,.0f}**")

        # Excluded items note
        excluded = []
        if not params.get("accom_requested") and params.get("days", 1) <= 1:
            excluded.append("accommodation (day trip query)")
        elif params.get("accom_requested") and not any(it.category == "accommodation" and it.is_quantified for it in all_verified):
            excluded.append("accommodation (no verified accommodation price was available)")
        if not any(u.category == "travel" for u in params.get("user_costs", [])):
            excluded.append("travel (varies by transport provider / not supplied)")
        if not any(u.category == "prasadam" for u in params.get("user_costs", [])) and not any(it.category == "restaurants" for it in all_verified):
            excluded.append("personal dining / food (unless specified)")

        if excluded:
            lines.append(f"\n*(Total excludes {', '.join(excluded)}).*")
        lines.append("")

        # Assumptions Section
        lines.append("### Assumptions")
        if params.get("pax", 1) == 1 and params.get("pax_assumed"):
            lines.append("- Group size: 1 person (default assumption)")
        else:
            lines.append(f"- Group size: {params['pax']} pilgrim(s)")

        if params.get("days", 1) == 1 and params.get("days_assumed"):
            lines.append("- Duration: 1 day visit (default assumption)")
        else:
            lines.append(f"- Duration: {params['days']} day(s)")
        lines.append("")

        # Notes Section
        lines.extend([
            "### Notes",
            "- Verified prices are from the project's static records.",
            "- Prices may change; verify current temple tariffs before payment.",
            "- Official devasthanam tickets and room bookings should be confirmed at the temple enquiry counter."
        ])

        answer_text = "\n".join(lines)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        # Metadata
        metadata = {
            "temples": detected_temples,
            "parameters": {
                "pax": params["pax"],
                "pax_assumed": params["pax_assumed"],
                "days": params["days"],
                "days_assumed": params["days_assumed"],
                "budget_limit": params.get("budget_limit"),
                "accom_requested": params["accom_requested"]
            },
            "calculated_total": {
                "min": grand_min,
                "max": grand_max,
                "currency": "INR"
            },
            "verified_item_count": len(all_verified),
            "unquantified_item_count": len(all_unquantified),
            "user_item_count": len(params.get("user_costs", []))
        }

        return AgentResponse(
            success=True,
            agent_name=self.name,
            answer=answer_text,
            sources=sorted(list(all_sources)),
            latency_ms=latency_ms,
            metadata=metadata
        )
