"""
PilgrimAI - ResponseAggregator (Phase E)

Composes one or more already-produced AgentResponse objects into a single, clean,
unified AgentResponse without inventing or hallucinating facts.

Core Principles:
- 100% Deterministic (pure in-memory composition, zero LLM calls).
- Zero database dependencies (no vector store or retrieval imports).
- Preserves factual integrity (never fills gaps, never rewrites facts).
- Conflict transparency (preserves conflicting information from different agents without picking a winner).
- Clean source and metadata deduplication and preservation.
"""

import re
import html
import time
import logging
from typing import List, Dict, Any, Set, Optional

from app.agents.state import AgentResponse

logger = logging.getLogger(__name__)


class ResponseAggregator:
    """
    Pure composition layer combining already-produced AgentResponse objects
    into a cohesive, standardized AgentResponse.
    """

    def __init__(self):
        pass

    def _detect_conflict(self, responses: List[AgentResponse]) -> bool:
        """
        Determines whether multiple responses contain conflicting assertions
        (e.g., contradictory opening hours on the exact same temple query).
        """
        if len(responses) < 2:
            return False

        # Check explicit conflict markers or differing opening/closing assertions on same keywords
        for i in range(len(responses)):
            for j in range(i + 1, len(responses)):
                a1, a2 = responses[i].answer.lower(), responses[j].answer.lower()
                m1 = re.findall(r"\b(?:opens\s+(?:daily\s+)?at|timings\s+are)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b", a1)
                m2 = re.findall(r"\b(?:opens\s+(?:daily\s+)?at|timings\s+are)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b", a2)
                if m1 and m2 and set(m1) != set(m2):
                    return True
                if "opens at" in a1 and "opens at" in a2 and a1 != a2:
                    return True
                if "timings are" in a1 and "timings are" in a2 and a1 != a2:
                    return True

        return False

    def _synthesize_itinerary_and_budget(
        self,
        itinerary_resp: AgentResponse,
        budget_resp: AgentResponse
    ) -> str:
        """
        Combines ItineraryPlanningAgent and BudgetAgent responses into a cohesive,
        well-structured response following Requirement 4 without repetition or internal debug output.
        """
        it_lines = []
        disclaimer_line = None
        has_bg_accom = (
            "recommended accommodation" in budget_resp.answer.lower()
            or "recommended stay" in budget_resp.answer.lower()
            or "accommodation comparison" in budget_resp.answer.lower()
        )

        skip_accom_catalog = False
        for line in itinerary_resp.answer.strip().split("\n"):
            if line.startswith("*(Data Sources & Scope:") or line.startswith("*(Live-Data Limitation:"):
                disclaimer_line = line
            elif line.strip().startswith("**Sources:**"):
                break
            elif has_bg_accom and (
                (line.startswith("### ") or line.startswith("## "))
                and any(k in line.lower() for k in ["accommodation", "lodging", "stay plan", "stay options"])
            ):
                skip_accom_catalog = True
                continue
            elif skip_accom_catalog and line.startswith("### ") and not any(k in line.lower() for k in ["accommodation", "lodging", "stay"]):
                skip_accom_catalog = False
                it_lines.append(line)
            elif not skip_accom_catalog:
                it_lines.append(line)
        it_clean = "\n".join(it_lines).strip()

        # Extract budget-relevant sections from budget answer
        bg_sections = []
        keep_bg_sec = False
        for line in budget_resp.answer.strip().split("\n"):
            if line.startswith("### ") or line.startswith("## "):
                h_low = line.lower()
                if any(ex in h_low for ex in ["travel & journey routes", "notes", "sources", "trip overview"]):
                    keep_bg_sec = False
                else:
                    keep_bg_sec = True
                    bg_sections.append(line)
            elif keep_bg_sec:
                bg_sections.append(line)

        bg_clean = "\n".join(bg_sections).strip()
        if bg_clean and not bg_clean.startswith("## "):
            bg_clean = "## 💰 Budget Estimation & Cost Breakdown\n\n" + bg_clean

        doc_parts = [it_clean]
        if bg_clean:
            doc_parts.append(bg_clean)
        if disclaimer_line:
            doc_parts.append(disclaimer_line)

        return "\n\n".join(doc_parts).strip()

    def aggregate(self, responses: List[AgentResponse]) -> AgentResponse:
        """
        Main composition method. Aggregates a list of AgentResponse objects
        into a single unified AgentResponse.
        """
        t0 = time.perf_counter()

        # -------------------------------------------------------------
        # 1. Handle Empty Input List
        # -------------------------------------------------------------
        if not responses:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            return AgentResponse(
                success=False,
                agent_name="response_aggregator",
                answer="",
                sources=[],
                error="No agent responses provided for aggregation.",
                metadata={"agent_count": 0, "aggregation_latency_ms": latency_ms},
                latency_ms=latency_ms
            )

        successful: List[AgentResponse] = [r for r in responses if r.success]
        failed: List[AgentResponse] = [r for r in responses if not r.success]

        # -------------------------------------------------------------
        # 2. All Responses Failed
        # -------------------------------------------------------------
        if not successful:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            error_details = [
                f"{r.agent_name or 'unknown_agent'}: {r.error or 'Failed without specific error message'}"
                for r in failed
            ]
            combined_error = "; ".join(error_details)
            # Check if any specialist produced a user-facing explanation or clarification in answer
            fallback_answer = next((r.answer.strip() for r in failed if r.answer and r.answer.strip()), "")
            fallback_sources = []
            for r in failed:
                fallback_sources.extend(r.sources)

            return AgentResponse(
                success=False,
                agent_name="response_aggregator",
                answer=fallback_answer,
                sources=fallback_sources,
                error=f"All specialist agents failed: {combined_error}",
                metadata={
                    "agent_count": len(responses),
                    "failed_agents": [r.agent_name for r in failed],
                    "aggregation_latency_ms": latency_ms
                },
                latency_ms=latency_ms
            )

        # -------------------------------------------------------------
        # 3. Deduplicate Identical Successful Responses
        # -------------------------------------------------------------
        unique_successful: List[AgentResponse] = []
        seen_signatures: Set[str] = set()

        for r in successful:
            norm_answer = r.answer.strip()
            sig = f"{r.agent_name}::{norm_answer}"
            if sig not in seen_signatures:
                seen_signatures.add(sig)
                unique_successful.append(r)

        # If after deduplication only 1 answer remains and no failures occurred, preserve it directly
        if len(unique_successful) == 1 and not failed:
            single = unique_successful[0]
            latency_ms = (time.perf_counter() - t0) * 1000.0
            merged_meta = dict(single.metadata)
            merged_meta["aggregation_latency_ms"] = latency_ms
            merged_meta["agent_count"] = len(responses)
            return AgentResponse(
                success=True,
                agent_name=single.agent_name or "response_aggregator",
                answer=single.answer,
                sources=list(single.sources),
                metadata=merged_meta,
                latency_ms=single.latency_ms
            )

        # -------------------------------------------------------------
        # 4. Merge Sources (Preserve Order, Remove Duplicates)
        # -------------------------------------------------------------
        merged_sources: List[str] = []
        seen_sources: Set[str] = set()

        for r in responses:
            for src in r.sources:
                if src and src not in seen_sources:
                    seen_sources.add(src)
                    merged_sources.append(src)

        # Order responses logically by domain hierarchy:
        # Overview/Temple Info -> Itinerary -> Weather -> Budget -> Navigation -> Emergency -> Other
        AGENT_ORDER = {
            "temple_information": 10,
            "recommendation": 15,
            "itinerary_planning": 20,
            "live_weather": 30,
            "budget": 40,
            "live_navigation": 50,
            "emergency": 60,
            "voice_multilingual": 70,
        }
        ordered_successful = sorted(
            unique_successful,
            key=lambda r: AGENT_ORDER.get(r.agent_name, 100)
        )

        # -------------------------------------------------------------
        # 5. Check Conflicting Information Across Multiple Responses
        # -------------------------------------------------------------
        has_conflict = self._detect_conflict(unique_successful)

        if has_conflict:
            conflict_lines = ["Information from the available agents differs:"]
            for r in ordered_successful:
                agent_label = r.agent_name or "Specialist Agent"
                conflict_lines.append(f"- **{agent_label}**: {r.answer.strip()}")
            conflict_lines.append("\nNote: The conflicting information should be verified before relying on it.")
            combined_answer = "\n".join(conflict_lines)
        else:
            it_resp = next((r for r in ordered_successful if r.agent_name == "itinerary_planning"), None)
            bg_resp = next((r for r in ordered_successful if r.agent_name == "budget"), None)

            if it_resp and bg_resp:
                synthesized = self._synthesize_itinerary_and_budget(it_resp, bg_resp)
                other_responses = [r for r in ordered_successful if r.agent_name not in ("itinerary_planning", "budget")]
                if other_responses:
                    combined_answer = synthesized + "\n\n---\n\n" + "\n\n---\n\n".join(r.answer.strip() for r in other_responses if r.answer.strip())
                else:
                    combined_answer = synthesized
            else:
                answer_parts = [r.answer.strip() for r in ordered_successful if r.answer.strip()]
                combined_answer = "\n\n---\n\n".join(answer_parts) if len(answer_parts) > 1 else (answer_parts[0] if answer_parts else "")

        combined_answer = html.unescape(combined_answer)

        # -------------------------------------------------------------
        # 6. Merge Metadata
        # -------------------------------------------------------------
        latency_ms = (time.perf_counter() - t0) * 1000.0

        merged_metadata: Dict[str, Any] = {
            "agent_count": len(responses),
            "agents": [r.agent_name for r in responses if r.agent_name],
            "successful_agents": [r.agent_name for r in unique_successful if r.agent_name],
            "failed_agents": [r.agent_name for r in failed if r.agent_name],
            "has_conflict": has_conflict,
            "aggregation_latency_ms": latency_ms
        }

        if failed:
            merged_metadata["partial_failure"] = True
            merged_metadata["failure_errors"] = [r.error for r in failed if r.error]

        # Propagate child metadata keys if not already present, respecting ordered_successful
        for r in ordered_successful:
            for k, v in r.metadata.items():
                if k not in merged_metadata:
                    merged_metadata[k] = v

        return AgentResponse(
            success=True,
            agent_name="response_aggregator",
            answer=combined_answer,
            sources=merged_sources,
            metadata=merged_metadata,
            error=None if not failed else f"Partial completion: {len(failed)} agent(s) failed.",
            latency_ms=latency_ms
        )
