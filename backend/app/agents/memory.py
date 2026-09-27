"""
PilgrimAI - In-Memory Conversation Memory Manager (Phase I)

Maintains short-lived conversational context across turns within distinct user sessions.
Supports deterministic pronoun and anaphora resolution without external LLM dependencies.

Core Principles:
- 100% Deterministic (pure in-memory rule-based entity tracking and resolution).
- Zero external databases (Redis, Postgres, Mongo are strictly avoided).
- Zero LLM generation / classification calls.
- Zero raw RAG, vector store, or retrieval dependency.
- Strict bounded session capacity (LRU eviction at 1000 sessions).
- Time-to-Live (TTL) expiration per session (default: 30 minutes).
- Complete session isolation (zero cross-session context leakage).
- Sensitive credential and secret sanitization.
"""

import re
import copy
import time
import logging
from collections import OrderedDict
from typing import Dict, Any, List, Optional, Tuple, Callable, Set
from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)

# Constants
MAX_SESSIONS_DEFAULT = 1000
DEFAULT_TTL_SECONDS = 1800.0  # 30 minutes

# Sensitive keys to redact
_SENSITIVE_KEYS = {
    "api_key", "secret", "password", "token", "access_token",
    "auth", "authorization", "private_key", "credential"
}


def _sanitize_meta(meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Sanitizes metadata dictionary removing sensitive keys and truncating long texts."""
    if not meta:
        return {}
    sanitized = {}
    for k, v in meta.items():
        k_str = str(k).lower()
        if any(sens in k_str for sens in _SENSITIVE_KEYS):
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, str) and len(v) > 1000:
            sanitized[k] = v[:1000] + "... [TRUNCATED]"
        elif isinstance(v, dict):
            sanitized[k] = _sanitize_meta(v)
        else:
            sanitized[k] = v
    return sanitized


class MemoryTurn(BaseModel):
    """
    Lightweight structured representation of an individual conversation turn.
    Stores conversational entities (temples, intents) rather than raw document text.
    """
    model_config = ConfigDict(extra="allow")

    session_id: str = Field(..., description="Unique conversation session identifier")
    user_query: str = Field(..., description="Original query as submitted by user")
    resolved_query: str = Field(..., description="Query after anaphora/pronoun resolution")
    detected_intents: List[str] = Field(default_factory=list, description="Classified intents for turn")
    identified_temples: List[str] = Field(default_factory=list, description="Canonical temples identified")
    timestamp: float = Field(..., description="Unix timestamp of the turn")
    response_summary: str = Field(default="", description="Brief summary of response text")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Sanitized turn metadata")


class ConversationMemoryManager:
    """
    In-memory, session-isolated conversation context manager.
    Enforces LRU session bounds, TTL expiration, and deterministic pronoun resolution.
    """

    def __init__(
        self,
        max_sessions: int = MAX_SESSIONS_DEFAULT,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        time_provider: Optional[Callable[[], float]] = None
    ):
        self.max_sessions = max_sessions
        self.ttl_seconds = ttl_seconds
        self._time_provider = time_provider or time.time
        # OrderedDict used for LRU tracking: key -> session dict
        self._sessions: OrderedDict[str, Dict[str, Any]] = OrderedDict()

    def _now(self) -> float:
        return float(self._time_provider())

    def _get_or_create_session(self, session_id: str) -> Dict[str, Any]:
        """
        Retrieves existing session (verifying TTL) or creates a new one.
        Enforces LRU eviction if capacity is reached.
        """
        now = self._now()

        if session_id in self._sessions:
            session = self._sessions[session_id]
            # Check TTL expiration
            if (now - session["last_accessed"]) > self.ttl_seconds:
                # Expired session -> remove and reset
                del self._sessions[session_id]
            else:
                # Refresh access time and move to end (MRU position)
                session["last_accessed"] = now
                self._sessions.move_to_end(session_id)
                return session

        # Enforce LRU eviction if capacity reached
        while len(self._sessions) >= self.max_sessions:
            # Evict least recently used session (first item in OrderedDict)
            evicted_id, _ = self._sessions.popitem(last=False)
            logger.debug(f"Evicted LRU session: {evicted_id}")

        new_session = {
            "session_id": session_id,
            "created_at": now,
            "last_accessed": now,
            "turns": []
        }
        self._sessions[session_id] = new_session
        return new_session

    def add_turn(
        self,
        session_id: str,
        user_query: str,
        resolved_query: Optional[str] = None,
        detected_intents: Optional[List[str]] = None,
        identified_temples: Optional[List[str]] = None,
        response_summary: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> MemoryTurn:
        """
        Records a completed conversation turn for the given session.
        """
        session = self._get_or_create_session(session_id)
        now = self._now()
        safe_meta = _sanitize_meta(metadata)

        turn = MemoryTurn(
            session_id=session_id,
            user_query=user_query,
            resolved_query=resolved_query or user_query,
            detected_intents=detected_intents or [],
            identified_temples=identified_temples or [],
            timestamp=now,
            response_summary=response_summary[:300] if response_summary else "",
            metadata=safe_meta
        )

        session["turns"].append(turn)
        session["last_accessed"] = now
        self._sessions.move_to_end(session_id)
        return turn

    def get_recent_turns(self, session_id: str, limit: int = 5) -> List[MemoryTurn]:
        """
        Returns chronological list of recent turns for session, up to limit.
        Returns defensive copies to prevent caller mutation of internal state.
        """
        now = self._now()
        if session_id not in self._sessions:
            return []

        session = self._sessions[session_id]
        if (now - session["last_accessed"]) > self.ttl_seconds:
            # Expired
            del self._sessions[session_id]
            return []

        # Refresh access time and move to end
        session["last_accessed"] = now
        self._sessions.move_to_end(session_id)

        turns = session["turns"][-limit:] if limit > 0 else []
        return [copy.deepcopy(t) for t in turns]

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Returns a defensive copy of the session state for testing and diagnostics.
        """
        now = self._now()
        if session_id not in self._sessions:
            return None

        session = self._sessions[session_id]
        if (now - session["last_accessed"]) > self.ttl_seconds:
            del self._sessions[session_id]
            return None

        session["last_accessed"] = now
        self._sessions.move_to_end(session_id)
        return copy.deepcopy(session)

    def clear_session(self, session_id: str) -> bool:
        """
        Clears memory for a specific session. Safe no-op if session does not exist.
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def clear_all(self) -> None:
        """
        Clears all in-memory sessions.
        """
        self._sessions.clear()

    def resolve_query(self, session_id: str, query: str) -> Dict[str, Any]:
        """
        Deterministically resolves pronouns and anaphoric references using recent conversation context.

        Returns:
            Dict containing:
                - "resolved_query": str
                - "is_ambiguous": bool
                - "referenced_temple": Optional[str]
                - "clarification_message": Optional[str]
        """
        clean_query = query.strip()
        recent_turns = self.get_recent_turns(session_id, limit=3)

        # 1. Check if the query itself explicitly names a registered or unregistered temple
        # (Imported dynamically from router planner to preserve strict dependency boundaries)
        from app.rag.query_planner import query_planner
        explicit_temples = []
        q_norm = clean_query.lower()
        for canonical, aliases in query_planner.temple_aliases.items():
            for alias in sorted(aliases, key=len, reverse=True):
                pattern = r'\b' + re.escape(alias) + r'\b'
                if re.search(pattern, q_norm):
                    explicit_temples.append(canonical)
                    break

        if explicit_temples:
            # Explicit new temple in the current turn overrides all memory
            return {
                "resolved_query": clean_query,
                "is_ambiguous": False,
                "referenced_temple": explicit_temples[0],
                "clarification_message": None
            }

        # 2. Extract temples mentioned across recent turns
        recent_temples_ordered: List[str] = []
        for t in reversed(recent_turns):
            for tm in t.identified_temples:
                if tm and tm not in recent_temples_ordered:
                    recent_temples_ordered.append(tm)

        # 3. Check for pronoun and anaphoric reference triggers
        # Examples: "its", "it", "this temple", "that temple", "the temple", "there"
        pronoun_patterns = [
            (r"\b(its|it's)\b", "possessive"),
            (r"\b(this|that|the)\s+temple\b", "demonstrative"),
            (r"\bthere\b", "locative"),
            (r"\bit\b", "neutral_pronoun")
        ]

        has_reference = False
        ref_type = None
        for pat, r_type in pronoun_patterns:
            if re.search(pat, clean_query, re.IGNORECASE):
                has_reference = True
                ref_type = r_type
                break

        # If query has no pronouns and no context is needed, return original query
        if not has_reference:
            # Check budget follow-up queries like "what about for 2 people?", "budget for one person", "for 4 people"
            budget_followup_pattern = r"\b(what\s+about\s+(for\s+)?|how\s+about\s+(for\s+)?|budget\s+for\s+|and\s+for\s+|for\s+)(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(people|person|persons|adults)\b"
            if re.search(budget_followup_pattern, clean_query, re.IGNORECASE) and recent_temples_ordered:
                has_reference = True
                ref_type = "budget_followup"
            else:
                # Check ellipsis queries like "What about sevas?" or "And timings?"
                ellipsis_pattern = r"\b(what\s+about|how\s+about|and|also)\s+(sevas?|timings?|facilities|rooms?|history|dress\s+code|budget|cost|price)\b"
                if re.search(ellipsis_pattern, clean_query, re.IGNORECASE) and recent_temples_ordered:
                    has_reference = True
                    ref_type = "ellipsis"
                else:
                    return {
                        "resolved_query": clean_query,
                        "is_ambiguous": False,
                        "referenced_temple": None,
                        "clarification_message": None
                    }

        # 4. Handle ambiguity: multiple distinct temples mentioned recently
        if len(recent_temples_ordered) > 1:
            temples_str = " and ".join(recent_temples_ordered[:2])
            return {
                "resolved_query": clean_query,
                "is_ambiguous": True,
                "referenced_temple": None,
                "clarification_message": f"Which temple are you referring to? You recently discussed {temples_str}."
            }

        # If no temples exist in recent memory, cannot resolve pronoun
        if not recent_temples_ordered:
            return {
                "resolved_query": clean_query,
                "is_ambiguous": False,
                "referenced_temple": None,
                "clarification_message": None
            }

        # 5. Deterministically resolve reference to the single recent temple
        target_temple = recent_temples_ordered[0]
        resolved = clean_query

        if ref_type == "possessive":
            # "What are its sevas?" -> "What are Dharmapuri temple's sevas?"
            resolved = re.sub(r"\b(its|it's)\b", f"{target_temple} temple's", resolved, flags=re.IGNORECASE)
        elif ref_type == "demonstrative":
            # "timings of the temple" -> "timings of Dharmapuri temple"
            resolved = re.sub(r"\b(this|that|the)\s+temple\b", f"{target_temple} temple", resolved, flags=re.IGNORECASE)
        elif ref_type == "locative":
            # "how to reach there?" -> "how to reach Dharmapuri"
            if re.search(r"\b(reach|go\s+to|travel\s+to|head\s+to|visit)\s+there\b", resolved, re.IGNORECASE):
                resolved = re.sub(r"\b(reach|go\s+to|travel\s+to|head\s+to|visit)\s+there\b", rf"\1 {target_temple}", resolved, flags=re.IGNORECASE)
            elif re.search(r"\bto\s+there\b", resolved, re.IGNORECASE):
                resolved = re.sub(r"\bto\s+there\b", f"to {target_temple}", resolved, flags=re.IGNORECASE)
            else:
                # "Is accommodation available there?" -> "Is accommodation available at Dharmapuri temple?"
                resolved = re.sub(r"\bthere\b", f"at {target_temple} temple", resolved, flags=re.IGNORECASE)
        elif ref_type == "neutral_pronoun":
            # "How can I reach it?" -> "How can I reach Dharmapuri temple?"
            resolved = re.sub(r"\bit\b", f"{target_temple} temple", resolved, flags=re.IGNORECASE)
        elif ref_type == "budget_followup":
            # "what about for 2 people?" -> "what about budget for 2 people at Dharmapuri temple?"
            if not re.search(r"\bbudget\b", resolved, re.IGNORECASE):
                resolved = f"budget {resolved} at {target_temple} temple"
            else:
                resolved = f"{resolved} at {target_temple} temple"
        elif ref_type == "ellipsis":
            # "What about sevas?" -> "What about sevas at Dharmapuri temple?"
            resolved = f"{resolved} at {target_temple} temple"

        return {
            "resolved_query": resolved,
            "is_ambiguous": False,
            "referenced_temple": target_temple,
            "clarification_message": None
        }
