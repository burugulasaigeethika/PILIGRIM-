"""
PilgrimAI - Deterministic AgentRouter (Phase D)

Analyzes user queries and deterministically routes them to appropriate specialist agents.
Emits the standardized AgentRouteDecision contract from Phase A.

Core Principles:
- 100% Deterministic (rule-based classification, zero LLM / Ollama calls).
- Sub-millisecond latency.
- Explicit intent taxonomy with support for future agent expansion.
- Clear separation between active specialist agents and unimplemented future agents.
- Strict dependency boundary (zero raw database or embedding model imports).
"""

import re
import logging
from typing import Dict, Any, List, Optional, Set

from app.agents.state import AgentRouteDecision
from app.rag.query_planner import query_planner, QueryPlanner

logger = logging.getLogger(__name__)


class AgentRouter:
    """
    Deterministic query router for the PilgrimAI multi-agent assistant.
    Dispatches to specialist agents based on query analysis, intent detection,
    and temple registry validation.
    """

    def __init__(self, planner: Optional[QueryPlanner] = None, active_agents: Optional[Set[str]] = None):
        self.planner = planner or query_planner
        self.active_agents: Set[str] = set(active_agents) if active_agents else {"temple_information"}
        self._init_taxonomies_and_patterns()

    def register_agent(self, agent_name: str) -> None:
        """Dynamically registers an active specialist agent name."""
        self.active_agents.add(agent_name)

    def unregister_agent(self, agent_name: str) -> None:
        """Dynamically unregisters a specialist agent name."""
        self.active_agents.discard(agent_name)

    def _init_taxonomies_and_patterns(self):
        """Initializes regex matchers for intent taxonomy and priority rules."""
        # 1. Comparison Triggers
        self._comparison_patterns = [
            r"\b(compare|comparison|versus|vs\.?|difference\s+between)\b",
            r"\b(which\s+(is\s+)?(better|closer|larger|older))\b"
        ]

        # 2. Itinerary / Tour Planning Triggers
        self._itinerary_patterns = [
            r"\bplan\s+(?:(?:a|an|my|our|the)\s+)?(?:[\w-]+(?:\s+days?)?\s+)?(?:trip|tour|visit|itinerary|journey|travel|pilgrimage)\b",
            r"\b(itinerary\s+(for|to|of)|tour\s+plan|travel\s+itinerary|day\s+trip|weekend\s+trip|pilgrimage\s+itinerary)\b",
            r"\b(how\s+to\s+plan\s+(my\s+)?visit)\b"
        ]

        # 3. Cross-Temple Aggregation Triggers
        self._aggregation_patterns = [
            r"\b(which\s+(all\s+)?temples)\b",
            r"\b(list\s+(all\s+)?temples)\b",
            r"\b(how\s+many\s+temples)\b",
            r"\b(all\s+temples\s+(that|with|without|having|offering|providing|located))\b",
            r"\b(temples\s+(with|without|having|offering|providing|located\s+on))\b"
        ]

        # 4. Famous Non-Registered Temples for Anti-Hallucination Rejection
        self._famous_unregistered = [
            "golden temple", "meenakshi", "somnath", "kedarnath", "badrinath",
            "kashi vishwanath", "kashi", "jagannath", "kamakhya", "akshardham", "shirdi",
            "padmanabhaswamy", "murudeshwar", "konark", "brihadeeswarar", "ranganathaswamy",
            "amarnath", "vaishno devi", "tiruchendur", "palani"
        ]

        # 5. Temple-Related Indicators
        self._temple_indicators = [
            "temple", "temples", "mandir", "devasthanam", "kovil", "timings", "timing",
            "hours", "darshan", "seva", "sevas", "pooja", "poojas", "puja", "prasadam",
            "harathi", "abhishekam", "festival", "festivals", "accommodation", "rooms",
            "cottages", "history", "dress code", "rules", "dos and don'ts", "facilities",
            "parking", "wheelchair", "location", "address", "reach", "travel", "contact"
        ]

        # 6. Distinct Multi-Intent Sub-Categories
        self._sub_intent_patterns: Dict[str, List[str]] = {
            "timings": [r"\b(timings?|hours?|darshan\s+timings?|open|close|when\s+does)\b"],
            "travel": [r"\b(reach|how\s+to\s+reach|how\s+can\s+i\s+reach|transport|bus|train|railway|airport)\b"],
            "sevas": [r"\b(sevas?|poojas?|pujas?|abhishekam|kalyanam|harathi)\b"],
            "facilities": [r"\b(facilities|facility|parking|wheelchair|amenities)\b"],
            "accommodation": [r"\b(accommodation|rooms?|cottages?|stay|guest\s*houses?|choultry)\b"],
            "prasadam": [r"\b(prasadam|food|annadanam|meals?)\b"],
            "history": [r"\b(history|origin|significance|mythology|story)\b"],
            "comparison": [r"\b(compare|comparison|versus|vs\.?)\b"],
            "itinerary": [
                r"\bplan\s+(?:(?:a|an|my|our|the)\s+)?(?:[\w-]+(?:\s+days?)?\s+)?(?:trip|tour|visit|itinerary|journey|travel|pilgrimage)\b",
                r"\b(itinerary\s+(for|to|of)|tour\s+plan|travel\s+itinerary|day\s+trip|weekend\s+trip|pilgrimage\s+itinerary)\b"
            ],
            "weather": [
                r"\b(weather|forecast|temperature|rain|raining|rainfall|climate|humidity|wind)\b",
                r"\b(will\s+it\s+rain|is\s+it\s+raining)\b"
            ],
            "budget": [
                r"\b(budget|costs?|prices?|expenses?|tariff|fees?|ticket\s+rates?)\b",
                r"\b(how\s+much\s+(?:will|does|to|would)?\s*(?:it|a|the|visit|trip|darshan|seva|accommodation|stay)?\s*(?:cost|spend|need|take))\b",
                r"\b(calculate\s+(?:my|the|a)?\s*budget)\b",
                r"\b(?:under|within|below)\s+(?:a\s+budget\s+of\s+)?₹?\s*\d+\b",
                r"\b(?:with\s+(?:a\s+)?budget\s+(?:of\s+)?₹?\s*\d+)\b"
            ],
            "navigation": [
                r"\b(directions?|navigate|navigation|route\s*map|map\s*route)\b",
                r"\b(how\s+far|how\s+long(?:\s+(?:would|will|does|can|might)\s+it\s+take)?)\b",
                r"\b(?:takes?|take\s+to\s+reach)\b",
                r"\b(travel\s+time|driving\s+time|travel\s+duration|driving\s+duration|duration|road\s+distance|driving\s+distance|distance)\b",
                r"\b(route|routes)(?!\s+itinerary)\b",
                r"\b(go\s+from|travel\s+from|drive\s+from|get\s+from|how\s+to\s+get\s+from|how\s+to\s+reach)\b",
                r"\b(eta|estimated\s+arrival|journey)\b"
            ],
            "emergency": [
                r"\b(emergency|emergencies|emergency\s*contacts?|emergency\s*numbers?)\b",
                r"\b(medical\s*help|medical\s*assistance|first\s*aid|ambulance|hospital|hospitals|clinic|clinics)\b",
                r"\b(police|police\s*station|police\s*help|fire\s*station|fire\s*services?)\b",
                r"\b(help\s*desk|helpline|helplines|urgent\s*help|doctor|doctors|trauma)\b"
            ],
            "recommendation": [
                r"\b(recommend|recommendation|recommendations|suggest|suggestion|suggestions)\b",
                r"\b(which\s+temple\s+(?:should|can|to)\s+(?:i|we)\s+visit)\b",
                r"\b(where\s+should\s+(?:i|we)\s+go)\b",
                r"\b(which\s+temple\s+suits?\s+(?:me|us))\b"
            ]
        }

        # 7. Weather Triggers
        self._weather_patterns = [
            r"\b(weather|temperature|temperatures|forecast|rain|raining|rainfall|climate|humidity|wind)\b",
            r"\b(will\s+it\s+rain|is\s+it\s+raining|how\s+(hot|cold|warm)\s+is\s+it)\b",
            r"\b(?:above|below|under|over|around|between)\s*\d+\s*(?:°?c|degrees?|deg)?\b",
            r"\b\d+\s*(?:°?c|degrees?|deg)\b"
        ]

        # 8. Budget Triggers
        self._budget_patterns = [
            r"\b(budget|costs?|prices?|expenses?|tariff|fees?|ticket\s+rates?)\b",
            r"\b(how\s+much\s+(?:will|does|to|would)?\s*(?:it|a|the|visit|trip|darshan|seva|accommodation|stay)?\s*(?:cost|spend|need|take))\b",
            r"\b(calculate\s+(?:my|the|a)?\s*budget)\b",
            r"\b(?:under|within|below)\s+(?:a\s+budget\s+of\s+)?₹?\s*\d+\b",
            r"\b(?:with\s+(?:a\s+)?budget\s+(?:of\s+)?₹?\s*\d+)\b"
        ]

        # 9. Navigation Triggers
        self._navigation_patterns = [
            r"\b(directions?|navigate|navigation|route\s*map|map\s*route)\b",
            r"\b(how\s+far|how\s+long(?:\s+(?:would|will|does|can|might)\s+it\s+take)?)\b",
            r"\b(?:takes?|take\s+to\s+reach)\b",
            r"\b(travel\s+time|driving\s+time|travel\s+duration|driving\s+duration|duration|road\s+distance|driving\s+distance|distance)\b",
            r"\b(route|routes)(?!\s+itinerary)\b",
            r"\b(go\s+from|travel\s+from|drive\s+from|get\s+from|how\s+to\s+get\s+from|how\s+to\s+reach)\b",
            r"\b(eta|estimated\s+arrival|journey)\b"
        ]

        # 10. Voice / Multilingual Triggers
        self._voice_multilingual_patterns = [
            r"\b(?:translate|translation)\b.*?\b(?:to|into|in)\s+(?:telugu|hindi|english)\b",
            r"\b(?:answer|respond|tell\s+me|speak)\s+(?:in|using)\s+(?:telugu|hindi|english)\b",
            r"\bin\s+(?:telugu|hindi)[\s:,]+",
            r"\b(?:voice\s+response|audio\s+response|read\s+(?:it\s+)?aloud|speak\s+out)\b",
            r"\b(?:convert\s+(?:this\s+)?speech|transcribe\s+(?:this\s+)?audio|what\s+did\s+i\s+say)\b",
            r"[\u0C00-\u0C7F]",  # Telugu Unicode block
            r"[\u0900-\u097F]"   # Devanagari / Hindi Unicode block
        ]

        # 11. Emergency Triggers
        self._emergency_patterns = [
            r"\b(emergency|emergencies|emergency\s*contacts?|emergency\s*numbers?|emergency\s*assistance)\b",
            r"\b(medical\s*emergency|medical\s*help|medical\s*assistance|first\s*aid|ambulance)\b",
            r"\b(hospital|hospitals|health\s*centre|clinic|clinics|trauma\s*care|doctor|doctors)\b",
            r"\b(police|police\s*station|police\s*contact|fire\s*station|fire\s*service)\b",
            r"\b(help\s*desk|helpline|helplines|helpline\s*numbers?|urgent\s*help)\b"
        ]

        # 12. Recommendation Triggers
        self._recommendation_patterns = [
            r"\b(recommend|recommendation|recommendations|suggest|suggestion|suggestions)\b",
            r"\b(which\s+temple\s+(?:should|can|to)\s+(?:i|we)\s+visit)\b",
            r"\b(which\s+temple\s+has\s+(?:the\s+)?facilities)\b",
            r"\b(which\s+temples?\s+(?:are\s+good|suitable|best\s+for|has|have))\b",
            r"\b(where\s+should\s+(?:i|we)\s+go)\b",
            r"\b(which\s+temple\s+suits?\s+(?:me|us))\b",
            r"\b(temple\s+recommendation|temple\s+suggestions?)\b"
        ]

    def _detect_temples(self, query: str) -> List[str]:
        """Detects all registered canonical temples mentioned in the query."""
        q_norm = query.lower()
        detected = []
        for canonical_id, aliases in self.planner.temple_aliases.items():
            for alias in sorted(aliases, key=len, reverse=True):
                pattern = r'\b' + re.escape(alias) + r'\b'
                if re.search(pattern, q_norm):
                    detected.append(canonical_id)
                    break
        return detected

    def _detect_unregistered_temple(self, query: str) -> Optional[str]:
        """Detects if an explicit non-registered temple is referenced."""
        q_lower = query.lower()
        for name in self._famous_unregistered:
            if re.search(r"\b" + re.escape(name) + r"\b", q_lower):
                return name.title()

        pattern = r"\b([A-Za-z]+(?:\s+[A-Za-z]+)?)\s+(temple|mandir|kovil|devasthanam)\b"
        stopwords = {
            "the", "a", "an", "this", "that", "these", "those", "which", "what", "where",
            "who", "how", "why", "when", "are", "is", "was", "were", "be", "been",
            "do", "does", "did", "have", "has", "had", "any", "all", "our", "your",
            "my", "their", "its", "some", "of", "in", "at", "to", "for", "with", "about",
            "suggest", "recommend", "visit", "find"
        }
        for match in re.finditer(pattern, query, re.IGNORECASE):
            candidate = match.group(1).strip()
            words = [w.lower() for w in candidate.split()]
            meaningful = [w for w in words if w not in stopwords]
            if not meaningful:
                continue
            cleaned = " ".join(meaningful)
            if not self.planner.detect_temple(cleaned):
                return f"{cleaned.title()} {match.group(2).title()}"

        return None

    def _detect_multi_intent(self, query: str) -> List[str]:
        """
        Detects if query conjoins multiple distinct sub-topics
        (e.g., 'timings and how to reach', or 'itinerary with budget 5000').
        """
        conjunction_match = re.search(r"\b(and|also|as\s+well\s+as|along\s+with|&)\b", query, re.IGNORECASE)
        preposition_multi_intent = (
            re.search(r"\b(?:plan|itinerary|trip|tour)\b.*\b(?:with\s+(?:a\s+)?budget|under\s+(?:a\s+budget\s+of\s+)?₹?\s*\d+)\b", query, re.IGNORECASE) or
            re.search(r"\b(?:with\s+(?:a\s+)?budget|under\s+(?:a\s+budget\s+of\s+)?₹?\s*\d+)\b.*\b(?:plan|itinerary|trip|tour)\b", query, re.IGNORECASE)
        )
        if not conjunction_match and not preposition_multi_intent:
            return []

        matched_sub_intents = []
        for cat_name, patterns in self._sub_intent_patterns.items():
            for pat in patterns:
                if re.search(pat, query, re.IGNORECASE):
                    matched_sub_intents.append(cat_name)
                    break

        return matched_sub_intents if len(matched_sub_intents) >= 2 else []

    def route(self, query: str) -> AgentRouteDecision:
        """
        Main deterministic routing method.
        Evaluates the query through priority rules and returns an AgentRouteDecision.
        """
        # -------------------------------------------------------------
        # Priority 1: Empty / Whitespace Query
        # -------------------------------------------------------------
        if not query or not query.strip():
            return AgentRouteDecision(
                selected_agent="none",
                intent="unsupported",
                confidence=1.0,
                reason="Query is empty or contains only whitespace.",
                metadata={"error": "empty_query"}
            )

        clean_query = query.strip()
        detected_temples = self._detect_temples(clean_query)

        # -------------------------------------------------------------
        # Priority 2: Explicit Unsupported Temple
        # -------------------------------------------------------------
        if not detected_temples:
            unknown_temple = self._detect_unregistered_temple(clean_query)
            if unknown_temple:
                return AgentRouteDecision(
                    selected_agent="none",
                    intent="unsupported",
                    confidence=0.95,
                    reason=f"Explicitly named temple '{unknown_temple}' is not in the registered knowledge base.",
                    metadata={"detected_unknown_temple": unknown_temple, "supported": False}
                )

        # -------------------------------------------------------------
        # Priority 2.5: Voice / Multilingual Intent
        # -------------------------------------------------------------
        is_voice_syntax = any(re.search(p, clean_query, re.IGNORECASE) for p in self._voice_multilingual_patterns)
        if is_voice_syntax:
            is_active = "voice_multilingual" in self.active_agents
            return AgentRouteDecision(
                selected_agent="voice_multilingual" if is_active else "none",
                intent="voice_multilingual",
                confidence=0.95,
                reason=(
                    "Query contains explicit voice, speech, or multilingual language directives."
                    if is_active
                    else "Query matches voice or multilingual intent, but VoiceMultilingualAgent is not active."
                ),
                metadata={
                    "available": is_active,
                    "target_agent": "VoiceMultilingualAgent",
                    "detected_temples": detected_temples
                }
            )

        # -------------------------------------------------------------
        # Priority 2.8: Emergency Intent
        # -------------------------------------------------------------
        is_emergency_syntax = any(re.search(p, clean_query, re.IGNORECASE) for p in self._emergency_patterns)
        if is_emergency_syntax:
            sub_intents = self._detect_multi_intent(clean_query)
            if len(sub_intents) >= 2:
                return AgentRouteDecision(
                    selected_agent="none",
                    intent="multi_intent",
                    confidence=0.90,
                    reason=f"Query contains multiple distinct intents ({', '.join(sub_intents)}). Sequential multi-intent execution will process them in order.",
                    metadata={
                        "available": True,
                        "sub_intents": sub_intents,
                        "detected_temples": detected_temples
                    }
                )

            is_active = "emergency" in self.active_agents
            return AgentRouteDecision(
                selected_agent="emergency" if is_active else "none",
                intent="emergency",
                confidence=0.95,
                reason=(
                    "Query matches emergency, medical, police, or helpline assistance intent."
                    if is_active
                    else "Query matches emergency intent, but EmergencyAgent is not active."
                ),
                metadata={
                    "available": is_active,
                    "target_agent": "EmergencyAgent",
                    "detected_temples": detected_temples
                }
            )

        # -------------------------------------------------------------
        # Priority 3: Live Navigation Intent (Takes precedence over comparison for travel/distance/duration)
        # -------------------------------------------------------------
        is_comparison_syntax = any(re.search(p, clean_query, re.IGNORECASE) for p in self._comparison_patterns)
        is_itinerary_syntax = any(re.search(p, clean_query, re.IGNORECASE) for p in self._itinerary_patterns)
        is_budget_syntax = any(re.search(p, clean_query, re.IGNORECASE) for p in self._budget_patterns)
        is_navigation_syntax = any(re.search(p, clean_query, re.IGNORECASE) for p in self._navigation_patterns)

        # Travel semantics override comparison semantics when travel/distance/duration phrases exist
        if is_navigation_syntax and not is_comparison_syntax and not is_itinerary_syntax:
            sub_intents = self._detect_multi_intent(clean_query)
            if len(sub_intents) >= 2:
                return AgentRouteDecision(
                    selected_agent="none",
                    intent="multi_intent",
                    confidence=0.85,
                    reason=f"Query contains multiple distinct intents ({', '.join(sub_intents)}). Sequential multi-intent execution will process them in order.",
                    metadata={
                        "available": True,
                        "sub_intents": sub_intents,
                        "detected_temples": detected_temples
                    }
                )

            is_active = "live_navigation" in self.active_agents
            return AgentRouteDecision(
                selected_agent="live_navigation" if is_active else "none",
                intent="live_navigation",
                confidence=0.95,
                reason=(
                    f"Query matches live navigation and route intent."
                    if is_active
                    else "Query matches live navigation intent, but LiveNavigationAgent is not active."
                ),
                metadata={
                    "available": is_active,
                    "target_agent": "LiveNavigationAgent",
                    "detected_temples": detected_temples
                }
            )

        # -------------------------------------------------------------
        # Priority 3.5: Comparison Intent
        # -------------------------------------------------------------
        is_weather_syntax = any(re.search(p, clean_query, re.IGNORECASE) for p in self._weather_patterns)
        if (is_comparison_syntax or (len(detected_temples) >= 2 and not is_itinerary_syntax and not is_budget_syntax and not is_navigation_syntax)) and not is_weather_syntax:
            # If query is conjoined with factual sub-intents, route to multi_intent
            sub_intents = self._detect_multi_intent(clean_query)
            non_comp_intents = [si for si in sub_intents if si != "comparison"]
            # Exclude topic attributes (budget, navigation, sevas/accommodation/timings) from forcing multi_intent when comparing
            if is_comparison_syntax and set(non_comp_intents) <= {"budget", "navigation", "travel", "sevas", "accommodation", "prasadam", "timings", "facilities"}:
                non_comp_intents = []
            if len(non_comp_intents) >= 2:
                return AgentRouteDecision(
                    selected_agent="none",
                    intent="multi_intent",
                    confidence=0.85,
                    reason=f"Query contains multiple distinct intents ({', '.join(sub_intents)}).",
                    metadata={
                        "available": True,
                        "sub_intents": sub_intents,
                        "detected_temples": detected_temples
                    }
                )

            is_active = "comparison" in self.active_agents
            return AgentRouteDecision(
                selected_agent="comparison" if is_active else "none",
                intent="comparison",
                confidence=0.95,
                reason="Query matches comparison intent and is routed to ComparisonAgent." if is_active else "Query matches comparison intent, but ComparisonAgent is not yet implemented.",
                metadata={
                    "available": is_active,
                    "target_agent": "ComparisonAgent",
                    "detected_temples": detected_temples
                }
            )

        # -------------------------------------------------------------
        # Priority 3.8: Budget Intent (Evaluated before itinerary so 'budget to plan a trip' routes to budget)
        # -------------------------------------------------------------
        if is_budget_syntax and len(detected_temples) >= 1:
            sub_intents = self._detect_multi_intent(clean_query)
            if len(sub_intents) >= 2:
                return AgentRouteDecision(
                    selected_agent="none",
                    intent="multi_intent",
                    confidence=0.85,
                    reason=f"Query contains multiple distinct intents ({', '.join(sub_intents)}). Sequential multi-intent execution will process them in order.",
                    metadata={
                        "available": True,
                        "sub_intents": sub_intents,
                        "detected_temples": detected_temples
                    }
                )
            is_active = "budget" in self.active_agents
            return AgentRouteDecision(
                selected_agent="budget" if is_active else "none",
                intent="budget",
                confidence=0.95,
                reason=(
                    f"Query contains registered temple(s) ({', '.join(detected_temples)}) and budget calculation intent."
                    if is_active
                    else f"Query matches budget intent for {', '.join(detected_temples)}, but BudgetAgent is not active."
                ),
                metadata={
                    "available": is_active,
                    "target_agent": "BudgetAgent",
                    "detected_temples": detected_temples
                }
            )

        # -------------------------------------------------------------
        # Priority 4: Itinerary Planning Intent
        # -------------------------------------------------------------
        if any(re.search(p, clean_query, re.IGNORECASE) for p in self._itinerary_patterns):
            # If query is conjoined with other distinct sub-intents, route to multi_intent
            sub_intents = self._detect_multi_intent(clean_query)
            if len(sub_intents) >= 2:
                return AgentRouteDecision(
                    selected_agent="none",
                    intent="multi_intent",
                    confidence=0.85,
                    reason=f"Query contains multiple distinct intents ({', '.join(sub_intents)}). Sequential multi-intent execution will process them in order.",
                    metadata={
                        "available": True,
                        "sub_intents": sub_intents,
                        "detected_temples": detected_temples
                    }
                )

            is_active = "itinerary_planning" in self.active_agents
            return AgentRouteDecision(
                selected_agent="itinerary_planning" if is_active else "none",
                intent="itinerary_planning",
                confidence=0.90,
                reason="Query matches itinerary planning intent and is routed to ItineraryPlanningAgent." if is_active else "Query matches itinerary planning intent, but ItineraryPlanningAgent is not yet implemented.",
                metadata={
                    "available": is_active,
                    "target_agent": "ItineraryPlanningAgent",
                    "detected_temples": detected_temples
                }
            )

        # -------------------------------------------------------------
        # Priority 5: Cross-Temple Aggregation Intent
        # -------------------------------------------------------------
        if any(re.search(p, clean_query, re.IGNORECASE) for p in self._aggregation_patterns) and not is_weather_syntax:
            is_active = "cross_temple_aggregation" in self.active_agents
            return AgentRouteDecision(
                selected_agent="cross_temple_aggregation" if is_active else "none",
                intent="cross_temple_aggregation",
                confidence=0.90,
                reason="Query matches cross-temple aggregation intent and is routed to CrossTempleAggregationAgent." if is_active else "Query matches cross-temple aggregation intent, but CrossTempleAggregationAgent is not yet implemented.",
                metadata={
                    "available": is_active,
                    "target_agent": "CrossTempleAggregationAgent"
                }
            )

        # -------------------------------------------------------------
        # Priority 5.5: Recommendation Intent
        # -------------------------------------------------------------
        if any(re.search(p, clean_query, re.IGNORECASE) for p in self._recommendation_patterns):
            # If query is conjoined with other distinct sub-intents, route to multi_intent
            sub_intents = self._detect_multi_intent(clean_query)
            if len(sub_intents) >= 2:
                return AgentRouteDecision(
                    selected_agent="none",
                    intent="multi_intent",
                    confidence=0.85,
                    reason=f"Query contains multiple distinct intents ({', '.join(sub_intents)}). Sequential multi-intent execution will process them in order.",
                    metadata={
                        "available": True,
                        "sub_intents": sub_intents,
                        "detected_temples": detected_temples
                    }
                )

            is_active = "recommendation" in self.active_agents
            return AgentRouteDecision(
                selected_agent="recommendation" if is_active else "none",
                intent="recommendation",
                confidence=0.90,
                reason=(
                    "Query matches temple recommendation intent and is routed to RecommendationAgent."
                    if is_active
                    else "Query matches recommendation intent, but RecommendationAgent is not active."
                ),
                metadata={
                    "available": is_active,
                    "target_agent": "RecommendationAgent",
                    "detected_temples": detected_temples
                }
            )

        # -------------------------------------------------------------
        # Priority 6: Multi-Intent Query
        # -------------------------------------------------------------
        sub_intents = self._detect_multi_intent(clean_query)
        if sub_intents:
            return AgentRouteDecision(
                selected_agent="none",
                intent="multi_intent",
                confidence=0.85,
                reason=f"Query contains multiple distinct intents ({', '.join(sub_intents)}). Sequential multi-intent execution will process them in order.",
                metadata={
                    "available": True,
                    "sub_intents": sub_intents,
                    "detected_temples": detected_temples
                }
            )

        # -------------------------------------------------------------
        # Priority 6.5: Live Weather Intent
        # -------------------------------------------------------------
        if is_weather_syntax:
            has_cross_temple_weather = (
                "which temple" in clean_query.lower() or
                "which temples" in clean_query.lower() or
                "any temple" in clean_query.lower() or
                bool(re.search(r'(?:above|below|over|under|greater than|less than|around|between)\s+\d+', clean_query, re.IGNORECASE))
            )
            if detected_temples or has_cross_temple_weather:
                is_active = "live_weather" in self.active_agents
                temple_name = ", ".join(detected_temples) if detected_temples else "all registered temples"
                return AgentRouteDecision(
                    selected_agent="live_weather" if is_active else "none",
                    intent="weather",
                    confidence=0.95,
                    reason=(
                        f"Query matches live weather or temperature observation intent for {temple_name}."
                        if is_active
                        else f"Query matches live weather intent, but LiveWeatherAgent is not active."
                    ),
                    metadata={
                        "available": is_active,
                        "target_agent": "LiveWeatherAgent",
                        "detected_temple": detected_temples[0] if detected_temples else None,
                        "detected_temples": detected_temples
                    }
                )
            elif "temple" in clean_query.lower() or "temples" in clean_query.lower():
                return AgentRouteDecision(
                    selected_agent="none",
                    intent="clarification",
                    confidence=0.85,
                    reason="Temple-related query does not identify a specific supported temple.",
                    metadata={"clarification_needed": True, "missing_temple": True}
                )
            else:
                return AgentRouteDecision(
                    selected_agent="none",
                    intent="unsupported",
                    confidence=0.95,
                    reason="Query is outside the scope of pilgrimage temple assistance.",
                    metadata={"out_of_scope": True}
                )

        # -------------------------------------------------------------
        # Priority 6.6: Budget Intent
        # -------------------------------------------------------------
        if is_budget_syntax and len(detected_temples) >= 1:
            is_active = "budget" in self.active_agents
            return AgentRouteDecision(
                selected_agent="budget" if is_active else "none",
                intent="budget",
                confidence=0.95,
                reason=(
                    f"Query contains registered temple(s) ({', '.join(detected_temples)}) and budget calculation intent."
                    if is_active
                    else f"Query matches budget intent for {', '.join(detected_temples)}, but BudgetAgent is not active."
                ),
                metadata={
                    "available": is_active,
                    "target_agent": "BudgetAgent",
                    "detected_temples": detected_temples
                }
            )

        # -------------------------------------------------------------
        # Priority 6.7: Live Navigation Intent
        # -------------------------------------------------------------
        if is_navigation_syntax:
            is_active = "live_navigation" in self.active_agents
            return AgentRouteDecision(
                selected_agent="live_navigation" if is_active else "none",
                intent="live_navigation",
                confidence=0.95,
                reason=(
                    f"Query matches live navigation and route intent."
                    if is_active
                    else "Query matches live navigation intent, but LiveNavigationAgent is not active."
                ),
                metadata={
                    "available": is_active,
                    "target_agent": "LiveNavigationAgent",
                    "detected_temples": detected_temples
                }
            )

        # -------------------------------------------------------------
        # Priority 7: Single Known-Temple Factual Information (Active Agent)
        # -------------------------------------------------------------
        if len(detected_temples) == 1:
            temple_name = detected_temples[0]
            return AgentRouteDecision(
                selected_agent="temple_information",
                intent="temple_information",
                confidence=0.95,
                reason=f"Query contains registered temple '{temple_name}' and factual temple information intent.",
                metadata={
                    "available": True,
                    "target_agent": "TempleInformationAgent",
                    "detected_temple": temple_name
                }
            )

        # -------------------------------------------------------------
        # Priority 8: Ambiguous Temple Query (Missing Temple Name)
        # -------------------------------------------------------------
        q_lower = clean_query.lower()
        if any(re.search(r"\b" + re.escape(w) + r"\b", q_lower) for w in self._temple_indicators):
            return AgentRouteDecision(
                selected_agent="none",
                intent="clarification",
                confidence=0.85,
                reason="Temple-related query does not identify a specific supported temple.",
                metadata={"clarification_needed": True, "missing_temple": True}
            )

        # -------------------------------------------------------------
        # Priority 9: Unsupported / Out-of-Scope Query
        # -------------------------------------------------------------
        return AgentRouteDecision(
            selected_agent="none",
            intent="unsupported",
            confidence=0.95,
            reason="Query is outside the scope of pilgrimage temple assistance.",
            metadata={"out_of_scope": True}
        )
