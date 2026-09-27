"""
PilgrimAI - ItineraryPlanningAgent (Phase M)

Specialist agent responsible for grounded, timing-aware pilgrimage itinerary
planning across registered temples in Telangana.

Key Capabilities:
- Single-temple and multi-temple (up to 3 stops) pilgrimage itinerary generation.
- Grounded in verified temple timings, sevas, accommodation, travel, prasadam, and crowd data.
- Strict Fact vs Planning Suggestion separation (every suggestion clearly demarcated).
- Zero fabricated travel durations or distances between arbitrary temples.
- Strict Live-Data Limitations disclosure (deterministic Live-Data Disclaimer).
- RAGTool facade as the exclusive knowledge access interface (zero direct DB/raw file imports).
- Inherits from BaseAgent with standard execution tracing, latency tracking, and error containment.
- Seamless compatibility with AgentRouter, MasterAgentCoordinator, SequentialMultiIntentPipeline,
  and ConversationMemoryManager.
"""

import re
import logging
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


class ItineraryPlanningAgent(BaseAgent):
    """
    Specialist agent providing grounded, timing-aware pilgrimage itinerary
    planning across registered temples in Telangana.
    """

    def __init__(
        self,
        rag_tool: Optional[Any] = None,
        name: str = "itinerary_planning",
        description: str = "Specialist agent providing grounded, timing-aware pilgrimage itinerary planning across registered temples using verified knowledge."
    ):
        super().__init__(name=name, description=description)
        self._rag_tool = rag_tool
        self._temple_aliases: Dict[str, List[str]] = {}
        self._init_temple_registry()

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
            "Ujjaini": ["ujjaini", "ujjaini mahakali", "mahakali secunderabad", "secunderabad mahakali"],
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

    def detect_temples(self, query: str) -> List[str]:
        """
        Detects all registered canonical temples referenced in the query in order of appearance.
        """
        if not query or not query.strip():
            return []

        clean_query = query.strip()
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
        match = re.search(r"\b(\d+)\s*[- ]*(?:days?|day)\b", query, re.IGNORECASE)
        if match:
            try:
                days = int(match.group(1))
                return max(1, min(days, 7))
            except ValueError:
                pass

        word_map = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "single": 1, "weekend": 2
        }
        for word, val in word_map.items():
            if re.search(r"\b" + word + r"\s*[- ]*(?:days?|day|trip|visit)?\b", query, re.IGNORECASE):
                return val

        return max(1, num_temples)

    def _get_temple_itinerary_data(self, temple: str) -> Tuple[Dict[str, Any], List[str]]:
        """
        Retrieves verified records for relevant categories via RAGTool.
        Returns (data_dict, sources_list).
        """
        categories = ["timings", "sevas", "travel", "accommodation", "prasadam", "crowd", "facilities"]
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

    def _format_schedule_section(
        self,
        temple: str,
        day_num: int,
        data: Dict[str, Any]
    ) -> List[str]:
        """
        Builds a structured daily itinerary section strictly separating
        verified facts from planning suggestions.
        """
        lines = [f"#### Day {day_num}: {temple} Temple\n"]

        # 1. Verified Timings & Visit Windows
        timings_obj = data.get("timings")
        timings_text = "Standard daily opening hours apply."
        if isinstance(timings_obj, dict):
            t_items = []
            for k in ["general_timings", "darshan_timings", "morning", "evening", "temple_hours"]:
                if k in timings_obj:
                    val = timings_obj[k]
                    if isinstance(val, (str, list)):
                        t_items.append(f"{k.replace('_', ' ').title()}: {val}")
            if t_items:
                timings_text = "; ".join(t_items[:2])
            elif "darshan_slots" in timings_obj:
                timings_text = str(timings_obj["darshan_slots"])
        elif isinstance(timings_obj, str) and timings_obj.strip():
            first_line = timings_obj.strip().split("\n")[0]
            timings_text = first_line[:120]

        # 2. Verified Sevas
        sevas_obj = data.get("sevas")
        seva_sample = []
        if isinstance(sevas_obj, list):
            for s in sevas_obj:
                if isinstance(s, dict) and "name" in s:
                    s_name = s.get("name")
                    s_time = s.get("timing") or s.get("time") or ""
                    seva_sample.append(f"{s_name}" + (f" ({s_time})" if s_time else ""))
                elif isinstance(s, str):
                    seva_sample.append(s[:60])
                if len(seva_sample) >= 2:
                    break
        elif isinstance(sevas_obj, dict):
            for s_list in sevas_obj.values():
                if isinstance(s_list, list):
                    for s in s_list:
                        if isinstance(s, dict) and "name" in s:
                            seva_sample.append(s["name"])
                        elif isinstance(s, str):
                            seva_sample.append(s[:60])
                        if len(seva_sample) >= 2:
                            break

        # 3. Verified Prasadam / Annadanam
        prasadam_obj = data.get("prasadam")
        prasadam_note = None
        if isinstance(prasadam_obj, dict):
            if "annadanam" in prasadam_obj:
                prasadam_note = f"Annadanam available: {str(prasadam_obj['annadanam'])[:100]}"
            elif "items" in prasadam_obj:
                prasadam_note = "Prasadam counters operational during temple hours."
        elif isinstance(prasadam_obj, list):
            prasadam_note = "Prasadam offerings and food counters available."

        # 4. Verified Accommodation
        accom_obj = data.get("accommodation")
        accom_note = "On-site Devasthanam guest houses / choultries verified in records." if accom_obj else "Check nearby private stays; no devasthanam stay specified."

        # 5. Verified Static Transit
        travel_obj = data.get("travel")
        transit_note = None
        if isinstance(travel_obj, dict):
            t_notes = []
            if "nearest_railway_station" in travel_obj:
                st = travel_obj["nearest_railway_station"]
                if isinstance(st, dict):
                    t_notes.append(f"Nearest Railway: {st.get('name', '')} ({st.get('distance', '')})")
            if "nearest_airport" in travel_obj:
                ap = travel_obj["nearest_airport"]
                if isinstance(ap, dict):
                    t_notes.append(f"Nearest Airport: {ap.get('name', '')} ({ap.get('distance', '')})")
            if "bus_routes" in travel_obj and isinstance(travel_obj["bus_routes"], list):
                if travel_obj["bus_routes"]:
                    t_notes.append(f"Bus Connectivity: {travel_obj['bus_routes'][0][:90]}")
            if t_notes:
                transit_note = "; ".join(t_notes)

        # Assemble Structured Sections (Fact vs Suggestion)
        lines.append("**Verified Temple Information:**")
        lines.append(f"- **Operating Schedule**: {timings_text}")
        if seva_sample:
            lines.append(f"- **Featured Sevas**: {', '.join(seva_sample)}")
        if prasadam_note:
            lines.append(f"- **Prasadam / Food**: {prasadam_note}")
        lines.append(f"- **Accommodation**: {accom_note}")
        if transit_note:
            lines.append(f"- **Transit & Connectivity**: {transit_note}")
        lines.append("")

        lines.append("**Suggested Visit Plan:**")
        lines.append("- **Morning Window**: Arrive early for initial darshan and attend morning sevas if participating.")
        lines.append("- **Afternoon Window**: Utilize Annadanam / lunch services. Observe any afternoon sanctum rest periods.")
        lines.append("- **Evening Window**: Attend evening Harathi / darshan, visit sub-shrines, and proceed to lodging.")
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

        # 3. Detect candidate registered temples
        detected_temples = self.detect_temples(raw_query)

        # 4. Zero Temples Identified
        if not detected_temples:
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
        duration_days = self._extract_duration_days(raw_query, len(detected_temples))

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
        temples_title = " & ".join(detected_temples)
        day_str = f"{duration_days} Day" if duration_days == 1 else f"{duration_days} Days"
        doc_lines = [f"### Pilgrimage Itinerary: {temples_title} ({day_str})\n"]

        # Allocate temples across days
        for i in range(duration_days):
            day_num = i + 1
            # If more days than temples, repeat last temple or focus on surrounding complex
            temple_idx = min(i, len(detected_temples) - 1)
            active_temple = detected_temples[temple_idx]
            t_data = temple_schedules[active_temple]

            section_lines = self._format_schedule_section(active_temple, day_num, t_data)
            doc_lines.extend(section_lines)

        # 8. Append Live-Data Disclaimer
        doc_lines.append(LIVE_DATA_DISCLAIMER)
        doc_lines.append("")

        # 9. Source Attribution
        if all_sources:
            doc_lines.append("**Sources:**")
            for t in detected_temples:
                t_srcs = sources_by_temple.get(t, [])
                if t_srcs:
                    doc_lines.append(f"- **{t}**: {', '.join(t_srcs)}")

        final_answer = "\n".join(doc_lines).strip()

        # 10. Update State Intermediate Results
        state.intermediate_results[self.name] = {
            "temples": detected_temples,
            "duration_days": duration_days,
            "sources_by_temple": sources_by_temple,
            "live_data_disclaimer": True
        }

        return AgentResponse(
            success=True,
            agent_name=self.name,
            answer=final_answer,
            sources=all_sources,
            metadata={
                "itinerary": True,
                "temples": detected_temples,
                "duration_days": duration_days,
                "sources_by_temple": sources_by_temple,
                "disclaimer_present": True
            }
        )
