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
            "Ujjaini": ["ujjaini", "ujjaini mahakali", "mahakali secunderabad", "secunderabad mahakali"],
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

        # 6. Execute grounded RAG query via RAGTool
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
