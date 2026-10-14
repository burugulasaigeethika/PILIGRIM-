"""
PilgrimAI - Live Navigation Agent (Phase O5)

Provides real-time routing, distance, travel duration, and direction details
between origins and pilgrimage temples using Google Maps Routes API v2 through
NavigationAdapter (O1 Firewall) and TempleCoordinateRegistry (O2 Registry).

Core Principles:
- Provider: Google Maps Routes API v2 via NavigationAdapter firewall.
- Zero credential leakage: API keys are never exposed in responses, logs, or traces.
- Zero-credential safety: missing credentials return a controlled informational message.
- Zero fabrication: distances, durations, routes, traffic, tolls, and speeds are NEVER invented.
- Pure provenance: only provider-returned fields are displayed; unsupplied fields are explicitly noted.
- Decoupled: zero raw RAG, vector DB, or direct HTTP imports.
- Supports canonical temples, temple aliases, and recognized regional cities/places.
"""

import re
import time
import logging
from typing import Dict, Any, Optional, Tuple, List, Union
from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState, AgentResponse
from app.agents.adapters.external_adapter import (
    ExternalAdapterError,
    ExternalTimeoutError,
    ExternalConnectionError,
    ExternalHTTPError,
    ExternalRateLimitError,
    ExternalCircuitOpenError
)
from app.agents.adapters.navigation_adapter import (
    NavigationAdapter,
    NavigationCredentialMissingError,
    RouteNotFoundError,
    UnsupportedTravelModeError
)
from app.agents.coordinate_registry import TempleCoordinateRegistry, TempleCoordinate

logger = logging.getLogger(__name__)

# Known major regional cities/places for address-based routing when origin/destination is not a temple
_KNOWN_REGIONAL_PLACES = {
    "hyderabad", "secunderabad", "warangal", "hanamkonda", "kazipet",
    "karimnagar", "nizamabad", "khammam", "nalgonda", "suryapet",
    "mahabubnagar", "adivaram", "ramagundam", "siddipet", "mancherial",
    "vijayawada", "guntur", "visakhapatnam", "tirupati", "kurnool",
    "bengaluru", "bangalore", "chennai", "mumbai", "delhi", "pune"
}


class NavigationResult(BaseModel):
    """Normalized structured data model representing route computation results."""
    origin: str = Field(..., description="User-specified origin name")
    destination: str = Field(..., description="User-specified destination name")
    origin_canonical: Optional[str] = Field(default=None, description="Canonical name if a registered temple")
    destination_canonical: Optional[str] = Field(default=None, description="Canonical name if a registered temple")
    distance_km: Optional[float] = Field(default=None, description="Driving/travel distance in kilometers")
    duration_minutes: Optional[float] = Field(default=None, description="Estimated travel duration in minutes")
    traffic_duration_minutes: Optional[float] = Field(default=None, description="Traffic-aware duration in minutes if returned")
    route_summary: Optional[str] = Field(default=None, description="Provider route description or major highway")
    travel_mode: str = Field(default="driving", description="Travel mode (driving, walking, bicycling, transit)")
    provider: str = Field(default="Google Maps Routes API", description="Underlying navigation service provider")
    retrieved_at: Optional[str] = Field(default=None, description="ISO timestamp of route retrieval")
    cache_hit: bool = Field(default=False, description="Whether result was served from cache")
    polyline: Optional[str] = Field(default=None, description="Encoded polyline string of the route geometry")
    viewport: Optional[Dict[str, Any]] = Field(default=None, description="Bounding viewport coordinates {low, high}")
    speed_reading_intervals: Optional[List[Dict[str, Any]]] = Field(default=None, description="Traffic speed reading intervals on polyline")


def format_duration(minutes: Optional[float]) -> str:
    """Formats numeric minutes into human-readable duration string (e.g., '1 hr 35 min' or '45 min')."""
    if minutes is None:
        return "Not available"
    total_mins = int(round(minutes))
    if total_mins < 60:
        return f"{total_mins} min"
    hours = total_mins // 60
    rem_mins = total_mins % 60
    if rem_mins == 0:
        return f"{hours} hr"
    return f"{hours} hr {rem_mins} min"


class LiveNavigationAgent(BaseAgent):
    """
    Specialist agent for retrieving live navigation routes, distance, and duration.
    Interfaces exclusively through NavigationAdapter and TempleCoordinateRegistry.
    """

    def __init__(
        self,
        coordinate_registry: Optional[TempleCoordinateRegistry] = None,
        adapter: Optional[NavigationAdapter] = None,
        cache_ttl_sec: float = 60.0,
        cache_enabled: bool = False
    ):
        super().__init__(
            name="live_navigation",
            description="Fetches live route, distance, travel duration, and navigation details using external navigation provider."
        )
        self.coordinate_registry = coordinate_registry or TempleCoordinateRegistry()
        self.adapter = adapter or NavigationAdapter()
        self.cache_ttl_sec = float(cache_ttl_sec)
        self.cache_enabled = bool(cache_enabled)
        self._cache: Dict[str, Tuple[float, NavigationResult]] = {}

    def extract_route_parameters(self, query: str) -> Dict[str, Any]:
        """
        Deterministically extracts origin, destination, and travel mode from query text.
        
        Patterns supported:
        - 'i want to travel to {dest} from {orig} give me bus routes'
        - 'travel from {orig} to {dest}'
        - 'travel to {dest} from {orig}'
        - 'how do i get from {orig} to {dest}'
        - 'route from {orig} to {dest}'
        - 'bus from {orig} to {dest}'
        - 'give me bus routes from {orig} to {dest}'
        - 'how far is {dest} from {orig}'
        - 'how far is {orig} from {dest}'
        - 'distance from {orig} to {dest}'
        - 'directions from {orig} to {dest}'
        - 'distance between {orig} and {dest}'
        - 'route between {orig} and {dest}'
        - 'how long does it take to reach {dest} from {orig}'
        - 'driving time from {orig} to {dest}'
        """
        clean_q = query.strip()
        q_lower = clean_q.lower()

        # 1. Detect travel mode
        travel_mode = "driving"
        if re.search(r"\b(walk|walking|by\s+foot|on\s+foot)\b", q_lower):
            travel_mode = "walking"
        elif re.search(r"\b(cycle|cycling|bicycle|bicycling|by\s+bike|by\s+cycle)\b", q_lower):
            travel_mode = "bicycling"
        elif re.search(r"\b(transit|bus|buses|train|trains|public\s+transit|by\s+bus|by\s+train)\b", q_lower):
            travel_mode = "transit"

        # 2. Origin & Destination Extraction
        orig_raw: Optional[str] = None
        dest_raw: Optional[str] = None

        # Clean trailing question marks and punctuation
        stripped_q = re.sub(r"[?!.,;]+$", "", clean_q).strip()

        # Pattern A: 'between {orig} and {dest}'
        m_between = re.search(
            r"\bbetween\s+(.+?)\s+and\s+(.+?)(?:\s+(?:by\s+(?:car|walk|bike|cycle|transit|driving|foot|bus|train)|give\s+me\s+.*|please.*))?$",
            stripped_q,
            re.IGNORECASE
        )
        if m_between:
            orig_raw, dest_raw = m_between.group(1), m_between.group(2)

        # Pattern B: '{action/prefix} to {dest} from {orig} {suffix}'
        # e.g., 'i want to travel to vemulavada from hyderabad give me bus routes'
        # e.g., 'how far is Yadadri from Hyderabad', 'how to reach Yadadri from Hyderabad'
        if not orig_raw or not dest_raw:
            m_to_from = re.search(
                r"(?:(?:i\s+want\s+to\s+)?(?:travel|go|drive|head)\s+to|how\s+(?:do\s+i|can\s+i|to)\s+(?:get|reach|go|travel)\s+to|directions?\s+to|route\s+to|how\s+far\s+is|how\s+long\s+(?:does\s+it\s+take\s+(?:to\s+reach)?|to\s+reach)?|to)\s+(.+?)\s+from\s+(.+?)$",
                stripped_q,
                re.IGNORECASE
            )
            if m_to_from:
                dest_raw, orig_raw = m_to_from.group(1), m_to_from.group(2)

        # Pattern C: '{action/prefix} from {orig} to {dest} {suffix}'
        # e.g., 'give me bus routes from Hyderabad to Vemulavada', 'Directions from Secunderabad to Basara'
        if not orig_raw or not dest_raw:
            m_from_to = re.search(
                r"\bfrom\s+(.+?)\s+to\s+(.+?)$",
                stripped_q,
                re.IGNORECASE
            )
            if m_from_to:
                orig_raw, dest_raw = m_from_to.group(1), m_from_to.group(2)

        # Pattern D: '{dest} from {orig}' fallback
        if not orig_raw or not dest_raw:
            m_simple = re.search(r"(.+?)\s+from\s+(.+?)$", stripped_q, re.IGNORECASE)
            if m_simple:
                cand_dest = m_simple.group(1)
                dest_raw, orig_raw = cand_dest, m_simple.group(2)

        # Pattern E: Single location check (e.g., 'How far is Yadadri?', 'Directions to Basara', 'route map of Yadadri')
        if not orig_raw and not dest_raw:
            m_single = re.search(
                r"(?:how\s+far\s+is|directions?\s+(?:to|of|for)|route\s+(?:map\s+)?(?:of|for|to)|map\s+route\s+(?:of|for|to)|travel\s+time\s+to|driving\s+time\s+to)\s+(.+?)$",
                stripped_q,
                re.IGNORECASE
            )
            if m_single:
                dest_raw = m_single.group(1).strip()

        # Filter metric noise words mistakenly assigned as destination or origin
        METRIC_NOISE_WORDS = {
            "directions", "direction", "route", "routes", "distance",
            "travel time", "driving time", "how far", "eta", "estimated arrival"
        }
        if dest_raw and dest_raw.strip().lower() in METRIC_NOISE_WORDS:
            dest_raw = None
        if orig_raw and orig_raw.strip().lower() in METRIC_NOISE_WORDS:
            orig_raw = None

        # Clean noise words
        orig_clean = self._clean_place_name(orig_raw) if orig_raw else None
        dest_clean = self._clean_place_name(dest_raw) if dest_raw else None

        return {
            "origin": orig_clean,
            "destination": dest_clean,
            "travel_mode": travel_mode
        }

    def _clean_place_name(self, text: Optional[str]) -> Optional[str]:
        """Cleans extraneous filler words while preserving canonical identifiers."""
        if not text:
            return None
        t = text.strip()
        # Remove trailing question marks or punctuation
        t = re.sub(r"[?!.,;]+$", "", t).strip()

        # Remove leading conversational / intent filler prefixes
        t = re.sub(
            r"^(?:(?:i\s+want\s+to\s+)?(?:travel|go|drive|head)\s+(?:to|from)?|how\s+(?:do\s+i|can\s+i|to)\s+(?:get|reach|go|travel)\s+(?:to|from)?|give\s+me\s+(?:the\s+)?(?:bus\s+|driving\s+|car\s+)?(?:routes?|directions?|distance)\s+(?:to|from)?|show\s+me\s+(?:the\s+)?(?:bus\s+|driving\s+|car\s+)?(?:routes?|directions?|distance)\s+(?:to|from)?|tell\s+me\s+(?:the\s+)?(?:bus\s+|driving\s+|car\s+)?(?:routes?|directions?|distance)\s+(?:to|from)?|what\s+is\s+the\s+(?:distance|route|driving\s+time|travel\s+time)\s+(?:of|for|between|from|to)?|how\s+far\s+is|directions?\s+(?:to|from|for|of)?|routes?\s+(?:to|from|for|of)?|reach|get\s+to|travel\s+to|travel\s+from|the|a|an)\s+",
            "",
            t,
            flags=re.IGNORECASE
        ).strip()

        # Remove trailing explanatory clauses (e.g., 'and explain the route information available', 'and tell me directions')
        t = re.sub(
            r"\s+(?:and|&)\s+(?:explain|tell\s+me|tell|describe|give\s+me|give|provide|show\s+me|show|detail)\b.*$",
            "",
            t,
            flags=re.IGNORECASE
        ).strip()

        # Remove trailing noise words and filler suffixes
        t = re.sub(
            r"\s+(?:give\s+me\s+(?:bus\s+|driving\s+|car\s+)?(?:routes?|directions?)|show\s+(?:me\s+)?(?:bus\s+|driving\s+|car\s+)?(?:routes?|directions?)|bus\s+routes?|driving\s+routes?|routes?|directions?|bus\s+timings?|by\s+(?:car|walk|bike|cycle|transit|driving|foot|bus|train)|please|thanks|thank\s+you)+$",
            "",
            t,
            flags=re.IGNORECASE
        ).strip()

        # Remove any lingering leading articles
        t = re.sub(r"^(the|a|an)\s+", "", t, flags=re.IGNORECASE).strip()
        return t if t else None

    def _resolve_location(self, place_name: Optional[str]) -> Tuple[str, Optional[Tuple[float, float]], Optional[str]]:
        """
        Resolves a place string to:
        (display_name, coordinates_tuple_or_None, canonical_name_or_None).
        
        Uses TempleCoordinateRegistry for temples and aliases.
        Uses recognized cities/places or passes address string through to provider.
        """
        if not place_name:
            return "", None, None

        # 1. Check Temple Coordinate Registry (handles canonical names and all aliases)
        temple_coord = self.coordinate_registry.get_coordinate(place_name)
        if temple_coord is not None:
            return (
                temple_coord.display_name or temple_coord.canonical_name,
                (temple_coord.latitude, temple_coord.longitude),
                temple_coord.canonical_name
            )

        # 2. Known Regional Cities / Places (address-based geocoding via Routes API)
        title_case = place_name.strip().title()
        return title_case, None, None

    def _format_markdown_response(self, result: NavigationResult) -> str:
        """Formats the NavigationResult into a structured Section Markdown response."""
        orig_disp = result.origin_canonical or result.origin
        dest_disp = result.destination_canonical or result.destination

        lines = [
            f"### Live Route Navigation: {orig_disp} → {dest_disp}",
            "",
            "#### Route Facts"
        ]

        # 1. Distance
        if result.distance_km is not None:
            lines.append(f"- **Distance**: {result.distance_km} km")
        else:
            lines.append("- **Distance**: Distance data not supplied by provider")

        # 2. Duration
        mode_label = result.travel_mode.title()
        if result.duration_minutes is not None:
            lines.append(f"- **Estimated Duration ({mode_label})**: {format_duration(result.duration_minutes)}")
        else:
            lines.append(f"- **Estimated Duration ({mode_label})**: Duration data not supplied by provider")

        # 3. Traffic Duration
        if result.traffic_duration_minutes is not None:
            lines.append(f"- **Traffic-Aware Duration**: {format_duration(result.traffic_duration_minutes)}")
        else:
            lines.append("- **Traffic-Aware Duration**: Live traffic information was not available from the configured provider.")

        # 4. Route summary / highway
        if result.route_summary:
            lines.append(f"- **Primary Route**: {result.route_summary}")

        lines.extend([
            "",
            "#### Journey Details",
            f"- **Origin**: {orig_disp}",
            f"- **Destination**: {dest_disp}",
            f"- **Travel Mode**: {mode_label}",
            f"- **Provider**: {result.provider}"
        ])

        if result.retrieved_at:
            lines.append(f"- **Retrieved At**: {result.retrieved_at}")

        lines.extend([
            "",
            "> **Note**: Navigation details are retrieved live from Google Maps Routes API. "
            "Actual travel times, road conditions, tolls, and detours may vary depending on local traffic, weather, and devasthanam parking regulations."
        ])

        return "\n".join(lines)

    def _run(self, state: AgentState) -> AgentResponse:
        """
        Executes live navigation query resolution via BaseAgent.execute lifecycle.
        """
        t0 = time.perf_counter()
        raw_query = state.user_query.strip()

        # 1. Empty input validation
        if not raw_query:
            return AgentResponse(
                success=False,
                agent_name=self.name,
                answer="Please provide a valid navigation or route question.",
                sources=[],
                error="Empty query",
                latency_ms=(time.perf_counter() - t0) * 1000.0
            )

        # 2. Extract Route Parameters
        params = self.extract_route_parameters(raw_query)
        origin_str = params.get("origin")
        dest_str = params.get("destination")
        travel_mode = params.get("travel_mode", "driving")

        # 3. Missing origin or destination clarification
        if not origin_str or not dest_str:
            target_temple = dest_str or origin_str
            if target_temple:
                clarification_msg = (
                    f"I can show a route map for {target_temple}, but I need a recognizable origin and destination. "
                    f"Please specify a starting location (e.g., 'Give me the route from Hyderabad to {target_temple}')."
                )
            else:
                clarification_msg = (
                    "I need a recognizable origin and destination to calculate a route. "
                    "Please specify both the starting point and destination (e.g., 'How far is Yadadri from Hyderabad?' or 'Route from Basara to Dharmapuri')."
                )
            return AgentResponse(
                success=False,
                agent_name=self.name,
                answer=clarification_msg,
                sources=[],
                error="Missing origin or destination",
                metadata={"clarification_needed": True, "extracted_params": params},
                latency_ms=(time.perf_counter() - t0) * 1000.0
            )

        # 4. Check zero-credential condition upfront
        if not self.adapter.has_credentials and self.adapter.transport is None:
            return AgentResponse(
                success=False,
                agent_name=self.name,
                answer="Live navigation is currently unavailable because no navigation provider credential is configured.",
                sources=[],
                error="Navigation provider credential not configured",
                metadata={
                    "provider": "Google Maps Routes API",
                    "credential_configured": False,
                    "origin": origin_str,
                    "destination": dest_str
                },
                latency_ms=(time.perf_counter() - t0) * 1000.0
            )

        # 5. Resolve locations to coordinates or verified names
        orig_name, orig_coords, orig_canon = self._resolve_location(origin_str)
        dest_name, dest_coords, dest_canon = self._resolve_location(dest_str)

        orig_waypoint: Union[Tuple[float, float], str] = orig_coords if orig_coords else orig_name
        dest_waypoint: Union[Tuple[float, float], str] = dest_coords if dest_coords else dest_name

        # 6. Check cache if enabled
        cache_key = f"{origin_str.lower()}::{dest_str.lower()}::{travel_mode}"
        now_ts = time.time()
        if self.cache_enabled and cache_key in self._cache:
            cache_time, cached_result = self._cache[cache_key]
            if (now_ts - cache_time) <= self.cache_ttl_sec:
                result_copy = cached_result.model_copy()
                result_copy.cache_hit = True
                answer_md = self._format_markdown_response(result_copy)
                return AgentResponse(
                    success=True,
                    agent_name=self.name,
                    answer=answer_md,
                    sources=["Google Maps Routes API"],
                    metadata=result_copy.model_dump(),
                    latency_ms=(time.perf_counter() - t0) * 1000.0
                )

        # 7. Query NavigationAdapter
        try:
            route_data = self.adapter.compute_route(
                origin=orig_waypoint,
                destination=dest_waypoint,
                travel_mode=travel_mode
            )
        except NavigationCredentialMissingError:
            return AgentResponse(
                success=False,
                agent_name=self.name,
                answer="Live navigation is currently unavailable because no navigation provider credential is configured.",
                sources=[],
                error="Navigation provider credential not configured",
                metadata={"credential_configured": False},
                latency_ms=(time.perf_counter() - t0) * 1000.0
            )
        except UnsupportedTravelModeError as e:
            return AgentResponse(
                success=False,
                agent_name=self.name,
                answer=f"The requested travel mode '{travel_mode}' is not supported by the navigation provider. Supported modes include: driving, walking, bicycling.",
                sources=[],
                error=str(e),
                metadata={"travel_mode": travel_mode, "unsupported_mode": True},
                latency_ms=(time.perf_counter() - t0) * 1000.0
            )
        except RouteNotFoundError:
            return AgentResponse(
                success=False,
                agent_name=self.name,
                answer=f"No route could be found between '{origin_str}' and '{dest_str}'. Please check the locations and try again.",
                sources=[],
                error="Route not found",
                metadata={"origin": origin_str, "destination": dest_str, "route_not_found": True},
                latency_ms=(time.perf_counter() - t0) * 1000.0
            )
        except ExternalTimeoutError:
            return AgentResponse(
                success=False,
                agent_name=self.name,
                answer="Navigation request timed out. Please check your network connection and try again.",
                sources=[],
                error="Navigation request timed out",
                latency_ms=(time.perf_counter() - t0) * 1000.0
            )
        except ExternalConnectionError:
            return AgentResponse(
                success=False,
                agent_name=self.name,
                answer="Navigation provider is currently unreachable. Please try again shortly.",
                sources=[],
                error="Navigation provider connection failure",
                latency_ms=(time.perf_counter() - t0) * 1000.0
            )
        except ExternalRateLimitError:
            return AgentResponse(
                success=False,
                agent_name=self.name,
                answer="Navigation request rate limit reached. Please wait a moment before retrying.",
                sources=[],
                error="Rate limit exceeded",
                latency_ms=(time.perf_counter() - t0) * 1000.0
            )
        except ExternalCircuitOpenError:
            return AgentResponse(
                success=False,
                agent_name=self.name,
                answer="Navigation service is temporarily unavailable due to repeated errors. Please retry later.",
                sources=[],
                error="Circuit breaker OPEN",
                latency_ms=(time.perf_counter() - t0) * 1000.0
            )
        except ExternalHTTPError as e:
            return AgentResponse(
                success=False,
                agent_name=self.name,
                answer="Navigation provider authentication or service error. Please verify provider configuration.",
                sources=[],
                error=f"HTTP {e.status_code}: {e.raw_message}",
                latency_ms=(time.perf_counter() - t0) * 1000.0
            )
        except ExternalAdapterError as e:
            return AgentResponse(
                success=False,
                agent_name=self.name,
                answer="Live navigation is currently unavailable due to an unexpected provider error.",
                sources=[],
                error=str(e),
                latency_ms=(time.perf_counter() - t0) * 1000.0
            )
        except Exception as e:
            logger.error(f"Unexpected error in LiveNavigationAgent: {e}", exc_info=True)
            return AgentResponse(
                success=False,
                agent_name=self.name,
                answer="An unexpected error occurred while calculating the route.",
                sources=[],
                error=str(e),
                latency_ms=(time.perf_counter() - t0) * 1000.0
            )

        # 8. Parse Provider Route Data
        routes = route_data.get("routes", [])
        if not routes:
            return AgentResponse(
                success=False,
                agent_name=self.name,
                answer=f"No route could be found between '{origin_str}' and '{dest_str}'.",
                sources=[],
                error="Empty routes array",
                latency_ms=(time.perf_counter() - t0) * 1000.0
            )

        primary_route = routes[0]

        # Distance extraction
        distance_km: Optional[float] = None
        if "distanceMeters" in primary_route:
            try:
                distance_km = round(float(primary_route["distanceMeters"]) / 1000.0, 1)
            except (ValueError, TypeError):
                distance_km = None

        # Duration extraction
        duration_minutes: Optional[float] = None
        traffic_duration_minutes: Optional[float] = None

        # Standard duration
        duration_raw = primary_route.get("duration")
        if duration_raw:
            dur_sec = self._parse_duration_seconds(duration_raw)
            if dur_sec is not None:
                duration_minutes = round(dur_sec / 60.0, 1)

        # Static vs Traffic Duration
        static_duration_raw = primary_route.get("staticDuration")
        if static_duration_raw:
            static_sec = self._parse_duration_seconds(static_duration_raw)
            if static_sec is not None and duration_minutes is not None:
                static_mins = round(static_sec / 60.0, 1)
                # If duration differs from staticDuration, duration contains traffic!
                if abs(duration_minutes - static_mins) >= 0.5:
                    traffic_duration_minutes = duration_minutes
                    duration_minutes = static_mins

        # Route summary
        route_summary = primary_route.get("description")

        # Route geometry (polyline and viewport)
        polyline_encoded: Optional[str] = None
        if "polyline" in primary_route and isinstance(primary_route["polyline"], dict):
            polyline_encoded = primary_route["polyline"].get("encodedPolyline")

        viewport_data: Optional[Dict[str, Any]] = primary_route.get("viewport")

        # Traffic speed reading intervals
        speed_intervals: Optional[List[Dict[str, Any]]] = None
        if "travelAdvisory" in primary_route and isinstance(primary_route["travelAdvisory"], dict):
            speed_intervals = primary_route["travelAdvisory"].get("speedReadingIntervals")

        # Construct NavigationResult
        iso_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_ts))
        result = NavigationResult(
            origin=orig_name or origin_str,
            destination=dest_name or dest_str,
            origin_canonical=orig_canon,
            destination_canonical=dest_canon,
            distance_km=distance_km,
            duration_minutes=duration_minutes,
            traffic_duration_minutes=traffic_duration_minutes,
            route_summary=route_summary,
            travel_mode=travel_mode,
            provider="Google Maps Routes API",
            retrieved_at=iso_time,
            cache_hit=False,
            polyline=polyline_encoded,
            viewport=viewport_data,
            speed_reading_intervals=speed_intervals
        )

        if self.cache_enabled:
            self._cache[cache_key] = (now_ts, result)

        answer_text = self._format_markdown_response(result)

        return AgentResponse(
            success=True,
            agent_name=self.name,
            answer=answer_text,
            sources=["Google Maps Routes API"],
            metadata=result.model_dump(),
            latency_ms=(time.perf_counter() - t0) * 1000.0
        )

    def _parse_duration_seconds(self, dur_val: Any) -> Optional[float]:
        """Parses Google API duration format (e.g. '3600s' or integer seconds)."""
        if dur_val is None:
            return None
        if isinstance(dur_val, (int, float)):
            return float(dur_val)
        if isinstance(dur_val, str):
            s = dur_val.strip().rstrip("sS")
            try:
                return float(s)
            except ValueError:
                return None
        return None

    def process(self, state: AgentState) -> AgentResponse:
        """Alias for BaseAgent.execute for coordinator consistency."""
        return self.execute(state)
