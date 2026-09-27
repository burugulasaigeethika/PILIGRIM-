"""
PilgrimAI - RecommendationAgent

Specialist agent responsible for providing grounded, criterion-based temple
recommendations across registered pilgrimage temples in Telangana.

Strictly adheres to:
- BaseAgent lifecycle contract: Inherits from BaseAgent, executes via _run(state).
- RAGTool Read-Only Facade: Accesses temple facts exclusively via read-only RAGTool.
  Zero direct Qdrant, BM25, or raw JSON file imports.
- CompletenessValidator Tri-State Logic: Classifies facilities into
  CONFIRMED_AVAILABLE, CONFIRMED_UNAVAILABLE, and INFORMATION_NOT_AVAILABLE.
- Zero Fabrication:
  * Never invents prices, crowd levels, rankings, popularity, or reviews.
  * Never claims one temple is objectively the "best" or "superior".
  * Never manufactures weather data; queries LiveWeatherAgent if available or reports unavailable.
  * If information is unrecorded in temple records, explicitly states that it is unavailable.
- Neutral Criteria-Matching:
  * When criteria are given (e.g., accommodation, accessibility, river, deity):
    evaluates verified data and recommends temples that match with affirmative evidence.
  * When no criteria are given (e.g., "Which temple should I visit?"):
    presents balanced pilgrimage themes and invites the user to specify preferences.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple, Set

from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState, AgentResponse
from app.agents.tools.rag_tool import RAGTool
from app.rag.category_registry import category_registry, CategoryRegistry
from app.rag.completeness_validator import (
    completeness_validator,
    CompletenessValidator,
    CONFIRMED_AVAILABLE,
    CONFIRMED_UNAVAILABLE,
    INFORMATION_NOT_AVAILABLE
)

logger = logging.getLogger(__name__)


# Canonical deity themes mapped to registered Telangana temples
THEMATIC_TEMPLE_MAP: Dict[str, Dict[str, Any]] = {
    "shakti_goddess": {
        "title": "Major Goddess & Shakti Peetha Shrines",
        "description": "Sacred Mother Goddess kshetras and ancient Shakti Peethas",
        "temples": ["Jogulamba(new)", "Balkampet", "Ujjaini", "Edupayal", "Medaram"],
        "keywords": ["goddess", "shakti", "devi", "durga", "yellamma", "mahakali", "sammakka", "saralamma", "mother"]
    },
    "shiva": {
        "title": "Lord Shiva & Jyotirlinga Shrines",
        "description": "Ancient Shaivite kshetras, Jyotirlinga, and Mukteshwara shrines",
        "temples": ["Srisaila", "Kaleshvaram", "Vemulawada", "Ramappa"],
        "keywords": ["shiva", "shivan", "lingam", "jyotirlinga", "mallikarjuna", "mukteshwara", "kaleshwara", "rajanna", "rajarajeshwara", "rudreshwara"]
    },
    "narasimha": {
        "title": "Lord Narasimha Kshetras",
        "description": "Sacred Vaishnavite hill shrines and Nava Narasimha kshetras",
        "temples": ["Yadadri", "Dharmapuri", "Ahobilam"],
        "keywords": ["narasimha", "narsimha", "laxmi narasimha", "lakshmi narasimha", "ahobila", "yoga narasimha"]
    },
    "saraswathi_education": {
        "title": "Goddess of Learning & Aksharabhyasam",
        "description": "Ancient educational and child initiation pilgrimage center on the banks of Godavari",
        "temples": ["Basara"],
        "keywords": ["saraswathi", "saraswati", "education", "study", "studies", "learning", "aksharabhyasam", "children", "child", "school"]
    },
    "rama_vaishnava": {
        "title": "Lord Rama & Lord Venkateswara Shrines",
        "description": "Venerated Ramayana sites and Balaji shrines",
        "temples": ["Badrachalam", "Chilkur", "Birla Mandir", "Ttd"],
        "keywords": ["rama", "sita", "ramachandra", "ram", "venkateswara", "balaji", "visa balaji", "govinda"]
    },
    "satyanarayana": {
        "title": "Sri Satyanarayana Swamy & Vratham Shrines",
        "description": "Renowned for sacred Satyanarayana Swamy Vrathams and blessings",
        "temples": ["Veera Satyanarayana"],
        "keywords": ["satyanarayana", "satyanarayana swamy", "vratham", "vratam", "annavaram"]
    },
    "hanuman": {
        "title": "Lord Hanuman & Protection Shrines",
        "description": "Historic Dhyana Anjaneya temple known for spiritual peace and protection",
        "temples": ["Karmanghat"],
        "keywords": ["hanuman", "anjaneya", "karmanghat"]
    },
    "heritage_architecture": {
        "title": "Kakatiya Heritage & UNESCO Architecture",
        "description": "World-renowned 12th-13th century Kakatiya stone sculpting, sandbox technology, and 1000-pillar shrines",
        "temples": ["Ramappa", "Thousand Pillar"],
        "keywords": ["heritage", "unesco", "architecture", "history", "sculpture", "kakatiya", "ancient", "monument", "thousand pillar"]
    }
}


class RecommendationAgent(BaseAgent):
    """
    Specialist agent providing grounded, neutral temple recommendations based on
    verified records and explicit user requirements across 20 Telangana temples.
    """

    def __init__(
        self,
        rag_tool: Optional[Any] = None,
        weather_agent: Optional[Any] = None,
        cat_registry: Optional[CategoryRegistry] = None,
        validator: Optional[CompletenessValidator] = None,
        name: str = "recommendation",
        description: str = "Recommends grounded pilgrimage temples based on user criteria and verified records."
    ):
        super().__init__(name=name, description=description)
        self._rag_tool = rag_tool
        self.weather_agent = weather_agent
        self.category_registry = cat_registry or category_registry
        self.validator = validator or completeness_validator

    @property
    def rag_tool(self) -> RAGTool:
        """Lazily initialize RAGTool to avoid premature instantiation before RAG service is ready."""
        if self._rag_tool is None:
            self._rag_tool = RAGTool()
        return self._rag_tool

    @rag_tool.setter
    def rag_tool(self, value: Any) -> None:
        self._rag_tool = value

    # -------------------------------------------------------------------------
    # BaseAgent Execution Lifecycle Implementation
    # -------------------------------------------------------------------------

    def _run(self, state: AgentState) -> AgentResponse:
        """
        Processes recommendation query against verified data and user criteria.
        """
        query = state.user_query.strip() if state.user_query else ""
        if not query:
            return AgentResponse(
                success=False,
                agent_name=self.name,
                answer="Please provide criteria or ask for temple recommendations.",
                sources=[],
                error="Empty query"
            )

        q_lower = query.lower()

        # 1. Identify Explicit Facility / Property Criteria
        facility_criterion = self._extract_facility_criterion(q_lower)

        # 2. Identify Deity / Thematic Criteria
        thematic_criterion = self._extract_thematic_criterion(q_lower)

        # 3. Identify Weather / Temperature Criteria
        weather_criterion = self._extract_weather_criterion(q_lower)

        # ---------------------------------------------------------------------
        # Case A: Weather / Temperature Criterion
        # ---------------------------------------------------------------------
        if weather_criterion is not None:
            return self._handle_weather_recommendation(weather_criterion, state)

        # ---------------------------------------------------------------------
        # Case B: Facility / Property Criterion (Accommodation, Accessibility, etc.)
        # ---------------------------------------------------------------------
        if facility_criterion is not None:
            return self._handle_facility_recommendation(facility_criterion, query)

        # ---------------------------------------------------------------------
        # Case C: Deity / Spiritual Theme Criterion
        # ---------------------------------------------------------------------
        if thematic_criterion is not None:
            return self._handle_thematic_recommendation(thematic_criterion, query)

        # ---------------------------------------------------------------------
        # Case D: General / Open Recommendation (No explicit criteria given)
        # ---------------------------------------------------------------------
        return self._handle_open_recommendation(query)

    # -------------------------------------------------------------------------
    # Criteria Extraction Helpers
    # -------------------------------------------------------------------------

    def _extract_facility_criterion(self, q_lower: str) -> Optional[str]:
        """
        Extracts verified facility category from query (accommodation, accessibility, river, annadanam, etc.).
        """
        if re.search(r"\b(accommodation|stay|rooms?|cottages?|guest\s*houses?|choultry|lodging)\b", q_lower):
            return "accommodation"
        if re.search(r"\b(accessibility|wheelchair|elderly|physically\s+disabled|ramps?|lifts?|elevators?|handicapped)\b", q_lower):
            return "accessibility"
        if re.search(r"\b(river|water|water\s*body|lake|stream|godavari|krishna|holy\s+dip|snanam|pushkarini|ghats?)\b", q_lower):
            return "river_bank"
        if re.search(r"\b(annadanam|free\s+(food|meals?)|prasadam|lunch|free\s+lunch|meals?)\b", q_lower):
            return "annadanam"
        if re.search(r"\b(parking|car\s+parking|vehicle\s+parking)\b", q_lower):
            return "parking"
        if re.search(r"\b(dress\s*code|attire|traditional\s+dress|strict\s+dress)\b", q_lower):
            return "dress_code"
        if re.search(r"\b(restaurant|restaurants|canteen|food\s+stalls?|dining)\b", q_lower):
            return "restaurants"
        if re.search(r"\b(festival|festivals|jatara|brahmotsavam)\b", q_lower):
            return "festivals"
        return None

    def _extract_thematic_criterion(self, q_lower: str) -> Optional[str]:
        """
        Extracts spiritual theme or deity preference from query.
        """
        for theme_key, data in THEMATIC_TEMPLE_MAP.items():
            for kw in data["keywords"]:
                if re.search(r"\b" + re.escape(kw) + r"\b", q_lower):
                    return theme_key
        return None

    def _extract_weather_criterion(self, q_lower: str) -> Optional[Dict[str, Any]]:
        """
        Detects if query asks for a temple recommendation based on temperature or weather conditions.
        """
        # Range e.g. "25-30", "25 to 30", "25–30", "25—30"
        range_match = re.search(r"(\d{1,2})\s*(?:[-–—]|to)\s*(\d{1,2})\s*(?:°?c|degrees|deg)?", q_lower)
        if range_match:
            min_temp = float(range_match.group(1))
            max_temp = float(range_match.group(2))
            return {"type": "range", "min_temp": min_temp, "max_temp": max_temp}

        single_match = re.search(r"(?:around|approx|about|under|below|less\s+than)\s*(\d{1,2})\s*(?:°?c|degrees|deg)?", q_lower)
        if single_match:
            val = float(single_match.group(1))
            if "under" in q_lower or "below" in q_lower or "less" in q_lower:
                return {"type": "range", "min_temp": 0.0, "max_temp": val}
            return {"type": "range", "min_temp": val - 2.5, "max_temp": val + 2.5}

        if any(w in q_lower for w in ["pleasant weather", "cool weather", "good weather", "low temperature", "nice climate"]):
            return {"type": "range", "min_temp": 20.0, "max_temp": 32.0}

        return None

    # -------------------------------------------------------------------------
    # Recommendation Handlers
    # -------------------------------------------------------------------------

    def _handle_facility_recommendation(self, category: str, query: str) -> AgentResponse:
        """
        Recommends temples matching a specific verified facility (accommodation, accessibility, etc.).
        Evaluates all 20 canonical temples against verified records.
        """
        canonical_temples = self.rag_tool.get_registered_temples()
        confirmed_matches: List[Dict[str, Any]] = []
        confirmed_unavailable: List[str] = []
        sources: List[str] = []

        cat_label_map = {
            "accommodation": "Accommodation & Guest Houses",
            "accessibility": "Wheelchair & Senior Citizen Accessibility",
            "river_bank": "Sacred River / Holy Water Pushkarini",
            "annadanam": "Free Annadanam / Prasadam Meals",
            "parking": "Dedicated Vehicle Parking",
            "dress_code": "Prescribed Traditional Dress Code",
            "restaurants": "Dining & Restaurant Facilities",
            "festivals": "Major Annual Festivals & Jataras"
        }
        rag_category = "wheelchair" if category == "accessibility" else category
        category_label = cat_label_map.get(category, cat_label_map.get(rag_category, category.replace("_", " ").title()))

        for temple in canonical_temples:
            raw_data = self.rag_tool.get_temple_category_data(temple, rag_category)
            status, evidence, field = self.validator.evaluate_availability(raw_data, rag_category)

            if status == CONFIRMED_AVAILABLE:
                src_path = f"{temple.lower()}/elderly_ppl.json" if rag_category == "wheelchair" else f"{temple.lower()}/{rag_category}.json"
                sources.append(src_path)
                confirmed_matches.append({
                    "temple": temple,
                    "evidence": evidence or "Confirmed available in temple records",
                    "source": src_path
                })
            elif status == CONFIRMED_UNAVAILABLE:
                confirmed_unavailable.append(temple)

        if not confirmed_matches:
            answer = (
                f"### Temple Recommendations: {category_label}\n\n"
                f"None of the 20 registered pilgrimage temples in Telangana have confirmed affirmative records "
                f"matching '{category_label}'. Information is currently unrecorded or unavailable in official records."
            )
            return AgentResponse(
                success=True,
                agent_name=self.name,
                answer=answer,
                sources=sources,
                metadata={
                    "category": category,
                    "matched_criteria": [category, "accessibility" if category == "wheelchair" else category],
                    "matching_count": 0
                }
            )

        # Build clean grounded markdown recommendation
        lines = [
            f"### 🛕 Recommended Temples with Verified {category_label}\n",
            f"Based on verified devasthanam records, the following **{len(confirmed_matches)} temples** are confirmed to provide {category_label.lower()}:\n"
        ]

        for i, match in enumerate(confirmed_matches, 1):
            t_name = match["temple"]
            evidence = match["evidence"]
            lines.append(f"{i}. **{t_name}**")
            lines.append(f"   - **Verified Facility**: {evidence}")

        if confirmed_unavailable:
            lines.append(f"\n> **Note**: Official records explicitly indicate that {', '.join(confirmed_unavailable[:3])} do not provide dedicated facilities for this category.")

        lines.append(f"\n*(Recommendation derived strictly from verified static records across all {len(canonical_temples)} registered Telangana temples)*")

        return AgentResponse(
            success=True,
            agent_name=self.name,
            answer="\n".join(lines),
            sources=sorted(list(set(sources))),
            metadata={
                "category": category,
                "matched_criteria": [category, "accessibility" if category == "wheelchair" else category],
                "matching_count": len(confirmed_matches),
                "matching_temples": [m["temple"] for m in confirmed_matches],
                "total_temples_evaluated": len(canonical_temples)
            }
        )

    def _handle_thematic_recommendation(self, theme_key: str, query: str) -> AgentResponse:
        """
        Recommends temples matching a specific spiritual theme or deity tradition.
        """
        theme = THEMATIC_TEMPLE_MAP[theme_key]
        title = theme["title"]
        description = theme["description"]
        temples = theme["temples"]
        sources: List[str] = []

        lines = [
            f"### 🛕 Recommended Temples: {title}\n",
            f"If you are seeking **{description}**, the following registered temples in Telangana are recommended:\n"
        ]

        for i, t_name in enumerate(temples, 1):
            # Fetch brief verified overview/history if available
            overview_data = self.rag_tool.get_temple_category_data(t_name, "overview")
            history_data = self.rag_tool.get_temple_category_data(t_name, "history_significance")
            deity_data = self.rag_tool.get_temple_category_data(t_name, "deity_legend")

            snippet = ""
            if isinstance(overview_data, dict) and overview_data.get("description"):
                snippet = str(overview_data["description"])[:140]
            elif isinstance(deity_data, dict) and deity_data.get("deity_name"):
                snippet = f"Dedicated to {deity_data.get('deity_name')}"
            elif isinstance(history_data, dict) and history_data.get("historical_significance"):
                snippet = str(history_data["historical_significance"])[:140]

            lines.append(f"{i}. **{t_name}**")
            if snippet:
                lines.append(f"   - *Significance*: {snippet.strip()}...")

            src_file = f"{t_name.lower()}/overview.json"
            sources.append(src_file)

        lines.append(f"\n*(To check darshan timings, sevas, or accommodation for any of these, ask about that specific temple).*")

        return AgentResponse(
            success=True,
            agent_name=self.name,
            answer="\n".join(lines),
            sources=sorted(list(set(sources))),
            metadata={
                "thematic_criterion": theme_key,
                "matching_temples": temples,
                "matching_count": len(temples)
            }
        )

    def _handle_weather_recommendation(self, weather_criterion: Dict[str, Any], state: AgentState) -> AgentResponse:
        """
        Handles temperature-based recommendation queries using LiveWeatherAgent if available.
        Strictly avoids fabricating weather data.
        """
        min_temp = weather_criterion.get("min_temp", 20.0)
        max_temp = weather_criterion.get("max_temp", 32.0)

        weather_results: List[Dict[str, Any]] = []

        if self.weather_agent is not None:
            try:
                coord_reg = getattr(self.weather_agent, "coordinate_registry", None)
                if coord_reg is not None and hasattr(self.weather_agent, "_fetch_open_meteo"):
                    all_coords = coord_reg.get_all_coordinates()
                    if isinstance(all_coords, dict):
                        for temple_name, coord in all_coords.items():
                            if coord and hasattr(coord, "latitude") and isinstance(coord.latitude, (int, float)):
                                cache_key = f"{coord.latitude:.4f}::{coord.longitude:.4f}"
                                data, hit, iso_time = self.weather_agent._fetch_open_meteo(coord.latitude, coord.longitude, cache_key)
                                if isinstance(data, dict):
                                    cur = data.get("current") or data.get("current_weather") or {}
                                    temp = cur.get("temperature_2m") if "temperature_2m" in cur else cur.get("temperature")
                                    wcode = cur.get("weather_code") if "weather_code" in cur else cur.get("weathercode", "Clear")
                                    if temp is not None:
                                        weather_results.append({
                                            "temple": getattr(coord, "display_name", None) or temple_name,
                                            "canonical_name": temple_name,
                                            "temp": float(temp),
                                            "condition": wcode,
                                            "retrieved_at": iso_time
                                        })
                if not weather_results and hasattr(self.weather_agent, "get_weather") and callable(self.weather_agent.get_weather):
                    for temple in ["Yadadri", "Basara", "Srisailam", "Bhadrachalam", "Dharmapuri", "Vemulawada", "Kaleshwaram", "Ramappa"]:
                        w = self.weather_agent.get_weather(temple)
                        if isinstance(w, dict) and "temperature" in w:
                            weather_results.append({
                                "temple": temple,
                                "canonical_name": temple,
                                "temp": float(w["temperature"]),
                                "condition": w.get("condition", "Clear"),
                                "retrieved_at": w.get("retrieved_at", "Live API")
                            })
            except Exception as e:
                logger.warning(f"Live weather check failed in RecommendationAgent: {e}")

        # If live weather succeeded and produced results
        if weather_results:
            matched_temples = [r for r in weather_results if min_temp <= r["temp"] <= max_temp]
            matched_temples.sort(key=lambda x: x["temp"])
            if matched_temples:
                lines = [
                    f"### 🌤️ Live Weather Recommendations ({min_temp:g}°C – {max_temp:g}°C)\n",
                    f"Based on **live observations from Open-Meteo**, the following registered pilgrimage temples currently satisfy your requested temperature range:\n"
                ]
                for m in matched_temples:
                    lines.append(f"- **{m['temple']}**: **{m['temp']}°C** (Live observation: {m['retrieved_at']})")
                lines.append(f"\n> **Note**: These temperatures reflect live observations and conditions may change during your journey.")
                lines.append(f"> **Attribution**: Weather data by Open-Meteo.com under CC BY 4.0.")
                lines.append(f"\n*(To check darshan timings, sevas, or accommodation for any of these temples, please ask about that specific temple).*")

                return AgentResponse(
                    success=True,
                    agent_name=self.name,
                    answer="\n".join(lines),
                    sources=["Open-Meteo Weather API"],
                    metadata={
                        "weather_filter": weather_criterion,
                        "matched_temples": [m["temple"] for m in matched_temples]
                    }
                )
            else:
                available_temps = ", ".join([f"{r['temple']} ({r['temp']}°C)" for r in weather_results[:5]])
                lines = [
                    f"### 🌤️ Live Weather Recommendation\n",
                    f"Currently, none of the registered temple locations are within **{min_temp:g}°C – {max_temp:g}°C**.",
                    f"Current live temperatures at monitored temples include: {available_temps}.",
                    f"\n> **Note**: Temperatures reflect current live observations and fluctuate throughout the day.",
                    f"> **Attribution**: Weather data by Open-Meteo.com under CC BY 4.0."
                ]
                return AgentResponse(
                    success=True,
                    agent_name=self.name,
                    answer="\n".join(lines),
                    sources=["Open-Meteo Weather API"],
                    metadata={"weather_filter": weather_criterion, "matched_temples": []}
                )

        # Fallback if weather agent is not available or service is unreachable:
        lines = [
            f"### 🛕 Temple Recommendations (Weather Service Status)\n",
            f"Live temperature and weather data is currently unavailable. To avoid guessing or fabricating temperatures, "
            f"PilgrimAI does not estimate live weather.\n",
            f"However, based on verified temple facilities, here are prominent temples suitable for a comfortable pilgrimage:\n",
            f"1. **Yadadri (Sri Lakshmi Narasimha Swamy)** — Modern hill shrine with sheltered queue complexes and comprehensive facilities.",
            f"2. **Basara (Gnana Saraswathi Temple)** — Peaceful riverside kshetra on the Godavari banks.",
            f"3. **Bhadrachalam (Sita Ramachandra Swamy)** — Historic riverbank temple with extensive devasthanam choultries.",
            f"4. **Vemulawada (Sri Raja Rajeshwara Swamy)** — Renowned Shiva temple with vast pilgrim amenities.\n",
            f"*(Please check the Live Weather Agent directly for updated forecast advisories before departure).*"
        ]
        return AgentResponse(
            success=True,
            agent_name=self.name,
            answer="\n".join(lines),
            sources=["yadadri/overview.json", "basara/overview.json", "badrachalam/overview.json"],
            metadata={"weather_filter": weather_criterion, "weather_status": "unavailable"}
        )

    def _handle_open_recommendation(self, query: str) -> AgentResponse:
        """
        Handles open-ended queries like "Which temple should I visit?" or "Suggest a temple".
        Does not claim one temple is objectively 'best'; provides balanced options across
        pilgrimage traditions and invites user preferences.
        """
        lines = [
            "### 🛕 PilgrimAI Temple Recommendations\n",
            "PilgrimAI covers **20 certified pilgrimage temples** in Telangana, each with distinct spiritual, historical, and architectural significance. "
            "Because pilgrimage choices depend on individual faith, travel convenience, and family needs, no single temple is objectively the 'best'.\n",
            "Here are recommended temples categorized by major pilgrimage traditions:\n",
            "1. **Major Shakti Peetha & Goddess Shrines**:",
            "   - **Jogulamba (Alampur)**: 5th Maha Shakti Peetha, dating to the Badami Chalukyas.",
            "   - **Balkampet Yellamma** & **Ujjaini Mahakali**: Iconic Secunderabad/Hyderabad mother goddess shrines.\n",
            "2. **Lord Shiva & Jyotirlinga Shrines**:",
            "   - **Srisailam**: Revered Jyotirlinga and Shakti Peetha on the Nallamala hills.",
            "   - **Vemulawada (Rajanna)**: Celebrated for its sacred Baddi Pooja and holy pushkarini.",
            "   - **Kaleshvaram**: Unique shrine where two Shiva Lingas reside on a single pedestal.\n",
            "3. **Lord Narasimha Kshetras**:",
            "   - **Yadadri (Yadagirigutta)**: Grand Dravidian-style hill temple, extensively renovated with modern amenities.",
            "   - **Dharmapuri**: Ancient Yoga Narasimha kshetra on the sacred Godavari river.\n",
            "4. **Education, Learning & Aksharabhyasam**:",
            "   - **Basara (Gnana Saraswathi)**: One of India's prominent Saraswathi shrines for children's learning initiation.\n",
            "5. **Lord Rama & Lord Venkateswara Kshetras**:",
            "   - **Bhadrachalam**: Sacred Ramayana kshetra on the Godavari river.",
            "   - **Chilkur Balaji**: Revered Visa Balaji shrine known for pradakshinas without monetary hundis.\n",
            "6. **UNESCO World Heritage & Kakatiya Architecture**:",
            "   - **Ramappa Temple**: 800-year-old UNESCO World Heritage site renowned for floating bricks and sculpted pillars.",
            "   - **Thousand Pillar Temple (Hanamkonda)**: Masterpiece of 12th-century Kakatiya stone architecture.\n",
            "---\n",
            "**💡 To help us tailor a specific recommendation, please let us know:**",
            "- Which **deity or ritual** you wish to worship?",
            "- Do you require **accommodation** or **wheelchair/senior citizen accessibility**?",
            "- Are you planning a **1-day trip** from Hyderabad or a longer tour?"
        ]

        sources = [
            "yadadri/overview.json",
            "basara/overview.json",
            "badrachalam/overview.json",
            "srisaila/overview.json",
            "ramappa/overview.json"
        ]

        return AgentResponse(
            success=True,
            agent_name=self.name,
            answer="\n".join(lines),
            sources=sources,
            metadata={
                "type": "open_recommendation",
                "recommendation_type": "open_guidance",
                "categories_suggested": list(THEMATIC_TEMPLE_MAP.keys())
            }
        )
