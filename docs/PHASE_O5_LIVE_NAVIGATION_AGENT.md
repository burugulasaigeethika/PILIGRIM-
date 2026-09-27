# Phase O5 — Live Navigation Agent Documentation

## 1. Objective & Scope

Phase O5 introduces the **`LiveNavigationAgent`** (`name = "live_navigation"`) to the PilgrimAI multi-agent architecture. It provides live distance, travel duration, traffic conditions, and turn-by-turn or route summary descriptions when an external navigation provider is configured.

### Non-Negotiable Boundaries:
- **Strict Scope**: Implements ONLY `LiveNavigationAgent` and `NavigationAdapter`. Does NOT implement `VoiceMultilingualAgent` (O6) or Phase O7 integrations.
- **Provider**: Google Maps Routes API v2 (`https://routes.googleapis.com/directions/v2:computeRoutes`).
- **External API Firewall**: Subclasses `BaseExternalAdapter` (Phase O1 firewall) with strict connection/read timeouts, max-1 retry, circuit breaker, and automatic header/query secret sanitization.
- **Coordinate Registry**: All temple locations are resolved via `TempleCoordinateRegistry` (Phase O2 registry) without guessing coordinates.
- **Zero-Credential Safety**: When `GOOGLE_MAPS_API_KEY` is not configured, the agent safely and gracefully returns:
  `"Live navigation is currently unavailable because no navigation provider credential is configured."`
  No fake routes, manufactured distances, or estimated ETAs are ever generated.
- **Zero-Fabrication Contract**:
  - Distance must strictly come from `distanceMeters`.
  - Duration must strictly come from provider `duration`.
  - Traffic-aware duration only shown when actually returned by provider.
  - Never derive `duration = distance / assumed speed`.
  - Never manufacture traffic conditions, ETAs, or route URLs.
- **Dataset & Database Integrity**: Zero changes to the 417 source temple JSON files, `qdrant_db/`, `bm25_index/`, or `evaluation/`.

---

## 2. End-to-End Architecture

```text
User Query
    ↓
/chat Endpoint (FastAPI)
    ↓
MasterAgentCoordinator
    ↓
AgentRouter (Deterministic Keyword & Regex Classification)
    ↓ (live_navigation)
LiveNavigationAgent (BaseAgent lifecycle)
    ├── Parameter Extraction (Origin, Destination, Travel Mode)
    ├── Location Resolution
    │     ├── Canonical Temples & Aliases → TempleCoordinateRegistry (lat, lng)
    │     └── Non-temple Cities/Places   → Address string waypoint
    ↓
NavigationAdapter (BaseExternalAdapter)
    ├── Circuit Breaker & Timeout Protection (connect=3.0s, read=5.0s)
    ├── Header Secret Sanitization (X-Goog-Api-Key)
    ├── Explicit FieldMask (routes.duration, routes.distanceMeters, etc.)
    ↓
Google Maps Routes API v2 (POST https://routes.googleapis.com/directions/v2:computeRoutes)
    ↓
NavigationResult Normalization (Distance in km, Duration in hrs/mins, Traffic info)
    ↓
AgentResponse (Factual Markdown Sections + Structured Metadata)
    ↓
ResponseAggregator / MultiIntentPipeline
    ↓
ChatResponse
```

---

## 3. NavigationAdapter Specification

`NavigationAdapter` resides in `backend/app/agents/adapters/navigation_adapter.py` and implements:

1. **Protocol**: Subclasses `BaseExternalAdapter`.
2. **Endpoint**: `https://routes.googleapis.com/directions/v2:computeRoutes`
3. **FieldMask**:
   `routes.duration,routes.distanceMeters,routes.description,routes.staticDuration`
4. **Waypoints**:
   - Registered temple coordinates: `{"location": {"latLng": {"latitude": lat, "longitude": lng}}}`
   - Address string: `{"address": "Hyderabad"}`
5. **Travel Modes Supported**:
   - `DRIVE` (driving / car)
   - `WALK` (walking / on foot)
   - `BICYCLE` (bicycle / cycling)
   - If `TRANSIT` is requested: Raises `UnsupportedTravelModeError` with a controlled response indicating TRANSIT is not currently supported by this endpoint configuration, rather than silently substituting driving.
6. **Secret Sanitization**:
   - The `X-Goog-Api-Key` header is classified as a sensitive header and stripped from all log outputs, error strings, and diagnostic traces.

---

## 4. Location & Coordinate Resolution

`LiveNavigationAgent` resolves locations deterministically:
1. **Registered Temples**: Queried against `TempleCoordinateRegistry`. If matched (e.g. `Yadagirigutta` or `Yadadri`), precise coordinates `(17.5898, 78.9392)` are returned as lat/lng waypoints.
2. **Cities and Non-Temple Origins**: Validated non-temple places (e.g., `Hyderabad`, `Secunderabad`, `Warangal`, `Vijayawada`) are passed as address string waypoints to the provider.
3. **Clarification on Missing / Ambiguous Destinations**: If no destination is identified or both origin and destination are empty, the agent asks for clarification rather than guessing a location.

---

## 5. Routing Protection & Sub-Intent Hierarchy

To avoid routing collisions between navigation, comparisons, itineraries, and multi-intent queries:

1. **Multi-Place Distance Inquiries**:
   - `How far is Yadadri from Basara?` → classified as `live_navigation`.
   - `Route from Hyderabad to Yadadri` → classified as `live_navigation`.
2. **Comparison Preservation**:
   - `Compare the distance between Yadadri and Basara.` → classified as `comparison` (comparison keywords take precedence).
   - `Compare travel information between Yadadri and Basara.` → classified as `comparison`.
3. **Itinerary Preservation**:
   - `Plan a route itinerary for Yadadri and Basara` → classified as `itinerary_planning` (bare "route" inside an itinerary request is preserved for itinerary planning).
4. **Multi-Intent Support**:
   - `Weather and route to Yadadri from Hyderabad` → decomposed into `["live_weather", "live_navigation"]`.
   - `Budget and travel route to Yadadri` → decomposed into `["budget", "live_navigation"]`.

---

## 6. Dependency Injection

In `backend/app/agents/coordinator.py`:
- `MasterAgentCoordinator.__init__` accepts `live_navigation_agent: Optional[Any] = None`.
- If not supplied, defaults to `None`.
- Zero auto-instantiation ensures complete backward compatibility and prevents accidental network calls in existing test suites.

---

## 7. Verification & Certification

### 7.1 Test Suite Breakdown
- **Phase O5 Suite (`tests/test_live_navigation_agent.py`)**: **52 tests, 100% passing**
  - Adapter lifecycle, request building, FieldMask headers.
  - Coordinate resolution (temple registry + address waypoints).
  - Zero-credential handling (`NavigationCredentialMissingError`).
  - Travel modes (`DRIVE`, `WALK`, `BICYCLE`, and controlled rejection of unsupported `TRANSIT`).
  - Zero-fabrication enforcement (no speed calculations, no manufactured traffic, no fake URLs).
  - Routing classification & multi-intent decomposition.
  - Coordinator dependency injection & conversation memory integration.
- **Phase O1/O2 Suite (`test_external_adapter.py`, `test_temple_coordinate_registry.py`)**: 34 tests passing.
- **Phase O3 Suite (`test_live_weather_agent.py`)**: 46 tests passing.
- **Phase O4 Suite (`test_budget_agent.py`)**: 55 tests passing.
- **Agent Router Suite (`test_agent_router.py`)**: 13 tests passing.
- **Total Certified Tests**: **511 tests passing across the entire regression suite**.

### 7.2 Dataset & Index Integrity
- 417/417 temple source JSON files verified byte-for-byte SHA-256 identical (0 modifications).
- `qdrant_db/` unchanged.
- `bm25_index/` unchanged.
- `evaluation/` unchanged.
