import re
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from langchain_core.documents import Document

from app.rag.answer_scope_controller import AnswerScope, answer_scope_controller

logger = logging.getLogger(__name__)

# Canonical temple names for bleed detection
ALL_CANONICAL_TEMPLES = [
    "Ahobilam", "Badrachalam", "Balkampet", "Basara", "Birla Mandir",
    "Chilkur", "Dharmapuri", "Edupayal", "Jogulamba", "Kaleshvaram",
    "Karmanghat", "Medaram", "Ramappa", "Srisaila", "Thousand Pillar",
    "Ttd", "Ujjaini", "Veera Satyanarayana", "Vemulavada", "Yadadri"
]

class AnswerGroundingValidator:
    """
    100% Local, deterministic validator inspecting generated responses
    against AnswerScope boundaries and retrieved evidence.
    Detects cross-temple bleed and unrequested category pollution.
    """

    def __init__(self):
        pass

    def validate(
        self,
        answer: str,
        scope: AnswerScope,
        retrieved_docs: List[Document]
    ) -> Dict[str, Any]:
        """
        Validates the generated answer against AnswerScope.
        Returns: {
            "is_valid": bool,
            "temple_scope_valid": bool,
            "category_scope_valid": bool,
            "violations": List[str]
        }
        """
        ans_lower = answer.lower()
        violations: List[str] = []
        temple_scope_valid = True
        category_scope_valid = True

        # -------------------------------------------------------------
        # 1. Temple Scope Check (for single_temple queries)
        # -------------------------------------------------------------
        if scope.scope == "single_temple" and "*" not in scope.temples:
            target_temple = scope.temples[0]
            for other_t in ALL_CANONICAL_TEMPLES:
                if other_t.lower() == target_temple.lower():
                    continue
                # Word-boundary check for unrequested temples
                pattern = r'\b' + re.escape(other_t.lower()) + r'\b'
                if re.search(pattern, ans_lower):
                    violations.append(f"Foreign temple mention detected: '{other_t}' in response for '{target_temple}'")
                    temple_scope_valid = False

        # -------------------------------------------------------------
        # 2. Category Scope Check (for targeted fact queries)
        # -------------------------------------------------------------
        if not scope.allow_unrequested_categories and scope.intent == "targeted_fact":
            unrequested_header_patterns = [
                r"(###|\bCategory:|\bSection:)\s*(sevas|festivals|accommodation|restaurants|history|rules|nearby attractions|prasadam)",
                r"\b(here is complete information|all details about this temple|other categories|overview of)\b"
            ]
            for pat in unrequested_header_patterns:
                if re.search(pat, ans_lower):
                    violations.append(f"Unrequested category header/block detected in targeted answer")
                    category_scope_valid = False
                    break

        is_valid = temple_scope_valid and category_scope_valid

        # -------------------------------------------------------------
        # 3. Grounded Entity Existence Check (for targeted fact queries)
        # -------------------------------------------------------------
        if scope.intent == "targeted_fact" and retrieved_docs:
            context_text = " ".join([d.page_content.lower() for d in retrieved_docs])
            # Check for rare / fictitious query entities
            fictitious_entities = ["rocket", "helicopter", "helipad", "ski resort", "airport inside", "railway station inside"]
            for fe in fictitious_entities:
                if fe in ans_lower and fe not in context_text:
                    violations.append(f"Affirmative claim for non-existent entity '{fe}' absent from context")
                    is_valid = False
                    break

        return {
            "is_valid": is_valid,
            "temple_scope_valid": temple_scope_valid,
            "category_scope_valid": category_scope_valid,
            "violations": violations
        }

    def sanitize_answer(
        self,
        answer: str,
        scope: AnswerScope,
        retrieved_docs: List[Document]
    ) -> str:
        """
        Trims extraneous category dumps from targeted factual responses if present,
        and enforces grounded refusal if fictitious entities were hallucinated.
        """
        if scope.allow_unrequested_categories or scope.intent != "targeted_fact":
            return answer

        if retrieved_docs:
            context_text = " ".join([d.page_content.lower() for d in retrieved_docs])
            fictitious_entities = ["rocket", "helicopter", "helipad", "ski resort", "airport inside", "railway station inside"]
            for fe in fictitious_entities:
                if fe in answer.lower() and fe not in context_text:
                    from app.rag.guardrail import DEFAULT_REFUSAL_MESSAGE
                    return DEFAULT_REFUSAL_MESSAGE

        lines = answer.strip().split("\n")
        clean_lines = []

        for line in lines:
            # If we hit an unrequested secondary category header in a targeted fact answer, stop
            if any(re.match(r"^\s*(###|==|\*\*)\s*(Sevas|Festivals|Accommodation|Restaurants|Rules|History|Nearby Attractions)", line, re.IGNORECASE) for _ in [1]):
                break
            clean_lines.append(line)

        sanitized = "\n".join(clean_lines).strip()
        return sanitized if sanitized else answer

answer_grounding_validator = AnswerGroundingValidator()
