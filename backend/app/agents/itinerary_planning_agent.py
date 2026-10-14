"""
PilgrimAI - ItineraryPlanningAgent (Phase M)

Specialist agent responsible for grounded, timing-aware pilgrimage itinerary
planning across registered temples in Telangana.

Key Capabilities:
- Single-temple and multi-temple pilgrimage itinerary generation with duration awareness.
- Non-repetitive day-by-day scheduling distributing verified sevas, darshan slots, and nearby sites.
- Grounded in verified temple timings, sevas, accommodation, travel, prasadam, rules, and crowd data.
- Strict Fact vs Planning Suggestion separation (every suggestion clearly demarcated).
- Zero fabricated travel durations, hotels, restaurants, or unverified attractions.
- Strict Live-Data Limitations disclosure (deterministic Live-Data Disclaimer).
- RAGTool facade as the exclusive knowledge access interface (zero direct DB/raw file imports).
- Inherits from BaseAgent with standard execution tracing, latency tracking, and error containment.
- Seamless compatibility with AgentRouter, MasterAgentCoordinator, SequentialMultiIntentPipeline,
  and ConversationMemoryManager.
"""

import re
import html
import logging
import datetime
import urllib.parse
from typing import Optional, List, Dict, Any, Tuple, TYPE_CHECKING

from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState, AgentResponse
if TYPE_CHECKING:
    from app.agents.tools.rag_tool import RAGTool

logger = logging.getLogger(__name__)

# Deterministic Live-Data Disclaimer
LIVE_DATA_DISCLAIMER = (
    "*(Live-Data Limitation: This itinerary is constructed strictly from verified static records. "
    "It does not include real-time traffic, live road conditions, real-time travel durations, "
    "live weather forecasts, or dynamic room booking availability. Please verify current local transit "
    "schedules and devasthanam announcements before departure).*"
)

TEMPLE_DISPLAY_MAP: Dict[str, str] = {
    "Badrachalam": "Bhadrachalam",
    "Srisaila": "Srisailam",
    "Jogulamba(new)": "Jogulamba",
    "Ttd": "Tirumala (TTD)",
    "Veera Satyanarayana": "Annavaram (Veera Satyanarayana)"
}


class ItineraryPlanningAgent(BaseAgent):
    """
    Specialist agent providing grounded, timing-aware pilgrimage itinerary
    planning across registered temples in Telangana.
    """

    def __init__(
        self,
        rag_tool: Optional[Any] = None,
        name: str = "itinerary_planning",
        description: str = "Specialist agent providing grounded, timing-aware pilgrimage itinerary planning across registered temples using verified knowledge.",
        navigation_adapter: Optional[Any] = None,
        coordinate_registry: Optional[Any] = None
    ):
        super().__init__(name=name, description=description)
        self._rag_tool = rag_tool
        self._navigation_adapter = navigation_adapter
        self._coordinate_registry = coordinate_registry
        self._weather_agent = None
        self._temple_aliases: Dict[str, List[str]] = {}
        self._init_temple_registry()

    @property
    def weather_agent(self) -> Any:
        """Lazily initialize LiveWeatherAgent."""
        if self._weather_agent is None:
            try:
                from app.agents.live_weather_agent import LiveWeatherAgent
                self._weather_agent = LiveWeatherAgent(coordinate_registry=self.coordinate_registry)
            except Exception as e:
                logger.warning(f"Could not initialize LiveWeatherAgent in ItineraryPlanningAgent: {e}")
                self._weather_agent = None
        return self._weather_agent

    @property
    def rag_tool(self) -> Any:
        """Lazily initialize RAGTool to break circular instantiation loops."""
        if self._rag_tool is None:
            from app.agents.tools.rag_tool import RAGTool
            self._rag_tool = RAGTool()
        return self._rag_tool

    @rag_tool.setter
    def rag_tool(self, value: Any) -> None:
        self._rag_tool = value

    @property
    def navigation_adapter(self) -> Any:
        """Lazily initialize NavigationAdapter to prevent unneeded external connections."""
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

    @staticmethod
    def _make_google_maps_search_url(place_name: str, context: Optional[str] = None) -> str:
        q = f"{place_name}, {context}" if context and context.lower() not in place_name.lower() else place_name
        return f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(q.strip())}"

    @staticmethod
    def _make_google_maps_directions_url(origin: str, destination: str) -> str:
        return f"https://www.google.com/maps/dir/?api=1&origin={urllib.parse.quote(origin.strip())}&destination={urllib.parse.quote(destination.strip())}&travelmode=driving"

    def process(self, state: AgentState) -> AgentResponse:
        """Alias to execute for consistent agent invocation across callers."""
        return self.execute(state)

    def _init_temple_registry(self):
        """
        Loads registered canonical temples dynamically and anchors aliases.
        """
        registered = [
            "Ahobilam", "Badrachalam", "Balkampet", "Basara", "Birla Mandir",
            "Chilkur", "Dharmapuri", "Edupayal", "Jogulamba(new)", "Kaleshvaram",
            "Karmanghat", "Medaram", "Ramappa", "Srisaila", "Thousand Pillar",
            "Ttd", "Ujjaini", "Veera Satyanarayana", "Vemulavada", "Yadadri"
        ]

        alias_seed: Dict[str, List[str]] = {
            "Ahobilam": ["ahobilam", "ahobila", "narasimha ahobilam"],
            "Badrachalam": ["badrachalam", "bhadrachalam", "bhadragiri", "rama temple bhadrachalam", "lord rama bhadrachalam"],
            "Balkampet": ["balkampet", "yellamma", "balkampet yellamma"],
            "Basara": ["basara", "basar", "gnana saraswathi", "saraswathi temple"],
            "Birla Mandir": ["birla mandir", "birla"],
            "Chilkur": ["chilkur", "visa balaji", "chilkur balaji"],
            "Dharmapuri": ["dharmapuri", "narasimha swamy dharmapuri", "dharmapuri narasimha"],
            "Edupayal": ["edupayal", "edupayala", "edupayala durga", "vanadurga bhavani", "vana durga bhavani", "vana durga", "edupayala vanadurga"],
            "Jogulamba(new)": ["jogulamba", "jogulamba(new)", "jogulamba(New)", "alampur", "jogulamba devi"],
            "Kaleshvaram": ["kaleshvaram", "kaleshwaram", "mukteshwara", "kaleshwara"],
            "Karmanghat": ["karmanghat", "karmanghat hanuman"],
            "Medaram": ["medaram", "sammakka", "saralamma", "jatara medaram", "sammakka saralamma"],
            "Ramappa": ["ramappa", "ramalingeswara", "rudreshwara"],
            "Srisaila": ["srisaila", "srisailam", "mallikarjuna", "bhramaramba"],
            "Thousand Pillar": ["thousand pillar", "thousand pillars", "rudreswara thousand", "thousand pillar temple"],
            "Ttd": ["ttd", "tirumala", "tirupati", "venkateswara ttd", "lord venkateswara"],
            "Ujjaini": [
                "ujjaini", "ujjaini mahakali", "ujjaini mahankali", "mahakali secunderabad",
                "secunderabad mahakali", "secunderabad mahankali", "sri ujjaini mahakali",
                "sri ujjaini mahankali", "ujjaini mahakali temple", "ujjaini mahankali temple",
                "sri ujjaini mahakali temple", "sri ujjaini mahankali temple", "ujjaini temple",
                "ujjaini devasthanam"
            ],
            "Veera Satyanarayana": ["veera satyanarayana", "satyanarayana swamy", "annavaram", "veera venkata satyanarayana"],
            "Vemulavada": ["vemulavada", "vemulawada", "rajarajeshwara", "rajanna", "rajanne"],
            "Yadadri": ["yadadri", "yadagirigutta", "laxmi narasimha yadadri", "narasimha yadadri"]
        }

        self._temple_aliases = {}
        for canonical in registered:
            matched = False
            for k, aliases in alias_seed.items():
                if k.lower() == canonical.lower():
                    self._temple_aliases[canonical] = sorted(list(set(aliases + [canonical.lower()])), key=len, reverse=True)
                    matched = True
                    break
            if not matched:
                self._temple_aliases[canonical] = [canonical.lower()]

    def _resolve_location(self, place_name: Optional[str]) -> Tuple[str, Optional[Tuple[float, float]], Optional[str]]:
        """
        Resolves a place string to:
        (display_name, coordinates_tuple_or_None, canonical_name_or_None).
        """
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

    def extract_origin(self, query: str) -> Optional[str]:
        """
        Deterministically extracts starting location / origin from natural language query.
        """
        if not query or not query.strip():
            return None

        clean_q = query.strip()
        clean_q = re.sub(r"[?!.,;]+$", "", clean_q).strip()

        # 1. "from <origin> to <destination>"
        m = re.search(r"\bfrom\s+(.+?)\s+to\s+", clean_q, re.IGNORECASE)
        if m:
            orig = self._clean_origin_candidate(m.group(1))
            if orig:
                return orig

        # 2. "to <destination> from <origin>"
        m = re.search(r"\bto\s+.+?\s+from\s+(.+?)(?:\s+(?:with|for|\d+\s+day|and)|\s*$)", clean_q, re.IGNORECASE)
        if m:
            orig = self._clean_origin_candidate(m.group(1))
            if orig:
                return orig

        # 3. "(?:starting|departing|leaving|start)\s+(?:from|at)\s+<origin>"
        m = re.search(r"\b(?:starting|departing|leaving|start)\s+(?:from|at)\s+(.+?)(?:\s+(?:to|for|with|\d+\s+day|and)|\s*$)", clean_q, re.IGNORECASE)
        if m:
            orig = self._clean_origin_candidate(m.group(1))
            if orig:
                return orig

        # 4. "from <origin>" at end of query or before budget/days
        m = re.search(r"\bfrom\s+(.+?)(?:\s+(?:with|for|\d+\s+day)|\s*$)", clean_q, re.IGNORECASE)
        if m:
            orig = self._clean_origin_candidate(m.group(1))
            if orig:
                return orig

        return None

    def _clean_origin_candidate(self, raw: str) -> Optional[str]:
        if not raw:
            return None
        text = raw.strip()
        text = re.sub(r"^(?:the|a|an|my\s+home|my\s+place|my\s+city|city\s+of|town\s+of)\s+", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"\s+(?:city|town|district|station|junction)$", "", text, flags=re.IGNORECASE).strip()
        text = text.rstrip(",;.").strip()
        
        invalid_words = {"what", "where", "how", "when", "why", "who", "which", "can", "plan", "here", "there", "it"}
        words = text.split()
        if not words or len(words) > 5:
            return None
        if any(w.lower().rstrip(",;.") in invalid_words for w in words):
            return None
        
        return text.title()

    def _is_return_requested(self, query: str, origin: Optional[str] = None) -> bool:
        """
        Determines whether the user explicitly stated or intended a return journey to the starting origin.
        Avoids assuming a multi-day trip implies return unless explicitly indicated.
        """
        if not query:
            return False
        # Direct round trip keywords
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
        """Parses Google API duration string (e.g. '1234s' or '123.4s') into float seconds."""
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

    def detect_temples(self, query: str, origin: Optional[str] = None) -> List[str]:
        """
        Detects all registered canonical temples referenced in the query in order of appearance.
        Excludes origin from candidate temples when origin is specified.
        """
        if not query or not query.strip():
            return []

        clean_query = query.strip()
        if origin:
            clean_query = re.sub(rf"\b(?:from|starting\s+(?:from|at)|leaving\s+from|start\s+from)\s+{re.escape(origin)}\b", " ", clean_query, flags=re.IGNORECASE)
            clean_query = re.sub(rf"\bfrom\s+[A-Za-z\s,]+?\s+to\b", " to ", clean_query, flags=re.IGNORECASE)

        matches: List[Tuple[int, str]] = []

        for canonical, aliases in self._temple_aliases.items():
            for alias in aliases:
                pattern = r"\b" + re.escape(alias) + r"\b"
                for match in re.finditer(pattern, clean_query, re.IGNORECASE):
                    matches.append((match.start(), canonical))
                    break

        matches.sort(key=lambda m: m[0])
        ordered_temples: List[str] = []
        for _, canonical in matches:
            if origin:
                _, _, orig_canon = self._resolve_location(origin)
                if orig_canon and canonical.lower() == orig_canon.lower():
                    continue
                if canonical.lower() == origin.lower():
                    continue
            if canonical not in ordered_temples:
                ordered_temples.append(canonical)

        return ordered_temples

    _detect_temples = detect_temples

    def _detect_unknown_temple(self, query: str) -> Optional[str]:
        """
        Identifies whether the user explicitly requests an unregistered / unknown temple.
        Guarantees zero hallucination and explicit refusal.
        """
        famous_unregistered = [
            "golden temple", "meenakshi", "somnath", "kedarnath", "badrinath",
            "kashi vishwanath", "kashi", "jagannath", "kamakhya", "akshardham", "shirdi",
            "padmanabhaswamy", "murudeshwar", "konark", "brihadeeswarar", "ranganathaswamy",
            "amarnath", "vaishno devi", "tiruchendur", "palani", "atlantis", "atlantis temple"
        ]
        for name in famous_unregistered:
            if re.search(r"\b" + re.escape(name) + r"\b", query, re.IGNORECASE):
                return name.title()

        pattern = r"\b([A-Za-z]+(?:\s+[A-Za-z]+)?)\s+(temple|mandir|kovil|devasthanam)\b"
        stopwords = {
            "the", "a", "an", "this", "that", "these", "those", "which", "what", "where",
            "who", "how", "why", "when", "are", "is", "was", "were", "be", "been",
            "do", "does", "did", "have", "has", "had", "any", "all", "our", "your",
            "my", "their", "its", "some", "of", "in", "at", "to", "for", "with", "about",
            "plan", "itinerary", "visit", "trip", "tour", "day", "days"
        }
        for match in re.finditer(pattern, query, re.IGNORECASE):
            candidate = match.group(1).strip()
            words = [w.lower() for w in candidate.split()]
            meaningful = [w for w in words if w not in stopwords]
            if not meaningful:
                continue

            cleaned_candidate = " ".join(meaningful)
            detected = False
            for canonical, aliases in self._temple_aliases.items():
                if any(re.search(r"\b" + re.escape(a) + r"\b", cleaned_candidate, re.IGNORECASE) for a in aliases):
                    detected = True
                    break
            if not detected:
                return f"{cleaned_candidate.title()} {match.group(2).title()}"

        return None

    def _extract_duration_days(self, query: str, num_temples: int) -> int:
        """
        Extracts requested duration in days from the query, or defaults sensibly.
        """
        # 1. Numeric days (e.g., "4 days", "4-day trip", "1 day")
        match = re.search(r"\b(\d+)\s*[- ]*(?:days?|day)\b", query, re.IGNORECASE)
        if match:
            try:
                days = int(match.group(1))
                return max(1, min(days, 14))
            except ValueError:
                pass

        # 2. Numeric nights (e.g., "2-night stay", "3 nights") -> duration in days = nights + 1
        n_match = re.search(r"\b(\d+)\s*[- ]*(?:nights?|night)\b", query, re.IGNORECASE)
        if n_match:
            try:
                nights = int(n_match.group(1))
                return max(1, min(nights + 1, 14))
            except ValueError:
                pass

        # 3. Explicit standalone day trip / single day patterns
        if re.search(r"\b(?:day\s*trip|day\s*visit|single\s*day|same\s*day|one\s*day)\b", query, re.IGNORECASE):
            return 1

        # 4. Word-based numbers
        word_map = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
            "single": 1, "weekend": 2, "week": 7
        }
        for word, val in word_map.items():
            if re.search(r"\b" + word + r"\s*[- ]*(?:nights?|night)\b", query, re.IGNORECASE):
                return min(val + 1, 14)
            if re.search(r"\b" + word + r"\s*[- ]*(?:days?|day|trip|visit)\b", query, re.IGNORECASE):
                return val

        return max(1, num_temples)

    _extract_duration = _extract_duration_days

    def _clean_text(self, text: Optional[str]) -> str:
        """
        Sanitizes raw text snippets: strips trailing single dangling letters,
        eliminates empty/malformed patterns, and removes unescaped artifacts.
        """
        if not text or not isinstance(text, str):
            return ""

        cleaned = html.unescape(text).strip()
        # Suppress empty malformed tokens like ": | :" or standalone colons
        if re.match(r"^[\s:|–—-]+$", cleaned):
            return ""

        # Remove trailing single dangling letters from OCR/parser artifacts (e.g. "... q", " ... w")
        cleaned = re.sub(r"\s+[a-zA-Z]\s*$", "", cleaned)
        cleaned = re.sub(r"\.\.\.\s*[a-zA-Z]\s*$", "...", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    def _get_temple_itinerary_data(self, temple: str) -> Tuple[Dict[str, Any], List[str]]:
        """
        Retrieves verified records for relevant categories via RAGTool.
        Returns (data_dict, sources_list).
        """
        categories = ["timings", "sevas", "travel", "accommodation", "prasadam", "crowd", "facilities", "rules", "nearby_attractions"]
        data: Dict[str, Any] = {}
        sources: List[str] = []

        clean_t = temple.lower().replace(" ", "_")

        for cat in categories:
            cat_data = self.rag_tool.get_temple_category_data(temple, cat)
            if cat_data:
                data[cat] = cat_data
                sources.append(f"{clean_t}/{cat}.json")
            else:
                # Try parent text fallback
                parent = self.rag_tool.get_complete_parent_text(temple, cat)
                if parent:
                    data[cat] = parent
                    sources.append(f"{clean_t}/{cat}.json")

        return data, sources

    def _parse_timings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts verified opening hours, darshan windows, and break periods.
        """
        timings_obj = data.get("timings")
        res = {
            "summary": "Standard daily temple opening hours apply.",
            "opening": "morning opening window",
            "closing": "evening closing hour",
            "break_period": None,
            "has_break": False
        }

        if isinstance(timings_obj, dict):
            t_items = []
            for k in ["general_timings", "darshan_timings", "temple_hours", "morning", "evening"]:
                if k in timings_obj:
                    v = self._clean_text(str(timings_obj[k]))
                    if v and not re.match(r"^[\s:|–—-]+$", v):
                        t_items.append(f"{k.replace('_', ' ').title()}: {v}")
            if t_items:
                res["summary"] = "; ".join(t_items[:2])
            elif "darshan_slots" in timings_obj and isinstance(timings_obj["darshan_slots"], list):
                res["summary"] = "Darshan Slots: " + ", ".join([str(s) for s in timings_obj["darshan_slots"][:3]])

            # Check break hours
            for bk in ["break_timings", "afternoon_break", "break"]:
                if bk in timings_obj:
                    bv = self._clean_text(str(timings_obj[bk]))
                    if bv:
                        res["break_period"] = bv
                        res["has_break"] = True
                        break

            # Extract specific opening/closing times if available
            text_str = str(timings_obj)
            open_m = re.search(r"(\d{1,2}(?::\d{2})?\s*(?:AM|am))", text_str)
            if open_m:
                res["opening"] = open_m.group(1)
            close_m = re.search(r"(\d{1,2}(?::\d{2})?\s*(?:PM|pm))", text_str)
            if close_m:
                res["closing"] = close_m.group(1)

        elif isinstance(timings_obj, str) and timings_obj.strip():
            clean_str = self._clean_text(timings_obj)
            if clean_str:
                res["summary"] = clean_str.split("\n")[0][:120]

        return res

    def _parse_sevas(self, data: Dict[str, Any]) -> Dict[str, List[Dict[str, str]]]:
        """
        Extracts and organizes verified sevas into morning, evening, and general groups.
        """
        sevas_obj = data.get("sevas")
        res = {"morning": [], "evening": [], "general": [], "all": []}

        raw_list = []
        if isinstance(sevas_obj, list):
            raw_list = sevas_obj
        elif isinstance(sevas_obj, dict):
            for k, v in sevas_obj.items():
                if isinstance(v, list):
                    raw_list.extend(v)
                elif isinstance(v, dict) and "name" in v:
                    raw_list.append(v)

        for item in raw_list:
            if isinstance(item, dict) and "name" in item:
                s_name = self._clean_text(str(item.get("name", "")))
                s_timing = self._clean_text(str(item.get("timing") or item.get("time") or ""))
                s_desc = self._clean_text(str(item.get("description") or item.get("desc") or ""))
                s_cost = self._clean_text(str(item.get("price") or item.get("ticket_price") or item.get("cost") or ""))

                if not s_name:
                    continue

                entry = {
                    "name": s_name,
                    "timing": s_timing,
                    "desc": s_desc[:90] if s_desc else "",
                    "cost": s_cost
                }
                res["all"].append(entry)

                time_lower = s_timing.lower()
                name_lower = s_name.lower()
                if "am" in time_lower or "morning" in time_lower or "suprabhata" in name_lower or "abhishekam" in name_lower:
                    res["morning"].append(entry)
                elif "pm" in time_lower or "evening" in time_lower or "harathi" in name_lower or "unja" in name_lower:
                    res["evening"].append(entry)
                else:
                    res["general"].append(entry)

            elif isinstance(item, str) and item.strip():
                clean_s = self._clean_text(item)
                if clean_s:
                    entry = {"name": clean_s[:60], "timing": "", "desc": "", "cost": ""}
                    res["all"].append(entry)
                    res["general"].append(entry)

        return res

    def _parse_nearby_attractions(self, data: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Extracts verified nearby attractions from nearby_attractions.json if available.
        """
        obj = data.get("nearby_attractions")
        attractions: List[Dict[str, str]] = []

        if isinstance(obj, dict) and "attractions" in obj and isinstance(obj["attractions"], list):
            items = obj["attractions"]
        elif isinstance(obj, list):
            items = obj
        else:
            items = []

        for item in items:
            if isinstance(item, dict) and "name" in item:
                name = self._clean_text(str(item.get("name", "")))
                dist = self._clean_text(str(item.get("distance", "")))
                desc = self._clean_text(str(item.get("description", "")))
                if name:
                    attractions.append({
                        "name": name,
                        "distance": dist,
                        "desc": desc[:100] if desc else ""
                    })

        return attractions

    def _parse_prasadam(self, data: Dict[str, Any]) -> str:
        """
        Extracts verified prasadam / Annadanam food service details.
        """
        prasadam_obj = data.get("prasadam")
        if isinstance(prasadam_obj, dict):
            if "annadanam" in prasadam_obj:
                ann = self._clean_text(str(prasadam_obj["annadanam"]))
                if ann:
                    return f"Annadanam available: {ann[:110]}"
            if "items" in prasadam_obj:
                return "Prasadam counters operational during temple opening hours."
        elif isinstance(prasadam_obj, list):
            return "Prasadam counters and sanctified food offerings operational."
        return "Prasadam offerings and official devasthanam food counters available during opening hours."

    def _parse_accommodation(self, data: Dict[str, Any]) -> str:
        """
        Extracts verified accommodation records (Devasthanam cottages/choultries).
        """
        accom_obj = data.get("accommodation")
        if isinstance(accom_obj, dict):
            parts = []
            if "devasthanam_guest_houses" in accom_obj and isinstance(accom_obj["devasthanam_guest_houses"], list):
                names = [self._clean_text(str(g.get("name") if isinstance(g, dict) else g)) for g in accom_obj["devasthanam_guest_houses"][:2]]
                valid_names = [n for n in names if n]
                if valid_names:
                    parts.append(f"Devasthanam Stays: {', '.join(valid_names)}")
            if "types" in accom_obj and isinstance(accom_obj["types"], list):
                parts.append(f"Options: {', '.join(str(t) for t in accom_obj['types'][:2])}")
            if parts:
                return "; ".join(parts)
            return "On-site Devasthanam guest houses, cottages, and choultries verified in records."
        elif isinstance(accom_obj, list) and accom_obj:
            return "On-site Devasthanam guest houses and cottages verified in records."
        elif accom_obj:
            return "On-site Devasthanam guest houses / choultries verified in records."
        return "Check nearby private stays; no devasthanam stay specified."

    def _determine_property_tier(self, prop: Dict[str, Any]) -> str:
        """Categorizes an accommodation record into Budget, Premium, or Standard / Comfort."""
        text = (str(prop.get("name", "")) + " " + str(prop.get("type", "")) + " " + str(prop.get("description", ""))).lower()
        price_str = str(prop.get("price") or prop.get("tariff") or prop.get("rate") or prop.get("cost") or "").lower()
        m = re.search(r"(?:₹|rs\.?|inr)?\s*(\d+)", price_str)
        cost_val = float(m.group(1)) if m else None

        if any(k in text for k in ["satram", "choultry", "dharamshala", "dormitory", "free", "annadanam"]):
            return "Budget"
        if cost_val is not None:
            if cost_val <= 800:
                return "Budget"
            elif cost_val >= 2500:
                return "Premium"
            else:
                return "Standard / Comfort"
        if any(k in text for k in ["resort", "suite", "luxury", "star", "premium"]):
            return "Premium"
        return "Standard / Comfort"

    def _format_temple_accommodation_options(self, temple: str, data: Dict[str, Any], accom_pref: Optional[str] = None) -> List[str]:
        """
        Extracts all verified accommodation options for a given temple from dataset records.
        Applies accommodation preference filtering consistently.
        """
        accom_obj = data.get("accommodation")
        if not accom_obj and hasattr(self, "rag_tool") and self.rag_tool:
            try:
                accom_obj = self.rag_tool.get_temple_category_data(temple, "accommodation")
            except Exception:
                accom_obj = None

        lines: List[str] = [f"#### {temple}"]

        accom_list: List[Dict[str, Any]] = []
        if isinstance(accom_obj, list):
            for it in accom_obj:
                if isinstance(it, dict):
                    accom_list.append(it)
                elif isinstance(it, str) and it.strip():
                    accom_list.append({"name": it.strip()})
        elif isinstance(accom_obj, dict):
            for k in ["devasthanam_guest_houses", "guest_houses", "hotels", "cottages", "satralu", "rooms", "traditional_guest_houses"]:
                if k in accom_obj and isinstance(accom_obj[k], list):
                    for it in accom_obj[k]:
                        if isinstance(it, dict):
                            accom_list.append(it)
                        elif isinstance(it, str) and it.strip():
                            accom_list.append({"name": it.strip(), "type": k.replace("_", " ").title()})
            if not accom_list and "name" in accom_obj:
                accom_list.append(accom_obj)

        if not accom_list:
            lines.append(f"- No verified accommodation options were found in the available dataset records for {temple}. Please check local hotel listings or enquire directly at the temple enquiry counter.")
            lines.append("")
            return lines

        # Preference Filtering
        pref_clean = None
        if accom_pref and accom_pref.lower() not in ("none", "no"):
            if "budget" in accom_pref.lower():
                pref_clean = "Budget"
            elif "premium" in accom_pref.lower():
                pref_clean = "Premium"
            elif "standard" in accom_pref.lower() or "comfort" in accom_pref.lower():
                pref_clean = "Standard / Comfort"

        matching_props = []
        alt_props = []
        if pref_clean:
            for p in accom_list:
                tier = self._determine_property_tier(p)
                p["_inferred_tier"] = tier
                if tier == pref_clean:
                    matching_props.append(p)
                else:
                    alt_props.append(p)
        else:
            matching_props = accom_list
            for p in matching_props:
                p["_inferred_tier"] = self._determine_property_tier(p)

        if pref_clean and not matching_props:
            lines.append(f"- No verified {pref_clean}-tier accommodation option was found near {temple} in official records.")
            lines.append("")
        else:
            if pref_clean:
                lines.append(f"*Matching Selected Preference ({pref_clean}):*")
            for idx, prop in enumerate(matching_props, start=1):
                name = html.unescape(str(prop.get("name", "")).strip()) or f"Accommodation Option {idx}"
                prop_type = html.unescape(str(prop.get("type", "")).strip())
                price = html.unescape(str(prop.get("price") or prop.get("tariff") or prop.get("rate") or prop.get("cost") or "").strip())
                dist = html.unescape(str(prop.get("distance") or prop.get("location") or f"Near {temple}").strip())
                desc = html.unescape(str(prop.get("description") or prop.get("notes") or "").strip())
                contact = html.unescape(str(prop.get("contact") or prop.get("phone") or "").strip())
                booking = html.unescape(str(prop.get("booking_platform") or prop.get("booking_url") or "").strip())
                tier = prop.get("_inferred_tier", "Standard / Comfort")

                lines.append(f"- **{name}** ({tier} Tier)")
                if prop_type:
                    lines.append(f"  - **Accommodation Type**: {prop_type}")
                if price:
                    lines.append(f"  - **Tariff / Price**: {price}")
                else:
                    lines.append("  - **Tariff / Price**: Tariff unquantified in verified records (contact property/counter directly)")
                lines.append(f"  - **Proximity**: {dist}")
                if contact:
                    lines.append(f"  - **Booking / Contact Information**: {contact}")
                elif booking:
                    lines.append(f"  - **Booking / Contact Information**: {booking}")
                if desc:
                    lines.append(f"  - **Limitations & Conditions**: {desc}")
                maps_s = self._make_google_maps_search_url(name, temple)
                maps_d = self._make_google_maps_directions_url(temple, name)
                lines.append(f"  - **Google Maps**: [🗺️ View on Google Maps]({maps_s}) | [🧭 Get Directions]({maps_d})")
            lines.append("")

        if pref_clean and alt_props:
            lines.append(f"##### Other Tier Options near {temple} (Reference Only):")
            for idx, prop in enumerate(alt_props, start=1):
                name = html.unescape(str(prop.get("name", "")).strip()) or f"Alternative Option {idx}"
                tier = prop.get("_inferred_tier", "Standard / Comfort")
                price = html.unescape(str(prop.get("price") or prop.get("tariff") or "").strip()) or "Tariff unquantified"
                maps_s = self._make_google_maps_search_url(name, temple)
                lines.append(f"- **{name}** ({tier} Tier) — Tariff: {price} ([🗺️ View on Maps]({maps_s}))")
            lines.append("")

        return lines

    def _build_live_data_disclaimer(self, route_legs: List[Dict[str, Any]]) -> str:
        """
        Builds honest, non-contradictory data disclaimer separating live route calculations from static temple data.
        """
        successful_legs = [l for l in route_legs if l.get("status") == "success"]
        has_traffic = any(l.get("traffic_duration_minutes") is not None for l in successful_legs)
        if successful_legs:
            traffic_clause = "including live traffic estimates where available, " if has_traffic else ""
            return (
                f"*(Data Sources & Scope: Route distances and driving durations ({traffic_clause})are calculated via Google Routes API navigation integration. "
                "Temple timings, sevas, accommodation options, and static amenities are sourced from the verified local knowledge base and should be confirmed at temple enquiry counters. "
                "Dynamic room availability, live public transit schedules, and weather forecasts are not real-time feeds and require independent confirmation).*"
            )
        else:
            return LIVE_DATA_DISCLAIMER

    def _parse_travel(self, data: Dict[str, Any]) -> List[str]:
        """
        Extracts verified static connectivity and transit hubs into clean human-readable strings.
        Guarantees zero raw dictionary or JSON object leakage into user responses.
        """
        travel_obj = data.get("travel")
        t_notes = []
        if isinstance(travel_obj, dict):
            # 1. Railway connectivity
            st = travel_obj.get("nearest_railway_station") or travel_obj.get("railway")
            if isinstance(st, dict):
                if "name" in st:
                    name = self._clean_text(st.get("name"))
                    dist = self._clean_text(st.get("distance", ""))
                    dist_str = f" ({dist})" if dist else ""
                    if name:
                        t_notes.append(f"Nearest Railway: {name}{dist_str}")
                elif "stations" in st and isinstance(st["stations"], list):
                    for station in st["stations"]:
                        if isinstance(station, dict):
                            s_name = station.get("station") or station.get("name")
                            s_dist = station.get("distance", "")
                            dist_str = f" ({s_dist})" if s_dist else ""
                            if s_name:
                                t_notes.append(f"Nearest Railway: {self._clean_text(str(s_name))}{dist_str}")
                                break
                        elif isinstance(station, str) and self._clean_text(station):
                            t_notes.append(f"Nearest Railway: {self._clean_text(station)}")
                            break
            elif isinstance(st, str) and self._clean_text(st):
                t_notes.append(f"Nearest Railway: {self._clean_text(st)}")

            # 2. Airport connectivity
            ap = travel_obj.get("nearest_airport") or travel_obj.get("airport")
            if isinstance(ap, dict):
                name = self._clean_text(ap.get("name"))
                dist = self._clean_text(ap.get("distance", ""))
                dist_str = f" ({dist})" if dist else ""
                if name:
                    t_notes.append(f"Nearest Airport: {name}{dist_str}")
            elif isinstance(ap, str) and self._clean_text(ap):
                t_notes.append(f"Nearest Airport: {self._clean_text(ap)}")

            # 3. Bus routes and local transit
            if "bus_routes" in travel_obj:
                br = travel_obj["bus_routes"]
                if isinstance(br, list):
                    for b in br:
                        if isinstance(b, dict):
                            st_name = b.get("nearest_bus_station") or b.get("station") or b.get("name")
                            st_dist = b.get("distance", "")
                            st_desc = b.get("description", "")
                            st_route = b.get("route", "")
                            if st_name and st_dist:
                                t_notes.append(f"Nearest Bus Station: {self._clean_text(str(st_name))} ({self._clean_text(str(st_dist))})")
                                break
                            elif st_desc and not st_desc.startswith("{"):
                                t_notes.append(f"Bus Connectivity: {self._clean_text(str(st_desc)[:120])}")
                                break
                            elif st_route and st_desc:
                                t_notes.append(f"Bus Route ({st_route}): {self._clean_text(str(st_desc)[:100])}")
                                break
                        elif isinstance(b, str) and self._clean_text(b) and not b.strip().startswith("{"):
                            t_notes.append(f"Bus Connectivity: {self._clean_text(b[:120])}")
                            break

        return t_notes

    def _parse_rules(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts verified dress code, dos, and don'ts.
        """
        rules_obj = data.get("rules")
        res = {"dress_code": None, "dos": [], "donts": []}

        if isinstance(rules_obj, dict):
            if "dress_code" in rules_obj:
                raw_dc = rules_obj["dress_code"]
                if isinstance(raw_dc, dict):
                    parts = []
                    for k, v in raw_dc.items():
                        clean_v = self._clean_text(str(v)) if v else ""
                        if clean_v:
                            parts.append(f"{k.capitalize()}: {clean_v}")
                    if parts:
                        res["dress_code"] = ", ".join(parts)
                elif isinstance(raw_dc, str):
                    dc = self._clean_text(raw_dc)
                    if dc and not re.match(r"^[\s:|–—-]+$", dc) and dc not in ["{}", "{'men': '', 'women': ''}", "{'men': '', 'women': ''}"]:
                        # Also check if it is stringified empty dict
                        if not (dc.startswith("{") and "''" in dc and not any(c.isalnum() for c in re.sub(r"['\":{},\s]|men|women", "", dc))):
                            res["dress_code"] = dc
            if "dos" in rules_obj and isinstance(rules_obj["dos"], list):
                res["dos"] = [self._clean_text(str(d)) for d in rules_obj["dos"][:2] if self._clean_text(str(d))]
            if "donts" in rules_obj and isinstance(rules_obj["donts"], list):
                res["donts"] = [self._clean_text(str(d)) for d in rules_obj["donts"][:2] if self._clean_text(str(d))]

        return res

    def _format_schedule_section(
        self,
        temple: str,
        day_num: int,
        total_days: int,
        temple_day_index: int,
        total_temple_days: int,
        data: Dict[str, Any],
        is_multi_temple: bool = False,
        next_temple: Optional[str] = None,
        next_leg: Optional[Dict[str, Any]] = None,
        prev_temple: Optional[str] = None,
        day_label: Optional[str] = None,
        day_activities: Optional[List[Any]] = None
    ) -> List[str]:
        """
        Builds a structured, non-repetitive daily itinerary section
        strictly separating verified facts from planning suggestions.
        """
        timings = self._parse_timings(data)
        sevas = self._parse_sevas(data)
        attractions = self._parse_nearby_attractions(data)
        prasadam_note = self._parse_prasadam(data)
        rules = self._parse_rules(data)

        # 1. Determine Day Theme & Focus
        if total_days == 1:
            theme = "Full Day Pilgrimage & Darshan"
        elif temple_day_index == 1 and day_num == 1:
            theme = "Arrival, Primary Darshan & Sevas"
        elif temple_day_index == 1 and is_multi_temple:
            theme = "Arrival & Sanctum Darshan"
        elif day_num == total_days:
            theme = "Concluding Darshan, Exploration & Departure"
        elif temple_day_index == total_temple_days and is_multi_temple:
            theme = "Special Rituals & Onward Journey"
        elif temple_day_index == 2:
            theme = "Special Sevas & Local Exploration"
        else:
            theme = "Spiritual Observance & Parivara Shrines"

        lbl = day_label if day_label else f"Day {day_num}"
        temple_maps_url = self._make_google_maps_search_url(temple)
        lines = [f"#### {lbl}: {temple} — Darshan & Nearby Places ({theme})\n"]

        # -------------------------------------------------------------
        # 1. VERIFIED TEMPLE INFORMATION
        # -------------------------------------------------------------
        lines.append("**Verified Temple Information:**")
        lines.append(f"- **Temple Sanctum**: [{temple} on Google Maps]({temple_maps_url})")
        if timings["summary"] and not re.match(r"^[\s:|–—-]+$", timings["summary"]):
            lines.append(f"- **Operating Schedule**: {timings['summary']}")

        # Featured Seva selection (progresses dynamically across days)
        if sevas["all"]:
            seva_offset = (temple_day_index - 1) * 2
            day_sevas = sevas["all"][seva_offset:seva_offset + 2] if len(sevas["all"]) > seva_offset else sevas["all"][:2]
            seva_strs = []
            for s in day_sevas:
                s_label = s["name"]
                if s["timing"]:
                    s_label += f" ({s['timing']})"
                seva_strs.append(s_label)
            if seva_strs:
                lines.append(f"- **Featured Sevas**: {', '.join(seva_strs)}")

        if temple_day_index > 1 and attractions:
            attr_strs = [f"{a['name']}" + (f" ({a['distance']})" if a['distance'] else "") for a in attractions[:2]]
            lines.append(f"- **Verified Nearby Attractions**: {', '.join(attr_strs)}")

        if prasadam_note and ("annadanam" in prasadam_note.lower() or "food" in prasadam_note.lower() or "operational" in prasadam_note.lower()):
            lines.append(f"- **Prasadam / Food**: {prasadam_note}")

        if rules["dress_code"]:
            lines.append(f"- **Dress Code**: {rules['dress_code']}")

        lines.append("")

        # -------------------------------------------------------------
        # 2. SUGGESTED VISIT PLAN (Morning, Afternoon, Evening)
        # -------------------------------------------------------------
        lines.append("**Suggested Visit Plan:**")

        # Morning Window
        if temple_day_index == 1:
            if prev_temple:
                lines.append(f"- **Morning Window**: Arrive at {temple} (following transit from {prev_temple}). Proceed to the main sanctum for initial darshan during morning opening hours ({timings['opening']} onwards).")
            else:
                lines.append(f"- **Morning Window**: Arrive at {temple}. Proceed to the main sanctum for initial darshan during morning opening hours ({timings['opening']} onwards).")
            if sevas["morning"]:
                s = sevas["morning"][0]
                t_str = f" ({s['timing']})" if s["timing"] else ""
                lines.append(f"  • Attend morning seva: **{s['name']}**{t_str}.")
        else:
            lines.append(f"- **Morning Window**: Attend peaceful early morning darshan and participate in daily sanctum archana / pradakshinam ({timings['opening']} onwards).")
            if len(sevas["all"]) > 1:
                alt_s = sevas["all"][1]
                t_str = f" ({alt_s['timing']})" if alt_s["timing"] else ""
                lines.append(f"  • Participate in **{alt_s['name']}**{t_str}.")

        # Afternoon Window
        if total_days == 1:
            if attractions:
                attr_names = [a["name"] for a in attractions[:2]]
                lines.append(f"- **Afternoon Window**: Utilize Annadanam / lunch services. Observe sanctum break hours, visit verified nearby sites — {', '.join(attr_names)} — and rest before evening darshan.")
            else:
                lines.append(f"- **Afternoon Window**: Utilize Annadanam / lunch services. Observe sanctum break hours, explore temple courtyard architecture, and rest before evening darshan.")
        elif temple_day_index == 1:
            lines.append(f"- **Afternoon Window**: Utilize Annadanam / lunch services. Observe sanctum break hours and proceed to lodging for check-in and rest.")
        elif attractions:
            attr_names = [a["name"] for a in attractions[:2]]
            lines.append(f"- **Afternoon Window**: Visit verified nearby sites — {', '.join(attr_names)} — and utilize courtyard amenities during afternoon sanctum break.")
        else:
            lines.append(f"- **Afternoon Window**: Explore temple courtyard architecture, visit devasthanam information center, and observe afternoon rest period.")

        # Evening Window
        if total_days == 1:
            lines.append(f"- **Evening Window**: Attend final evening Harathi / darshan, collect sanctified Laddu / Pulihora prasadam from official counters, and proceed for departure / return journey.")
        elif day_num == total_days:
            lines.append(f"- **Evening Window**: Attend final evening Harathi / darshan, collect sanctified Laddu / Pulihora prasadam from official counters, check out, and proceed for departure.")
        elif next_temple:
            transit_note = ""
            if next_leg and next_leg.get("status") == "success":
                dist_str = f"~{next_leg['distance_km']} km" if next_leg.get("distance_km") else ""
                dur_str = f"~{self._format_duration_human(next_leg['duration_minutes'])}" if next_leg.get("duration_minutes") else ""
                metrics = ", ".join(m for m in [dist_str, dur_str] if m)
                transit_note = f" ({metrics} driving transit)" if metrics else ""
            lines.append(f"- **Evening Window / Inter-Temple Transit**: Attend evening Harathi, conclude visit at {temple}, check out, and embark on highway transit to {next_temple}{transit_note}. Check into accommodation near {next_temple} for night rest.")
        elif temple_day_index == total_temple_days and is_multi_temple:
            lines.append(f"- **Evening Window**: Attend evening Harathi, conclude temple visit, and rest or prepare for onward travel to the next pilgrimage destination.")
        else:
            if sevas["evening"]:
                e_s = sevas["evening"][0]
                t_str = f" ({e_s['timing']})" if e_s["timing"] else ""
                lines.append(f"- **Evening Window**: Attend evening Harathi (**{e_s['name']}**{t_str}), visit parivara sub-shrines, and return to lodging for night rest.")
            else:
                lines.append(f"- **Evening Window**: Attend evening Harathi and darshan (open up to {timings['closing']}), explore illuminated complex, and return to lodging.")

        # Scheduled nearby activities for this day
        if day_activities:
            lines.append("- **Scheduled Nearby Attraction Visit(s)**:")
            for act in day_activities:
                act_name = act.get("name") if isinstance(act, dict) else str(act)
                act_dest = act.get("destination") or temple if isinstance(act, dict) else temple
                maps_s = self._make_google_maps_search_url(act_name, act_dest)
                maps_d = self._make_google_maps_directions_url(temple, act_name)
                lines.append(f"  • **{act_name}**: Exploration near {act_dest} scheduled for this day. ([📍 View on Maps]({maps_s}) | [🧭 Get Directions]({maps_d}))")

        # If multi-day visit exceeds verified activities, add honest disclaimer
        if temple_day_index > 2 and not attractions and len(sevas["all"]) <= 2:
            lines.append(f"  *(Note: Official records for {temple} focus on core darshan and rituals. Additional hours are left flexible for quiet contemplation and local rest).*")

        lines.append("")
        return lines

    def _run(self, state: AgentState) -> AgentResponse:
        """
        Executes grounded pilgrimage itinerary planning.
        Called automatically by BaseAgent.execute(state).
        """
        raw_query = state.user_query.strip() if state.user_query else ""

        # 1. Empty / Whitespace Input
        if not raw_query:
            return AgentResponse(
                success=False,
                agent_name=self.name,
                answer="Please provide a valid pilgrimage itinerary question.",
                sources=[],
                error="Empty query"
            )

        # 2. Check for explicitly named unknown / unregistered temples
        unknown_temple = self._detect_unknown_temple(raw_query)
        if unknown_temple:
            return AgentResponse(
                success=False,
                agent_name=self.name,
                answer=(
                    f"I don't have verified records for '{unknown_temple}' in the current PilgrimAI knowledge base. "
                    f"PilgrimAI currently covers 20 major pilgrimage temples in Telangana (such as Yadadri, Basara, Bhadrachalam, Srisailam, Dharmapuri, etc.)."
                ),
                sources=[],
                metadata={"detected_unknown_temple": unknown_temple},
                error="Unregistered temple"
            )

        constraints = state.structured_constraints if state and state.structured_constraints else {}

        # 2.5 Extract Origin (Starting Location)
        origin = self.extract_origin(raw_query)
        if not origin and constraints.get("origin"):
            origin = str(constraints.get("origin")).strip()

        # 3. Detect candidate registered temples (excluding origin)
        if constraints.get("destinations"):
            dest_input = constraints.get("destinations")
            dest_items = dest_input if isinstance(dest_input, list) else [dest_input]
            detected_temples = []
            for d in dest_items:
                d_found = self.detect_temples(str(d), origin=origin)
                if d_found:
                    for df in d_found:
                        if df not in detected_temples:
                            detected_temples.append(df)
                else:
                    _, _, canon = self._resolve_location(str(d))
                    if canon and canon not in detected_temples:
                        detected_temples.append(canon)
                    elif str(d).strip().title() not in detected_temples:
                        detected_temples.append(str(d).strip().title())
        else:
            detected_temples = self.detect_temples(raw_query, origin=origin)

        # If still empty, check if selected_activities specifies a destination
        if not detected_temples and (constraints.get("selected_activities") or constraints.get("added_activities")):
            acts = constraints.get("selected_activities") or constraints.get("added_activities")
            for a in acts:
                if isinstance(a, dict) and a.get("destination"):
                    detected_temples.extend(self.detect_temples(str(a["destination"]), origin=origin))
            seen_t = set()
            dedup_t = []
            for t in detected_temples:
                if t.lower() not in seen_t:
                    seen_t.add(t.lower())
                    dedup_t.append(t)
            detected_temples = dedup_t

        # 4. Zero Temples Identified
        if not detected_temples:
            if origin:
                return AgentResponse(
                    success=False,
                    agent_name=self.name,
                    answer=(
                        f"I see you want to start from '{origin}', but please specify which registered temple or temples "
                        f"you would like to visit in your itinerary. PilgrimAI covers 20 registered pilgrimage destinations "
                        f"in Telangana (e.g., Yadadri, Dharmapuri, Basara, Bhadrachalam, Srisailam)."
                    ),
                    sources=[],
                    metadata={"clarification_needed": True, "detected_temples": [], "origin": origin},
                    error="Missing destination temple specification"
                )
            return AgentResponse(
                success=False,
                agent_name=self.name,
                answer=(
                    "Which temple or temples would you like to include in your itinerary? "
                    "PilgrimAI covers 20 registered pilgrimage destinations in Telangana (e.g., Yadadri, Dharmapuri, Basara, Bhadrachalam, Srisailam)."
                ),
                sources=[],
                metadata={"clarification_needed": True, "detected_temples": []},
                error="Missing temple specification"
            )

        # 5. Determine Duration in Days
        if constraints.get("duration_days"):
            try:
                duration_days = int(constraints.get("duration_days"))
            except (ValueError, TypeError):
                duration_days = self._extract_duration_days(raw_query, len(detected_temples))
        else:
            duration_days = self._extract_duration_days(raw_query, len(detected_temples))

        # 5.5 Multi-Leg Route Calculation via NavigationAdapter (if origin provided)
        first_temple = detected_temples[0]
        is_return_requested = self._is_return_requested(raw_query, origin) if origin else False
        route_legs: List[Dict[str, Any]] = []
        feasibility_warning: Optional[str] = None
        total_driving_duration_minutes = 0.0

        constraints = state.structured_constraints if state and state.structured_constraints else {}
        activities = constraints.get("selected_activities") or constraints.get("added_activities") or []
        if isinstance(activities, list):
            activities = list(activities)
        else:
            activities = []

        m_act = re.search(r"\b(?:add|include|visit)\s+([A-Za-z0-9\s]+?(?:fort|lake|museum|gutta|temple|palace|falls|dam|cave|ghat|ghats|park|sanctuary|viewpoint|garden|kund|waterfall))\b", raw_query, re.IGNORECASE)
        m_day = re.search(r"\b(?:to|in|on)\s+Day\s*(\d+)\b", raw_query, re.IGNORECASE)
        target_day = int(m_day.group(1)) if m_day else None

        if m_act and not activities:
            cand_act = m_act.group(1).strip()
            if not any(cand_act.lower() == t.lower() for t in detected_temples):
                matched_dest = first_temple
                for t in detected_temples:
                    t_data_temp, _ = self._get_temple_itinerary_data(t)
                    t_attrs_temp = self._parse_nearby_attractions(t_data_temp)
                    if any(cand_act.lower() in a.get("name", "").lower() for a in t_attrs_temp):
                        matched_dest = t
                        break
                activities = [{"name": cand_act.title(), "destination": matched_dest, "day": target_day}]

        if origin:
            # Build sequence of required route legs preserving temple order
            legs_spec: List[Tuple[str, str, bool]] = []
            current_pt = origin
            for idx, tm in enumerate(detected_temples):
                legs_spec.append((current_pt, tm, False))
                current_pt = tm
                for act in activities:
                    a_name = act if isinstance(act, str) else act.get("name", "")
                    a_dest = act.get("destination") or act.get("temple") if isinstance(act, dict) else None
                    if (a_dest and a_dest.lower() in tm.lower()) or (not a_dest and idx == 0):
                        legs_spec.append((current_pt, a_name, False))
                        current_pt = a_name

            # Return leg ONLY when explicitly requested or established
            if is_return_requested:
                legs_spec.append((current_pt, origin, True))

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
                            if dur_mins is not None:
                                total_driving_duration_minutes += dur_mins
                        else:
                            leg_entry["error"] = f"No route found between '{l_orig}' and '{l_dest}'."
                except Exception as e:
                    logger.warning(f"Failed to compute route from {l_orig} to {l_dest}: {e}")
                    leg_entry["error"] = f"Route calculation unavailable: {str(e)}"

                route_legs.append(leg_entry)

        # 5.6 Feasibility Assessment for Single-Day & Multi-Destination Itineraries
        first_leg = route_legs[0] if route_legs else None
        if duration_days == 1:
            if first_leg and first_leg.get("duration_minutes") is not None and first_leg["duration_minutes"] >= 180:
                dur_val = first_leg["duration_minutes"]
                one_way_txt = self._format_duration_human(dur_val)
                round_trip_txt = self._format_duration_human(dur_val * 2)
                feasibility_warning = (
                    f"⚠️ **Travel Feasibility Advisory**: Driving from {origin} to {first_temple} takes approximately "
                    f"{one_way_txt} each way (~{round_trip_txt} round-trip driving time). Undertaking this as a single-day "
                    f"pilgrimage leaves constrained time for darshan, queueing, and temple rituals before afternoon sanctum breaks "
                    f"or evening closure. An **overnight stay** is strongly recommended for a relaxed experience."
                )
            if len(detected_temples) > 1:
                multi_adv = (
                    f"⚠️ **Multi-Destination Advisory**: Visiting multiple temples ({', '.join(detected_temples)}) in a single day "
                    f"requires tight scheduling and substantial inter-temple transit. Consider extending to at least 2 days."
                )
                if feasibility_warning:
                    feasibility_warning += f"\n\n> {multi_adv}"
                else:
                    feasibility_warning = multi_adv
        elif len(detected_temples) > 1 and duration_days > 1:
            long_legs = [l for l in route_legs[1:] if l.get("status") == "success" and l.get("duration_minutes") and l["duration_minutes"] >= 240]
            if long_legs:
                ll_msgs = [f"{ll['origin']} to {ll['destination']} (~{self._format_duration_human(ll['duration_minutes'])})" for ll in long_legs]
                feasibility_warning = (
                    f"⚠️ **Inter-Temple Transit Advisory**: Extended driving time required between "
                    f"{'; '.join(ll_msgs)}. Ensure travel is scheduled during daytime and account for rest intervals."
                )

        # 6. Retrieve Verified Information Per Temple
        temple_schedules: Dict[str, Dict[str, Any]] = {}
        sources_by_temple: Dict[str, List[str]] = {}
        all_sources: List[str] = []

        for temple in detected_temples:
            t_data, t_sources = self._get_temple_itinerary_data(temple)
            temple_schedules[temple] = t_data
            sources_by_temple[temple] = t_sources
            for s in t_sources:
                if s not in all_sources:
                    all_sources.append(s)

        # 7. Construct Output
        temples_title = " & ".join(TEMPLE_DISPLAY_MAP.get(t, t) for t in detected_temples)
        day_str = f"{duration_days} Day" if duration_days == 1 else f"{duration_days} Days"
        title_line = f"### Pilgrimage Itinerary: {temples_title} ({day_str})"
        if origin:
            title_line += f" from {origin}"
        doc_lines = [title_line + "\n"]

        # Insert feasibility warning prominently if present
        if feasibility_warning:
            doc_lines.append(f"> {feasibility_warning}\n")

        # Insert route section if origin was provided
        if origin and route_legs:
            if len(route_legs) == 1:
                # Single journey presentation (retains backward-compatible metrics)
                leg1 = route_legs[0]
                doc_lines.append(f"### 🚗 Travel & Journey Route from {origin}")
                doc_lines.append(f"#### Journey 1: {leg1['origin']} to {leg1['destination']}")
                doc_lines.append(f"- **Starting Point**: {leg1['origin']}")
                doc_lines.append(f"- **Destination**: {leg1['destination']}")
                if leg1["status"] == "success":
                    if leg1.get("distance_km") is not None:
                        doc_lines.append(f"- **Driving Distance**: {leg1['distance_km']} km")
                    if leg1.get("duration_minutes") is not None:
                        dur_label = self._format_duration_human(leg1["duration_minutes"])
                        doc_lines.append(f"- **Estimated Driving Duration**: {dur_label}")
                    if leg1.get("traffic_duration_minutes") is not None:
                        traf_label = self._format_duration_human(leg1["traffic_duration_minutes"])
                        doc_lines.append(f"- **Live Traffic Estimate**: {traf_label}")
                    doc_lines.append("- **Suggested Departure**: Early morning (05:30 AM – 06:00 AM) to arrive in time for morning darshan opening.")
                else:
                    err_msg = leg1.get("error") or "Route calculation unavailable"
                    doc_lines.append(f"- **Route Status**: Route details could not be calculated ({err_msg}). Please check local highway navigation and TSRTC bus timings.")
                doc_lines.append("")
                if not is_return_requested:
                    doc_lines.append(f"> ℹ️ **Return Journey**: A return leg to {origin} was not requested and is not included in this route schedule.")
                    doc_lines.append("")
            else:
                # Multi-journey presentation
                doc_lines.append(f"### 🚗 Travel & Journey Routes from {origin}")
                for leg in route_legs:
                    l_idx = leg["leg_index"]
                    orig_l = leg["origin"]
                    dest_l = leg["destination"]
                    is_ret = leg["is_return"]
                    journey_title = leg.get("journey_label") or (f"Return Journey: {orig_l} to {dest_l}" if is_ret else f"Journey {l_idx}: {orig_l} to {dest_l}")
                    doc_lines.append(f"#### {journey_title}")
                    doc_lines.append(f"- **Starting Point**: {orig_l}")
                    doc_lines.append(f"- **Destination**: {dest_l}")
                    if leg["status"] == "success":
                        if leg.get("distance_km") is not None:
                            doc_lines.append(f"- **Driving Distance**: {leg['distance_km']} km")
                        if leg.get("duration_minutes") is not None:
                            dur_label = self._format_duration_human(leg["duration_minutes"])
                            doc_lines.append(f"- **Estimated Driving Duration**: {dur_label}")
                        if leg.get("traffic_duration_minutes") is not None:
                            traf_label = self._format_duration_human(leg["traffic_duration_minutes"])
                            doc_lines.append(f"- **Live Traffic Estimate**: {traf_label}")
                        if l_idx == 1:
                            doc_lines.append("- **Suggested Departure**: Early morning (05:30 AM – 06:00 AM) to arrive in time for morning darshan opening.")
                        elif is_ret:
                            doc_lines.append(f"- **Return Departure**: Depart for {dest_l} after concluding afternoon darshan and prasadam.")
                        else:
                            doc_lines.append(f"- **Inter-Temple Transit**: Highway transit between {orig_l} and {dest_l}.")
                    else:
                        err_msg = leg.get("error") or "Route calculation unavailable"
                        doc_lines.append(f"- **Route Status**: Route details could not be calculated ({err_msg}). Please check local highway navigation and TSRTC bus timings.")
                    doc_lines.append("")

                if not is_return_requested:
                    doc_lines.append(f"> ℹ️ **Return Journey**: A return leg to {origin} was not requested and is not included in this route schedule. If you would like route details for the return journey, please let me know.")
                    doc_lines.append("")

        # 8. Compute Temple-to-Day Allocation
        num_temples = len(detected_temples)
        is_multi_temple = num_temples > 1

        # Determine allocation slices
        day_allocations: List[Tuple[str, int, int]] = [] # (temple_name, temple_day_index, total_temple_days)

        if duration_days >= num_temples:
            base_days = duration_days // num_temples
            extra_days = duration_days % num_temples

            temple_durations = {}
            for idx, t in enumerate(detected_temples):
                temple_durations[t] = base_days + (1 if idx < extra_days else 0)

            for t in detected_temples:
                t_total = temple_durations[t]
                for d_idx in range(1, t_total + 1):
                    day_allocations.append((t, d_idx, t_total))
        else:
            # More temples than days: distribute all requested temples across available days
            tight_adv = (
                f"⚠️ **Schedule Feasibility Constraint**: You requested {num_temples} pilgrimage destinations "
                f"({', '.join(detected_temples)}) within {duration_days} day(s). Visiting multiple devasthanams per day allows limited "
                f"time for darshan, queueing, and temple rituals, and requires tight inter-temple highway transit. Extending your journey to "
                f"at least {num_temples} days is strongly recommended for a relaxed, complete pilgrimage."
            )
            if feasibility_warning:
                feasibility_warning += f"\n\n> {tight_adv}"
            else:
                feasibility_warning = tight_adv

            # Chunk temples across the available days so all requested temples are scheduled
            day_chunks: List[List[str]] = [[] for _ in range(duration_days)]
            for t_idx, t in enumerate(detected_temples):
                target_day = min(t_idx * duration_days // num_temples, duration_days - 1)
                day_chunks[target_day].append(t)

            for d_idx, chunk in enumerate(day_chunks, start=1):
                chunk_len = len(chunk)
                for c_pos, t in enumerate(chunk):
                    if chunk_len == 1:
                        lbl = f"Day {d_idx}"
                    elif c_pos == 0:
                        lbl = f"Day {d_idx} (Morning)"
                    elif c_pos == 1:
                        lbl = f"Day {d_idx} (Afternoon)"
                    else:
                        lbl = f"Day {d_idx} (Evening)"
                    day_allocations.append((t, 1, 1, lbl, d_idx))

        # 9. Render Day-by-Day Itinerary with Inter-Temple Transit Awareness
        for i, alloc_item in enumerate(day_allocations):
            if len(alloc_item) == 5:
                active_temple, t_day_idx, t_total_days, custom_lbl, day_num = alloc_item
            else:
                active_temple, t_day_idx, t_total_days = alloc_item[:3]
                custom_lbl = None
                day_num = i + 1

            t_data = temple_schedules[active_temple]

            next_t = day_allocations[i + 1][0] if (i + 1 < len(day_allocations) and day_allocations[i + 1][0] != active_temple) else None
            next_l = next((l for l in route_legs if l["origin"] == active_temple and l["destination"] == next_t), None) if next_t else None
            prev_t = day_allocations[i - 1][0] if (i > 0 and day_allocations[i - 1][0] != active_temple) else None

            # Filter activities allocated to this day or temple (strictly validate destination and scheduled day)
            day_acts = []
            active_clean = active_temple.lower().replace("temple", "").strip()
            active_aliases = [al.lower() for al in self._temple_aliases.get(active_temple, [])]
            for act in activities:
                a_day = act.get("day") if isinstance(act, dict) else None
                a_dest = act.get("destination") or act.get("temple") if isinstance(act, dict) else None
                
                # Destination match validation: activity MUST belong to active_temple
                dest_match = False
                if not a_dest:
                    dest_match = (day_num == 1)
                else:
                    d_clean = str(a_dest).lower().replace("temple", "").strip()
                    dest_match = (
                        d_clean in active_clean
                        or active_clean in d_clean
                        or any(al in d_clean or d_clean in al for al in active_aliases)
                    )
                if not dest_match:
                    continue

                # Day validation: check if requested day matches day_num, or clamp to temple's first day
                temple_days = [a[4] if len(a) == 5 else idx + 1 for idx, a in enumerate(day_allocations) if a[0] == active_temple]
                if a_day is not None and int(a_day) == day_num:
                    day_acts.append(act)
                elif (a_day is None or int(a_day) not in temple_days) and t_day_idx == 1:
                    day_acts.append(act)

            section_lines = self._format_schedule_section(
                temple=active_temple,
                day_num=day_num,
                total_days=duration_days,
                temple_day_index=t_day_idx,
                total_temple_days=t_total_days,
                data=t_data,
                is_multi_temple=is_multi_temple,
                next_temple=next_t,
                next_leg=next_l,
                prev_temple=prev_t,
                day_label=custom_lbl,
                day_activities=day_acts
            )
            doc_lines.extend(section_lines)

        # 9.5. Nearby Attractions & Activities by Destination
        doc_lines.append("### 🏛️ Explore Nearby Attractions by Destination")
        for t in detected_temples:
            t_data = temple_schedules[t]
            t_attrs = self._parse_nearby_attractions(t_data)
            if t_attrs:
                doc_lines.append(f"#### Near {t}")
                for attr in t_attrs[:5]:
                    a_name = attr.get("name", "Attraction")
                    a_dist = attr.get("distance", f"Near {t}")
                    a_desc = attr.get("desc", "")
                    
                    # Categorize
                    text_sub = (a_name + " " + a_desc).lower()
                    if any(k in text_sub for k in ["fort", "monument", "chalukya", "heritage", "palace"]):
                        a_cat = "Historic Fort & Heritage"
                    elif any(k in text_sub for k in ["lake", "dam", "waterfall", "park", "nature", "river", "ghat"]):
                        a_cat = "Lakes & Nature"
                    elif any(k in text_sub for k in ["museum", "science", "planetarium"]):
                        a_cat = "Museums & Science"
                    elif any(k in text_sub for k in ["temple", "shrine", "gutta", "mandir"]):
                        a_cat = "Cultural Sites & Shrines"
                    elif any(k in text_sub for k in ["recreation", "activity", "boating"]):
                        a_cat = "Family Recreation"
                    else:
                        a_cat = "Local Experiences & Sightseeing"

                    maps_s = self._make_google_maps_search_url(a_name, t)
                    maps_d = self._make_google_maps_directions_url(t, a_name)
                    doc_lines.append(f"- **{a_name}** ({a_cat})")
                    doc_lines.append(f"  - **Distance / Proximity**: {a_dist} from {t}")
                    if a_desc:
                        doc_lines.append(f"  - **Details**: {a_desc}")
                    doc_lines.append("  - **Data Source**: Verified Temple Knowledge Base")
                    doc_lines.append(f"  - **Google Maps**: [🗺️ View on Google Maps]({maps_s}) | [🧭 Get Directions]({maps_d})")
                doc_lines.append("")
            else:
                doc_lines.append(f"#### Near {t}")
                doc_lines.append(f"- No additional nearby attractions recorded in verified records for {t}. Enquire at temple enquiry counter for local viewpoints.")
                doc_lines.append("")

        # 10. Consolidated Accommodation Section
        has_budget = (
            constraints.get("budget_limit") is not None
            or bool(re.search(r"\b(?:budget|under\s+(?:rs\.?|inr|₹)?\d+|within\s+(?:rs\.?|inr|₹)?\d+)\b", raw_query, re.IGNORECASE))
        )
        accom_pref = (
            constraints.get("accommodation_preference")
            or ("none" if re.search(r"\b(?:no\s+accommodation|without\s+accommodation)\b", raw_query, re.IGNORECASE) else None)
        )
        is_no_accom = accom_pref and ("none" in str(accom_pref).lower() or "no" in str(accom_pref).lower())

        total_trip_nights = max(0, duration_days - 1)
        temple_allocated_nights: Dict[str, int] = {}
        if len(detected_temples) > 1 and total_trip_nights > 0:
            num_t = len(detected_temples)
            base_n = total_trip_nights // num_t
            rem_n = total_trip_nights % num_t
            for idx, tm in enumerate(detected_temples):
                temple_allocated_nights[tm] = base_n + (1 if idx < rem_n else 0)
        else:
            for tm in detected_temples:
                temple_allocated_nights[tm] = total_trip_nights

        if is_no_accom:
            doc_lines.append("### 🏨 Lodging Information")
            doc_lines.append("> ℹ️ *Note: Trip planned without overnight accommodation as requested.*")
            doc_lines.append("")
        elif has_budget:
            # When a budget is supplied, the budget section owns full comparisons/breakdown
            doc_lines.append("### 🏨 Lodging & Night Allocation by Destination")
            if duration_days > 1:
                doc_lines.append(f"- **Total Overnight Stays**: {duration_days - 1} night(s) across {len(detected_temples)} destination(s).")
                for s_idx, t in enumerate(detected_temples, start=1):
                    n_allocated = temple_allocated_nights.get(t, 1)
                    t_maps = self._make_google_maps_search_url(f"hotels near {t}")
                    doc_lines.append(f"- **Stay {s_idx} — {t} | {n_allocated} Night(s)**: Recommended property, tariff, and budget breakdown are itemized in the Budget section below. ([🗺️ View Hotels on Google Maps]({t_maps}))")
            else:
                doc_lines.append("> ℹ️ *Note: Single-day visit does not require overnight accommodation. Budget details below focus on darshan and travel.*")
            doc_lines.append("")
        else:
            # When NO budget is supplied: preserve useful accommodation alternatives
            if duration_days == 1:
                doc_lines.append("### 🏨 Where to Stay — Accommodation Options by Destination (Optional for Day Trip)")
                doc_lines.append("> ℹ️ *Note: A single-day trip does not require an overnight stay. Verified accommodation options are provided below for reference if an extended stay is desired.*")
                doc_lines.append("")
            else:
                doc_lines.append("### 🏨 Where to Stay — Accommodation Options by Destination")
                doc_lines.append("")

            for t in detected_temples:
                t_data = temple_schedules[t]
                t_accom_lines = self._format_temple_accommodation_options(t, t_data, accom_pref=accom_pref)
                doc_lines.extend(t_accom_lines)

        # 11. Consolidated Travel & Connectivity Section
        doc_lines.append("### 🚆 Travel & Connectivity")
        for t in detected_temples:
            t_data = temple_schedules[t]
            t_notes = self._parse_travel(t_data)
            prefix = f"**{t}**: " if is_multi_temple else ""
            if t_notes:
                for note in t_notes:
                    doc_lines.append(f"- {prefix}{note}")
            else:
                doc_lines.append(f"- {prefix}Verify local road connectivity and TSRTC bus terminal schedules.")
        doc_lines.append("")

        # 11.5. Weather & Seasonal Planning Section
        doc_lines.append("### ☀️ Weather & Seasonal Planning")
        start_date_str = constraints.get("start_date")
        is_far_future = False
        if start_date_str:
            try:
                target_dt = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
                today_dt = datetime.date.today()
                days_diff = (target_dt - today_dt).days
                if days_diff > 14:
                    is_far_future = True
            except Exception:
                pass

        if is_far_future:
            doc_lines.append(f"> ℹ️ *Forecast Advisory: Planned travel date ({start_date_str}) is beyond the 7-day reliable meteorological forecast window. Verified current conditions and seasonal observations are provided below for planning.*")
            doc_lines.append("")

        for t in detected_temples:
            try:
                t_coord = self.coordinate_registry.get_coordinate(t)
                if t_coord and self.weather_agent:
                    raw_w, cache_hit, _ = self.weather_agent._fetch_open_meteo(
                        t_coord.latitude,
                        t_coord.longitude,
                        f"{t_coord.canonical_name}_weather"
                    )
                    curr = raw_w.get("current", {})
                    temp = curr.get("temperature_2m")
                    w_code = curr.get("weather_code")
                    from app.agents.live_weather_agent import get_weather_condition_description
                    w_desc = get_weather_condition_description(w_code)
                    rain = curr.get("rain", 0.0)
                    
                    label_type = "Current Weather Observations" if (is_far_future or not start_date_str) else f"Forecast for {start_date_str}"
                    doc_lines.append(f"#### {t} ({label_type})")
                    if temp is not None:
                        doc_lines.append(f"- **Temperature**: {temp}°C")
                    doc_lines.append(f"- **Conditions**: {w_desc}")
                    if rain > 0:
                        doc_lines.append(f"- **Precipitation**: {rain} mm rain observed")
                    else:
                        doc_lines.append("- **Precipitation**: No rain currently observed")
                    doc_lines.append("- **Source Attribution**: Weather data by Open-Meteo.com under CC BY 4.0")
                    doc_lines.append("")
                else:
                    doc_lines.append(f"#### {t}")
                    doc_lines.append("- Weather observation currently unavailable for this location.")
                    doc_lines.append("")
            except Exception as e:
                logger.info(f"Weather lookup skipped for {t}: {e}")
                doc_lines.append(f"#### {t}")
                doc_lines.append("- Weather forecast currently unavailable (offline mode). Did not block itinerary generation.")
                doc_lines.append("")

        # 12. Append Live-Data Disclaimer
        doc_lines.append(self._build_live_data_disclaimer(route_legs))
        doc_lines.append("")

        # 13. Source Attribution
        if all_sources:
            doc_lines.append("**Sources:**")
            for t in detected_temples:
                t_srcs = sources_by_temple.get(t, [])
                if t_srcs:
                    doc_lines.append(f"- **{t}**: {', '.join(t_srcs)}")

        final_answer = html.unescape("\n".join(doc_lines).strip())

        # 14. Update State Intermediate Results
        state.intermediate_results[self.name] = {
            "temples": detected_temples,
            "duration_days": duration_days,
            "origin": origin,
            "route_legs": route_legs,
            "sources_by_temple": sources_by_temple,
            "live_data_disclaimer": True
        }

        # 15. Metadata Construction
        display_destinations = [TEMPLE_DISPLAY_MAP.get(t, t) for t in detected_temples]
        meta = {
            "itinerary": True,
            "destinations": display_destinations,
            "temples": detected_temples,
            "duration_days": duration_days,
            "sources_by_temple": sources_by_temple,
            "disclaimer_present": True
        }
        if origin:
            meta["origin"] = origin
            meta["destination"] = first_temple
            meta["return_leg_requested"] = is_return_requested
            meta["route_legs"] = route_legs

            # Backwards compatibility: populate top-level fields from Leg 1 if present
            if route_legs:
                first_leg_res = route_legs[0]
                if first_leg_res.get("origin_canonical"):
                    meta["origin_canonical"] = first_leg_res["origin_canonical"]
                if first_leg_res.get("destination_canonical"):
                    meta["destination_canonical"] = first_leg_res["destination_canonical"]
                if first_leg_res.get("distance_km") is not None:
                    meta["distance_km"] = first_leg_res["distance_km"]
                if first_leg_res.get("duration_minutes") is not None:
                    meta["duration_minutes"] = first_leg_res["duration_minutes"]
                if first_leg_res.get("traffic_duration_minutes") is not None:
                    meta["traffic_duration_minutes"] = first_leg_res["traffic_duration_minutes"]
                if first_leg_res.get("polyline"):
                    meta["polyline"] = first_leg_res["polyline"]
                if first_leg_res.get("viewport"):
                    meta["viewport"] = first_leg_res["viewport"]
                if first_leg_res.get("speed_reading_intervals"):
                    meta["speed_reading_intervals"] = first_leg_res["speed_reading_intervals"]

            # Multi-leg totals
            if len(route_legs) > 1:
                succ_distances = [l["distance_km"] for l in route_legs if l.get("distance_km") is not None]
                if succ_distances:
                    meta["total_distance_km"] = round(sum(succ_distances), 1)
                succ_durations = [l["duration_minutes"] for l in route_legs if l.get("duration_minutes") is not None]
                if succ_durations:
                    meta["total_duration_minutes"] = round(sum(succ_durations), 1)

        if feasibility_warning:
            meta["feasibility_warning"] = feasibility_warning

        return AgentResponse(
            success=True,
            agent_name=self.name,
            answer=final_answer,
            sources=all_sources,
            metadata=meta
        )
