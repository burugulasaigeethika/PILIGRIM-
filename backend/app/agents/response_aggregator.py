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
        (e.g., disjoint opening hours or contradictory statements).
        """
        if len(responses) < 2:
            return False

        # Extract time assertions (e.g. 4:00 AM vs 5:00 AM)
        times_per_resp = []
        for r in responses:
            found_times = set(re.findall(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", r.answer, re.IGNORECASE))
            times_per_resp.append(found_times)

        populated_times = [t for t in times_per_resp if t]
        if len(populated_times) >= 2:
            for i in range(len(populated_times)):
                for j in range(i + 1, len(populated_times)):
                    if populated_times[i] != populated_times[j]:
                        return True

        # Check explicit conflict markers or differing numeric assertions on same keywords
        for i in range(len(responses)):
            for j in range(i + 1, len(responses)):
                a1, a2 = responses[i].answer.lower(), responses[j].answer.lower()
                if "opens at" in a1 and "opens at" in a2 and a1 != a2:
                    return True
                if "timings are" in a1 and "timings are" in a2 and a1 != a2:
                    return True

        return False

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

        # -------------------------------------------------------------
        # 5. Check Conflicting Information Across Multiple Responses
        # -------------------------------------------------------------
        has_conflict = self._detect_conflict(unique_successful)

        if has_conflict:
            conflict_lines = ["Information from the available agents differs:"]
            for r in unique_successful:
                agent_label = r.agent_name or "Specialist Agent"
                conflict_lines.append(f"- **{agent_label}**: {r.answer.strip()}")
            conflict_lines.append("\nNote: The conflicting information should be verified before relying on it.")
            combined_answer = "\n".join(conflict_lines)
        else:
            # Clean paragraph-based composition
            answer_parts = [r.answer.strip() for r in unique_successful if r.answer.strip()]
            combined_answer = "\n\n".join(answer_parts)

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

        # Propagate child metadata keys if not already present
        for r in unique_successful:
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
