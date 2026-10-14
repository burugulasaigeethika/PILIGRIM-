"""
PilgrimAI - TempleInformationAgent (Phase C)

Specialist agent responsible for answering factual queries about specific temples
(timings, sevas, poojas, history, rules, dress code, facilities, accommodation, transport).
Strictly adheres to:
- BaseAgent lifecycle contract (Phase A).
- RAGTool read-only facade (Phase B).
- Zero direct database / vector index / embedding model imports.
- Strict temple identity resolution and anti-hallucination isolation.
"""

import re
import logging
from typing import Optional, List, Dict, Set, Any

from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState, AgentResponse
from app.agents.tools.rag_tool import RAGTool

logger = logging.getLogger(__name__)


class TempleInformationAgent(BaseAgent):
    """
    Specialist agent providing grounded factual details for individual pilgrimage temples.
    Delegates all retrieval and grounded inference strictly to RAGTool.
    """

    def __init__(
        self,
        rag_tool: Optional[RAGTool] = None,
        name: str = "temple_information",
        description: str = "Answers factual questions about specific temples using verified RAG knowledge."
    ):
        super().__init__(name=name, description=description)
        self.rag_tool = rag_tool or RAGTool()
        self._registered_temples: List[str] = []
        self._temple_aliases: Dict[str, List[str]] = {}
        self._init_temple_registry()

    def _init_temple_registry(self):
        """
        Loads registered temples dynamically from RAGTool and populates aliases.
        Guarantees zero hardcoded independent temple datasets.
        """
        self._registered_temples = self.rag_tool.get_registered_temples()

        # Build alias map anchored on canonical registered temples
        alias_seed: Dict[str, List[str]] = {
            "Ahobilam": ["ahobilam", "ahobila", "narasimha ahobilam"],
            "Badrachalam": ["badrachalam", "bhadrachalam", "bhadragiri", "rama temple bhadrachalam", "lord rama bhadrachalam"],
            "Balkampet": ["balkampet", "yellamma", "balkampet yellamma"],
            "Basara": ["basara", "basar", "gnana saraswathi", "saraswathi temple"],
            "Birla Mandir": ["birla mandir", "birla"],
            "Chilkur": ["chilkur", "visa balaji", "chilkur balaji"],
            "Dharmapuri": ["dharmapuri", "narasimha swamy dharmapuri", "dharmapuri narasimha"],
            "Edupayal": ["edupayal", "edupayala", "edupayala durga", "vanadurga bhavani"],
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
        for canonical in self._registered_temples:
            # Check direct or case-insensitive match from seed
            matched = False
            for k, aliases in alias_seed.items():
                if k.lower() == canonical.lower():
                    self._temple_aliases[canonical] = sorted(list(set(aliases + [canonical.lower()])), key=len, reverse=True)
                    matched = True
                    break
            if not matched:
                self._temple_aliases[canonical] = [canonical.lower()]

    def detect_temple(self, query: str) -> Optional[str]:
        """
        Detects whether the query references a registered canonical temple.
        Uses strict regex word boundaries and multi-word alias prioritization.
        """
        if not query or not query.strip():
            return None

        clean_query = query.strip()

        # Iterate over canonical temples and their aliases
        for canonical, aliases in self._temple_aliases.items():
            for alias in aliases:
                pattern = r"\b" + re.escape(alias) + r"\b"
                if re.search(pattern, clean_query, re.IGNORECASE):
                    return canonical

        return None

    def _detect_unknown_temple(self, query: str) -> Optional[str]:
        """
        Identifies whether the user is asking about a temple that is NOT in the registered dataset.
        Prevents hallucination and random substitutions.
        """
        # 1. Check famous non-registered temples first
        famous_unregistered = [
            "golden temple", "meenakshi", "somnath", "kedarnath", "badrinath",
            "kashi vishwanath", "kashi", "jagannath", "kamakhya", "akshardham", "shirdi",
            "padmanabhaswamy", "murudeshwar", "konark", "brihadeeswarar", "ranganathaswamy",
            "amarnath", "vaishno devi", "tiruchendur", "palani"
        ]
        for name in famous_unregistered:
            if re.search(r"\b" + re.escape(name) + r"\b", query, re.IGNORECASE):
                return name.title()

        # 2. Check pattern "<Name> temple" where Name contains meaningful proper nouns
        pattern = r"\b([A-Za-z]+(?:\s+[A-Za-z]+)?)\s+(temple|mandir|kovil|devasthanam)\b"
        matches = re.finditer(pattern, query, re.IGNORECASE)
        stopwords = {
            "the", "a", "an", "this", "that", "these", "those", "which", "what", "where",
            "who", "how", "why", "when", "are", "is", "was", "were", "be", "been",
            "do", "does", "did", "have", "has", "had", "any", "all", "our", "your",
            "my", "their", "its", "some", "of", "in", "at", "to", "for", "with", "about"
        }
        for match in matches:
            candidate = match.group(1).strip()
            words = [w.lower() for w in candidate.split()]
            meaningful_words = [w for w in words if w not in stopwords]
            if not meaningful_words:
                continue

            cleaned_candidate = " ".join(meaningful_words)
            if not self.detect_temple(cleaned_candidate):
                return f"{cleaned_candidate.title()} {match.group(2).title()}"

        return None

    def _is_temple_related(self, query: str) -> bool:
        """
        Checks if the query touches temple pilgrimage topics.
        """
        indicators = [
            "temple", "mandir", "devasthanam", "timings", "darshan", "seva", "sevas",
            "pooja", "puja", "prasadam", "harathi", "abhishekam", "festival", "festivals",
            "accommodation", "rooms", "history", "dress code", "rules", "dos and don'ts",
            "facilities", "parking", "wheelchair", "location", "reach", "travel", "contact"
        ]
        q_lower = query.lower()
        return any(re.search(r"\b" + re.escape(w) + r"\b", q_lower) for w in indicators)

    def _is_seva_list_query(self, query: str) -> bool:
        """
        Determines if the query is requesting a list or schedule of sevas/rituals.
        """
        if not query or not query.strip():
            return False
        q = query.lower()
        seva_words = bool(re.search(r"\b(sevas?|poojas?|pujas?|rituals?)\b", q))
        if not seva_words:
            return False

        # Exclude specific non-list queries like booking guide, dress code, ticket counter procedures
        if re.search(r"\b(how to book|booking process|booking procedure|dress code|where to buy|online booking portal)\b", q):
            return False

        # Exclude specific single-seva price/timing lookups unless a list is requested
        if re.search(r"\b(cost of|price of|timing of|fee for|ticket for)\b", q) and not re.search(r"\b(all|list|every)\b", q):
            return False

        list_patterns = [
            r"\b(list|all|every|show|tell me|give me|which|available|names of|types of|schedule of)\b",
            r"\bwhat\s+(?:are\s+)?(?:the\s+)?(?:different\s+)?(?:all\s+)?sevas?\b",
            r"\b(?:sevas?|poojas?|pujas?|rituals?)\s+(?:are\s+)?(?:offered|conducted|performed|available)\b",
            r"\b(morning|evening|daily|arjitha|saswatha|regular)\s+(?:sevas?|poojas?|pujas?|rituals?)\b",
            r"\b(?:sevas?|poojas?|pujas?|rituals?)\s+(?:list|details|available|offered|conducted|performed|timings and prices|timings|prices)\b"
        ]
        return any(re.search(pat, q) for pat in list_patterns)

    def _handle_seva_list_query(self, detected_temple: str, query: str) -> AgentResponse:
        """
        Retrieves verified seva dataset records for the temple via RAGTool and formats
        a source-grounded response containing authentic seva names, Telugu titles,
        prices, timings, descriptions, and sub-temple associations without generic placeholders.
        """
        canonical_key = detected_temple
        for t in self._registered_temples:
            if t.lower() == detected_temple.lower():
                canonical_key = t
                break

        canonical_clean = canonical_key.lower().replace(" ", "_")
        try:
            folder = self.rag_tool._rag_service.knowledge_registry.get_temple_folder(canonical_key)
            rel_source = f"{folder.name}/sevas.json" if folder is not None else f"{canonical_clean}/sevas.json"
        except Exception:
            rel_source = f"{canonical_clean}/sevas.json"

        raw_data = self.rag_tool.get_temple_category_data(canonical_key, "sevas")

        if not raw_data or not isinstance(raw_data, list) or len(raw_data) == 0:
            return AgentResponse(
                success=False,
                agent_name=self.name,
                answer=f"No seva records are currently available for {detected_temple} in the verified knowledge base.",
                sources=[rel_source],
                metadata={
                    "temple": detected_temple,
                    "confidence_score": 0.0,
                    "retrieved_chunks": 0,
                    "is_refusal": True,
                    "is_complete_list": True
                }
            )

        q_lower = query.lower() if query else ""
        is_morning_only = bool(re.search(r"\b(morning|prabhata|suprabhata|early\s*morning)\b", q_lower))
        is_evening_only = bool(re.search(r"\b(evening|pradosa|pradosham|night|nishikala)\b", q_lower))

        main_sevas = []
        sub_temple_sevas: Dict[str, List[Dict[str, Any]]] = {}

        for item in raw_data:
            if not isinstance(item, dict):
                continue
            name = item.get("name", "").strip()
            if not name:
                continue

            telugu_name = item.get("telugu_name", "").strip()
            price = str(item.get("price", "")).strip()
            timing = str(item.get("timing", "")).strip()
            desc = str(item.get("description", "")).strip()

            # Check sub-temple association (explicit field or embedded description marker)
            sub_temple = str(item.get("sub_temple", "")).strip()
            if not sub_temple and "SUB" in desc.upper() and "TEMPLE" in desc.upper():
                m_sub = re.search(r"SUB\s*-?\s*TEMPLE\s*[\u2013\u2014\ufffd\-]\s*([^-\n]+)", desc, re.IGNORECASE)
                if m_sub:
                    sub_temple = m_sub.group(1).strip()

            # Clean description by removing redundant internal service-index markers
            clean_desc = desc
            if sub_temple and ("SUB -TEMPLE" in clean_desc.upper() or "SUB-TEMPLE" in clean_desc.upper()):
                clean_desc = re.sub(r"SUB\s*-?\s*TEMPLE\s*[\u2013\u2014\ufffd\-]\s*[^-\n]+(?:\s*-\s*Service\s*\d+)?", "", clean_desc, flags=re.IGNORECASE).strip()
            elif re.search(r"ARJITHA\s*SEVAS\s*-\s*Seva\s*\d+", clean_desc, re.IGNORECASE):
                clean_desc = re.sub(r"ARJITHA\s*SEVAS\s*-\s*Seva\s*\d+", "Arjitha Seva", clean_desc, flags=re.IGNORECASE).strip()
            elif re.search(r"SASWATHA\s*SEVAS\s*-\s*Seva\s*\d+", clean_desc, re.IGNORECASE):
                clean_desc = re.sub(r"SASWATHA\s*SEVAS\s*-\s*Seva\s*\d+", "Saswatha Seva", clean_desc, flags=re.IGNORECASE).strip()
            elif re.search(r"NITYANNADANAM\s*-\s*Seva\s*\d+", clean_desc, re.IGNORECASE):
                clean_desc = re.sub(r"NITYANNADANAM\s*-\s*Seva\s*\d+", "Nityannadanam Scheme", clean_desc, flags=re.IGNORECASE).strip()

            # Clean raw citation URLs and footnote brackets e.g. [[1](https://...)] or [[1]http...]
            if "http" in clean_desc or "[[" in clean_desc:
                clean_desc = re.sub(r":?\s*\[\[?\d+\]?\(?https?://[^\s\])]+\)?\]?", ".", clean_desc).strip()
                clean_desc = re.sub(r"\.\s*\.", ".", clean_desc).strip()
                if clean_desc.endswith(":"):
                    clean_desc = clean_desc[:-1] + "."

            seva_entry = {
                "name": name,
                "telugu_name": telugu_name,
                "price": price,
                "timing": timing,
                "description": clean_desc,
                "sub_temple": sub_temple
            }

            # Time-of-day subset filtering
            if is_morning_only:
                time_text = f"{timing} {desc}".lower()
                is_match = bool(re.search(r"\b(morning|am|prabhata|suprabhata|prathakala|madhyanhika)\b", time_text))
                if not is_match:
                    continue
            elif is_evening_only:
                time_text = f"{timing} {desc}".lower()
                is_match = bool(re.search(r"\b(evening|pm|pradosa|pradosham|nishikala|pavalimpu)\b", time_text))
                if not is_match:
                    continue

            if sub_temple:
                if sub_temple not in sub_temple_sevas:
                    sub_temple_sevas[sub_temple] = []
                sub_temple_sevas[sub_temple].append(seva_entry)
            else:
                main_sevas.append(seva_entry)

        total_matched = len(main_sevas) + sum(len(v) for v in sub_temple_sevas.values())
        if total_matched == 0:
            filter_label = "morning" if is_morning_only else ("evening" if is_evening_only else "")
            msg = f"No specific {filter_label} sevas were identified in the verified records for {detected_temple}." if filter_label else f"No seva records are currently available for {detected_temple} in the verified knowledge base."
            return AgentResponse(
                success=False,
                agent_name=self.name,
                answer=msg,
                sources=[rel_source],
                metadata={
                    "temple": detected_temple,
                    "confidence_score": 0.0,
                    "retrieved_chunks": 0,
                    "is_refusal": True,
                    "is_complete_list": True
                }
            )

        header_label = "Morning Sevas" if is_morning_only else ("Evening Sevas" if is_evening_only else "All Sevas & Rituals")
        lines = [f"Here is the verified list of **{header_label}** at **{detected_temple}** ({total_matched} total):\n"]

        def format_entry(idx: int, s: Dict[str, Any]) -> str:
            entry_lines = []
            tel_str = f" ({s['telugu_name']})" if s["telugu_name"] else ""
            entry_lines.append(f"{idx}. **{s['name']}**{tel_str}")
            details = []
            if s["price"]:
                details.append(f"Price: {s['price']}")
            if s["timing"]:
                details.append(f"Timing: {s['timing']}")
            if s["description"]:
                details.append(f"Details: {s['description']}")
            if details:
                entry_lines.append("   - " + " | ".join(details))
            return "\n".join(entry_lines)

        current_num = 1
        if main_sevas:
            if sub_temple_sevas:
                lines.append("### Main Temple Sevas\n")
            for s in main_sevas:
                lines.append(format_entry(current_num, s) + "\n")
                current_num += 1

        if sub_temple_sevas:
            lines.append("\n### Subsidiary Shrines & Sub-Temples\n")
            for st_name, st_items in sub_temple_sevas.items():
                lines.append(f"#### {st_name}\n")
                for s in st_items:
                    lines.append(format_entry(current_num, s) + "\n")
                    current_num += 1

        formatted_answer = "\n".join(lines)

        return AgentResponse(
            success=True,
            agent_name=self.name,
            answer=formatted_answer,
            sources=[rel_source],
            metadata={
                "temple": detected_temple,
                "confidence_score": 1.0,
                "retrieved_chunks": total_matched,
                "is_refusal": False,
                "is_complete_list": True,
                "plan": {
                    "mode": "complete_category",
                    "category": "sevas",
                    "temple": detected_temple
                }
            }
        )

    def _is_nearby_attractions_query(self, query: str) -> bool:
        """
        Determines if the query is requesting nearby places or attractions around a temple.
        Strictly preserves existing accommodation flow when the user asks for hotels or stays.
        """
        if not query or not query.strip():
            return False
        q = query.lower()

        # 1. Negative guard: preserve existing accommodation, dining, transit, and seva behavior
        if re.search(r"\b(hotel|hotels|room|rooms|stay|stays|accommodation|accomodation|cottage|cottages|choultry|choultries|lodge|lodges|lodging|resort|resorts|guest\s*houses?|dharamsala|dormitory)\b", q):
            return False
        if re.search(r"\b(restaurant|restaurants|food|dining|eatery|eateries|meals?|prasadam|canteen)\b", q):
            return False
        if re.search(r"\b(how\s+to\s+reach|how\s+can\s+i\s+reach|bus\s+stand|railway\s+station|airport|flight|train\s+timings?)\b", q):
            return False
        if re.search(r"\b(sevas?|poojas?|pujas?|rituals?|darshan\s+timings?)\b", q) and not re.search(r"\b(attractions?|places?\s+to\s+visit)\b", q):
            return False

        # 2. Positive indicators for nearby attractions / sightseeing / places to visit
        attraction_patterns = [
            r"\b(?:nearby|near\s+by)\s+(?:places?|attractions?|spots?|destinations?|locations?|sites?|sightseeing|monuments?|temples?)\b",
            r"\bplaces?\s+(?:to\s+visit|to\s+see|to\s+explore|worth\s+visiting)\b",
            r"\bwhat\s+(?:can\s+i|should\s+i|to)\s+(?:visit|see|explore)\s+(?:near|around|close\s+to|in)\b",
            r"\b(?:recommend|suggest|show|tell\s+me|give\s+me|list)\s+(?:(?:some|any|the|all)\s+)?(?:places?|attractions?|spots?|destinations?|sightseeing)\b",
            r"\b(?:attractions?|sightseeing|tourist\s+places?|tourist\s+spots?|sight-seeing)\s+(?:around|near|close\s+to|in\s+and\s+around|of|in)\b",
            r"\bthings\s+to\s+(?:see|visit|do|explore)\s+(?:near|around|close\s+to|in)\b",
            r"\bplaces?\s+(?:near|around|close\s+to)\b",
            r"\bwhat\s+are\s+the\s+nearby\b",
            r"\bwhat\s+else\s+can\s+i\s+visit\b"
        ]
        return any(re.search(pat, q) for pat in attraction_patterns)

    def _handle_nearby_attractions_query(self, detected_temple: str, query: str) -> AgentResponse:
        """
        Retrieves verified nearby_attractions category data for the temple via RAGTool
        and formats a source-grounded response containing authentic attraction names,
        distances (only if present in records), types, and descriptions without placeholders.
        """
        canonical_key = detected_temple
        for t in self._registered_temples:
            if t.lower() == detected_temple.lower():
                canonical_key = t
                break

        canonical_clean = canonical_key.lower().replace(" ", "_")
        try:
            folder = self.rag_tool._rag_service.knowledge_registry.get_temple_folder(canonical_key)
            rel_source = f"{folder.name}/nearby_attractions.json" if folder is not None else f"{canonical_clean}/nearby_attractions.json"
        except Exception:
            rel_source = f"{canonical_clean}/nearby_attractions.json"

        raw_data = self.rag_tool.get_temple_category_data(canonical_key, "nearby_attractions")

        if not raw_data or not isinstance(raw_data, list) or len(raw_data) == 0:
            return AgentResponse(
                success=True,
                agent_name=self.name,
                answer=f"No nearby attraction records are currently available for {detected_temple} in the verified knowledge base.",
                sources=[rel_source],
                metadata={
                    "temple": detected_temple,
                    "confidence_score": 1.0,
                    "retrieved_chunks": 0,
                    "is_refusal": False,
                    "category": "nearby_attractions",
                    "attraction_count": 0
                }
            )

        # Build clean markdown response from authentic records
        lines = [f"## Nearby Attractions — {detected_temple}\n"]
        lines.append(f"Here are the nearby attractions around {detected_temple} from verified records:\n")

        valid_count = 0
        for idx, item in enumerate(raw_data, 1):
            if not isinstance(item, dict):
                continue
            name = item.get("name", "").strip()
            if not name:
                continue

            valid_count += 1
            entry_lines = [f"### {valid_count}. {name}"]
            distance = str(item.get("distance", "")).strip()
            if distance:
                entry_lines.append(f"- **Distance**: {distance}")

            att_type = str(item.get("type", "")).strip()
            if att_type:
                entry_lines.append(f"- **Type**: {att_type}")

            loc = str(item.get("location", "")).strip()
            if loc:
                entry_lines.append(f"- **Location**: {loc}")

            desc = str(item.get("description", "")).strip()
            if desc:
                entry_lines.append(f"- **Description**: {desc}")

            lines.append("\n".join(entry_lines) + "\n")

        formatted_answer = "\n".join(lines).strip()

        return AgentResponse(
            success=True,
            agent_name=self.name,
            answer=formatted_answer,
            sources=[rel_source],
            metadata={
                "temple": detected_temple,
                "confidence_score": 1.0,
                "retrieved_chunks": valid_count,
                "is_refusal": False,
                "category": "nearby_attractions",
                "attraction_count": valid_count
            }
        )

    def _is_accommodation_query(self, query: str) -> bool:
        """
        Determines if the query is requesting accommodation, hotels, lodges,
        rooms, cottages, guest houses, stays, tariffs, or places to stay for a temple.
        Strictly distinguishes from genuine route directions and total trip budget calculations.
        """
        if not query or not query.strip():
            return False
        q = query.lower()

        # 1. Negative guards
        if re.search(r"\b(?:directions?\s+to|directions?\s+from|route\s+from|how\s+to\s+reach|how\s+can\s+i\s+reach|how\s+to\s+get|navigate\s+to)\b", q):
            return False
        if re.search(r"\b(?:weather|forecast|temperature|will\s+it\s+rain|climate)\b", q) and not re.search(r"\b(hotel|hotels|room|rooms|stay|stays|accommodation|accomodation|lodge|lodges|resort|resorts)\b", q):
            return False
        if re.search(r"\b(?:calculate\s+(?:my|the|a)?\s*budget|total\s+budget|pilgrimage\s+budget|trip\s+budget)\b", q):
            return False
        if re.search(r"\b(?:under|within|below)\s+(?:a\s+budget\s+of\s+)?₹?\s*\d+\b", q) and not re.search(r"\b(?:give|show|list|find|what\s+are)\b", q):
            return False

        # 2. Positive accommodation indicators
        accom_patterns = [
            r"\b(?:accommodations?|accomodations?|accommadations?)\b",
            r"\b(?:hotel|hotels|lodge|lodges|lodging|resort|resorts|room|rooms|stay|stays|guest\s*houses?|cottage|cottages|choultrys?|choultries|dharamsalas?|dharamshalas?|dormitory|dormitories)\b",
            r"\bplaces?\s+to\s+stay\b",
            r"\bwhere\s+to\s+stay\b",
            r"\bwhere\s+can\s+i\s+stay\b",
            r"\broom\s+(?:tariffs?|rates?|rents?|prices?|costs?|amounts?|details?)\b",
            r"\bhotel\s+(?:tariffs?|rates?|rents?|prices?|costs?|amounts?|names?|details?)\b"
        ]
        return any(re.search(pat, q) for pat in accom_patterns)

    def _handle_accommodation_query(self, detected_temple: str, query: str) -> AgentResponse:
        """
        Retrieves verified accommodation category data for the temple via RAGTool
        and formats a source-grounded response containing authentic accommodation names,
        types, distances/locations, tariffs/prices, descriptions, and booking contacts.
        Clearly distinguishes verified prices from unquantified/missing tariffs.
        """
        canonical_key = detected_temple
        for t in self._registered_temples:
            if t.lower() == detected_temple.lower():
                canonical_key = t
                break

        canonical_clean = canonical_key.lower().replace(" ", "_")
        try:
            folder = self.rag_tool._rag_service.knowledge_registry.get_temple_folder(canonical_key)
            rel_source = f"{folder.name}/accommodation.json" if folder is not None else f"{canonical_clean}/accommodation.json"
        except Exception:
            rel_source = f"{canonical_clean}/accommodation.json"

        raw_data = self.rag_tool.get_temple_category_data(canonical_key, "accommodation")

        if not raw_data or not isinstance(raw_data, list) or len(raw_data) == 0:
            return AgentResponse(
                success=True,
                agent_name=self.name,
                answer=f"No verified accommodation records are currently available for {detected_temple} in the verified knowledge base.",
                sources=[rel_source],
                metadata={
                    "temple": detected_temple,
                    "confidence_score": 1.0,
                    "retrieved_chunks": 0,
                    "is_refusal": False,
                    "category": "accommodation",
                    "accommodation_count": 0
                }
            )

        # Build clean markdown response from authentic records
        lines = [f"## 🏨 Accommodation Options — {detected_temple}\n"]
        lines.append(f"Here are the verified accommodation options for {detected_temple} from official records:\n")

        # Table header
        lines.append("| Accommodation | Type | Distance / Location | Price / Tariff |")
        lines.append("| :--- | :--- | :--- | :--- |")

        parsed_items = []
        valid_count = 0

        for item in raw_data:
            if not isinstance(item, dict):
                continue
            name = item.get("name", "").strip()
            if not name:
                continue

            valid_count += 1
            prop_type = str(item.get("type", "")).strip() or "Standard Stay"
            
            # Resolve distance / location
            raw_dist = str(item.get("distance", "")).strip()
            raw_loc = str(item.get("location", "")).strip()
            raw_price = str(item.get("price", "") or item.get("tariff", "") or item.get("rate", "") or item.get("cost", "")).strip()

            dist_display = raw_dist or raw_loc
            price_display = ""

            # Check if raw_price is actually a distance string (e.g. "~41.3 km")
            is_dist_in_price = bool(
                re.search(r"^\s*~?\s*\d+(?:\.\d+)?\s*(?:km|kms|meters?|m|miles?)\b", raw_price, re.IGNORECASE)
                and not re.search(r"(?:₹|rs\.?|inr|per\s+night|per\s+day|free)", raw_price, re.IGNORECASE)
            )

            if is_dist_in_price:
                if not dist_display:
                    dist_display = raw_price
                elif raw_price not in dist_display:
                    dist_display = f"{dist_display} ({raw_price})"
                price_display = "Not available in verified records (contact property directly)"
            elif not raw_price:
                price_display = "Not available in verified records (contact property directly)"
            elif raw_price.lower() in ["free", "0", "0.0", "zero"]:
                price_display = "FREE"
            else:
                price_display = raw_price

            if not dist_display:
                dist_display = "Not specified in verified records"

            # Table row (escape pipes if any)
            clean_name_tbl = name.replace("|", "/")
            clean_type_tbl = prop_type.replace("|", "/")
            clean_dist_tbl = dist_display.replace("|", "/")
            clean_price_tbl = price_display.replace("|", "/")
            lines.append(f"| {clean_name_tbl} | {clean_type_tbl} | {clean_dist_tbl} | {clean_price_tbl} |")

            parsed_items.append({
                "name": name,
                "type": prop_type,
                "distance": dist_display,
                "price": price_display,
                "description": str(item.get("description", "")).strip(),
                "contact": str(item.get("contact", "")).strip(),
                "booking_platform": str(item.get("booking_platform", "")).strip(),
                "amenities": item.get("amenities_and_facilities") or item.get("amenities")
            })

        lines.append("")
        lines.append("### Details & Booking Notes\n")

        for idx, it in enumerate(parsed_items, 1):
            detail_lines = [f"#### {idx}. {it['name']}"]
            if it["type"]:
                detail_lines.append(f"- **Type**: {it['type']}")
            if it["distance"]:
                detail_lines.append(f"- **Distance / Location**: {it['distance']}")
            if it["price"]:
                detail_lines.append(f"- **Price / Tariff**: {it['price']}")
            if it["description"]:
                detail_lines.append(f"- **Description / Booking**: {it['description']}")
            if it["contact"]:
                detail_lines.append(f"- **Contact**: {it['contact']}")
            if it["booking_platform"]:
                detail_lines.append(f"- **Booking Platform**: {it['booking_platform']}")
            if it["amenities"]:
                if isinstance(it["amenities"], list):
                    detail_lines.append(f"- **Amenities**: {', '.join(it['amenities'])}")
                else:
                    detail_lines.append(f"- **Amenities**: {it['amenities']}")

            lines.append("\n".join(detail_lines) + "\n")

        formatted_answer = "\n".join(lines).strip()

        return AgentResponse(
            success=True,
            agent_name=self.name,
            answer=formatted_answer,
            sources=[rel_source],
            metadata={
                "temple": detected_temple,
                "confidence_score": 1.0,
                "retrieved_chunks": valid_count,
                "is_refusal": False,
                "category": "accommodation",
                "accommodation_count": valid_count
            }
        )

    def _run(self, state: AgentState) -> AgentResponse:
        """
        Executes temple information retrieval and grounded answering logic.
        Called automatically by BaseAgent.execute(state).
        """
        raw_query = state.user_query.strip()

        # 1. Handle empty / whitespace input
        if not raw_query:
            return AgentResponse(
                success=False,
                agent_name=self.name,
                answer="Please provide a valid temple question.",
                sources=[],
                error="Empty query"
            )

        # 2. Identify target temple
        detected_temple = self.detect_temple(raw_query)

        # 3. Handle unknown / unregistered temples
        if not detected_temple:
            unknown_temple = self._detect_unknown_temple(raw_query)
            if unknown_temple:
                return AgentResponse(
                    success=False,
                    agent_name=self.name,
                    answer=(
                        f"I don't have verified information for '{unknown_temple}' in the current PilgrimAI knowledge base. "
                        f"PilgrimAI currently covers 20 major pilgrimage temples in Telangana (such as Yadadri, Basara, Bhadrachalam, Srisailam, Dharmapuri, etc.)."
                    ),
                    sources=[],
                    metadata={"detected_unknown_temple": unknown_temple},
                    error="Unregistered temple"
                )

            # 4. Handle ambiguous query without a temple mention
            if self._is_temple_related(raw_query):
                return AgentResponse(
                    success=False,
                    agent_name=self.name,
                    answer=(
                        "Which temple would you like information about? "
                        "PilgrimAI currently covers 20 major temples in Telangana (e.g., Yadadri, Basara, Bhadrachalam, Srisailam, Dharmapuri, etc.)."
                    ),
                    sources=[],
                    metadata={"clarification_needed": True},
                    error="Missing temple specification"
                )

            # 5. Handle out-of-scope non-temple queries
            return AgentResponse(
                success=False,
                agent_name=self.name,
                answer="I am the Temple Information Assistant. I can only provide factual information about registered pilgrimage temples in Telangana.",
                sources=[],
                metadata={"out_of_scope": True},
                error="Query outside temple information scope"
            )

        # 6. Intercept complete or time-filtered seva listing queries to ensure source-grounded completeness
        if self._is_seva_list_query(raw_query):
            return self._handle_seva_list_query(detected_temple, raw_query)

        # 6.5. Intercept nearby attractions queries to ensure source-grounded category retrieval across all temples
        if self._is_nearby_attractions_query(raw_query):
            return self._handle_nearby_attractions_query(detected_temple, raw_query)

        # 6.6. Intercept accommodation queries to ensure source-grounded category retrieval across all temples
        if self._is_accommodation_query(raw_query):
            return self._handle_accommodation_query(detected_temple, raw_query)

        # 7. Execute grounded RAG query via RAGTool
        try:
            rag_res = self.rag_tool.execute_grounded_rag(raw_query)
        except Exception as e:
            logger.error(f"RAGTool execution failed in TempleInformationAgent: {e}", exc_info=True)
            return AgentResponse(
                success=False,
                agent_name=self.name,
                answer="An error occurred while retrieving temple details from the knowledge base.",
                sources=[],
                error=str(e),
                metadata={"temple": detected_temple}
            )

        raw_answer = rag_res.get("answer", "")
        raw_sources = rag_res.get("sources", [])
        confidence = rag_res.get("confidence_score", 0.0)
        retrieved_chunks = rag_res.get("retrieved_chunks", 0)

        # 7. Enforce Temple Isolation on returned sources
        # Guarantee that retrieved sources reference the requested temple
        isolated_sources = []
        canonical_clean = detected_temple.lower().replace(" ", "_")
        aliases = self._temple_aliases.get(detected_temple, [detected_temple.lower()])

        for s in raw_sources:
            s_lower = s.lower()
            if canonical_clean in s_lower or detected_temple.lower() in s_lower or any(a in s_lower for a in aliases):
                isolated_sources.append(s)

        # If RAG returned sources but none match the detected temple, suppress bleed
        final_sources = isolated_sources if isolated_sources else (raw_sources if not raw_sources else [])

        # 8. Check refusal or lack of grounded content
        norm_ans = raw_answer.lower()
        is_refusal = (
            confidence < -3.0 or
            "could not find" in norm_ans or
            "not available in the provided" in norm_ans or
            "does not provide" in norm_ans or
            "no information" in norm_ans
        )

        success = not is_refusal if raw_answer else False

        return AgentResponse(
            success=success,
            agent_name=self.name,
            answer=raw_answer,
            sources=final_sources,
            metadata={
                "temple": detected_temple,
                "confidence_score": confidence,
                "retrieved_chunks": retrieved_chunks,
                "is_refusal": is_refusal,
                "is_complete_list": rag_res.get("is_complete_list", False),
                "plan": rag_res.get("plan"),
                "grounding_validation": rag_res.get("grounding_validation", {})
            }
        )
