import logging
from typing import Dict, Any, List, Optional, Set
from langchain_core.documents import Document

from app.rag.completeness_validator import completeness_validator, CompletenessValidator

logger = logging.getLogger(__name__)

# Priority order of categories for broad temple overview
BROAD_CATEGORY_PRIORITY = [
    "temple",
    "timings",
    "sevas",
    "festivals",
    "facilities",
    "travel",
    "accommodation",
    "restaurants",
    "prasadam",
    "river_bank",
    "wheelchair",
    "rules",
    "contacts",
    "emergency_contacts",
    "nearby_attractions",
    "sub_temples",
    "crowd",
    "donations"
]

class ContextBuilder:
    """
    Constructs deduplicated, structured, and budget-aware context for local LLM generation.
    Supports all 5 retrieval modes:
    - targeted
    - complete_category
    - cross_temple_aggregation
    - multi_category
    - broad_temple
    """

    def __init__(self, validator: Optional[CompletenessValidator] = None):
        self.validator = validator or completeness_validator

    def build_targeted_context(self, docs: List[Document]) -> str:
        """
        Builds deduplicated context for targeted Top-3 RAG queries.
        Preserves source metadata and parent context.
        """
        if not docs:
            return ""

        seen_texts: Set[str] = set()
        context_parts = []

        for doc in docs:
            text = doc.page_content.strip()
            if text and text not in seen_texts:
                seen_texts.add(text)
                temple = doc.metadata.get("temple", "")
                cat = doc.metadata.get("category", "")
                source = doc.metadata.get("path") or doc.metadata.get("source_file", "")

                header_meta = []
                if temple:
                    header_meta.append(f"[TEMPLE] {temple}")
                if cat:
                    header_meta.append(f"[CATEGORY] {cat.upper()}")
                if source:
                    header_meta.append(f"[SOURCE] {source}")

                header_str = " | ".join(header_meta)
                if header_str:
                    context_parts.append(f"{header_str}\n\n{text}")
                else:
                    context_parts.append(text)

        return "\n\n---\n\n".join(context_parts)

    def build_complete_category_context(
        self,
        temple: str,
        category: str,
        full_parent_text: str,
        source_path: str = "",
        item_count: Optional[int] = None
    ) -> str:
        """
        Builds structured context for a complete single-temple category retrieval.
        """
        completeness_str = f"{item_count} verified items" if item_count is not None else "Complete Verified Category"
        
        lines = [
            f"[TEMPLE]\n{temple}\n",
            f"[CATEGORY]\n{category.upper()}\n",
            f"[SOURCE]\n{source_path or f'{temple.lower()}/{category}.json'}\n",
            f"[COMPLETENESS]\n{completeness_str}\n",
            f"[CONTENT]\n{full_parent_text}"
        ]
        return "\n".join(lines)

    def build_cross_temple_context(
        self,
        validation_result: Dict[str, Any],
        query: str = ""
    ) -> str:
        """
        Builds a deterministic, source-grounded natural language answer for cross-temple aggregation.
        Explicitly distinguishes Confirmed Available, Confirmed Unavailable, and Missing Data.
        """
        cat_raw = validation_result.get("category") or validation_result.get("property_key") or "Information"
        category_name = str(cat_raw).replace("_", " ").title()
        condition = validation_result.get("condition", "positive")
        confirmed_avail = validation_result.get("confirmed_available", [])
        confirmed_unavail = validation_result.get("confirmed_unavailable", [])
        info_not_avail = validation_result.get("information_not_available", [])
        matches = validation_result.get("matches", confirmed_avail if condition != "negative" else confirmed_unavail)

        lines = []

        if condition == "negative":
            # Negative aggregation (e.g. temples that don't have wheelchair facilities)
            count = len(matches)
            if count == 0:
                lines.append(f"I could not find any temples with confirmed absence of {category_name.lower()} in the available temple knowledge base.")
            else:
                lines.append(f"Based on verified temple knowledge base records, the following **{count} temples** are confirmed to **NOT have {category_name}** (or have major documented architectural/physical limitations):\n")
                for idx, item in enumerate(matches, 1):
                    t_name = item["temple"]
                    evidence = item.get("evidence", "Explicitly documented as unavailable")
                    lines.append(f"{idx}. **{t_name}** — {evidence}")

            # Note unrecorded temples if any exist
            if info_not_avail:
                lines.append(f"\n*(Note: {len(info_not_avail)} temples have no specific {category_name.lower()} records documented in the current knowledge base).*")

        else:
            # Positive aggregation (e.g. temples that have river bank / accommodation)
            count = len(matches)
            if count == 0:
                lines.append(f"I could not find any temples with confirmed {category_name.lower()} information in the available temple knowledge base.")
            else:
                lines.append(f"Based on the temple knowledge base, the following **{count} temples** have confirmed **{category_name}** information:\n")
                for idx, item in enumerate(matches, 1):
                    t_name = item["temple"]
                    evidence = item.get("evidence", "Available")
                    lines.append(f"{idx}. **{t_name}** — {evidence}")

        return "\n".join(lines)

    def build_multi_category_context(
        self,
        temple: str,
        category_docs: Dict[str, List[Document]]
    ) -> str:
        """
        Builds balanced, structured multi-category context ensuring each requested category is represented.
        """
        sections = [f"[TEMPLE] {temple}\n"]

        for cat_key, docs in category_docs.items():
            cat_display = cat_key.replace("_", " ").title()
            cat_texts = []
            sources = set()

            for doc in docs:
                cat_texts.append(doc.page_content.strip())
                src = doc.metadata.get("path") or doc.metadata.get("source_file")
                if src:
                    sources.add(src)

            src_str = ", ".join(sorted(list(sources))) if sources else f"{temple.lower()}/{cat_key}.json"
            content_str = "\n\n".join(cat_texts) if cat_texts else "No specific records found for this category."

            sections.append(
                f"=== CATEGORY: {cat_display.upper()} ===\n"
                f"[SOURCE] {src_str}\n"
                f"[CONTENT]\n"
                f"{content_str}\n"
            )

        return "\n\n---\n\n".join(sections)

    def build_broad_temple_context(
        self,
        temple: str,
        category_texts: Dict[str, str],
        max_categories: int = 8
    ) -> str:
        """
        Builds a controlled, prioritized broad overview context for a single temple.
        """
        sections = [f"[TEMPLE] {temple}\n[OVERVIEW] Comprehensive Knowledge Base Summary\n"]
        included_count = 0

        # Iterate in defined priority order
        for cat_key in BROAD_CATEGORY_PRIORITY:
            if cat_key in category_texts and category_texts[cat_key].strip():
                if included_count >= max_categories:
                    break

                cat_display = cat_key.replace("_", " ").title()
                content = category_texts[cat_key].strip()
                
                # Truncate section if unusually long to maintain balance
                if len(content) > 1200:
                    content = content[:1200] + "\n...(summary continued)"

                sections.append(
                    f"### {cat_display}\n"
                    f"{content}\n"
                )
                included_count += 1

        return "\n\n".join(sections)

context_builder = ContextBuilder()
