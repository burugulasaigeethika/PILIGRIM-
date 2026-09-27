# Phase O3 — Live Weather Agent Documentation

## 1. Objective & Scope

Phase O3 introduces the **`LiveWeatherAgent`** to the PilgrimAI ecosystem, providing real-time weather observations and pilgrimage-oriented forecasts for canonical temples.

**Key Boundaries**:
- **Strict Scope**: Implements ONLY `LiveWeatherAgent`. Does NOT implement `BudgetAgent` (O4), `LiveNavigationAgent` (O5), `VoiceMultilingualAgent` (O6), or broader Phase O7 integrations.
- **Provider**: Powered by Open-Meteo (Free API, CC BY 4.0 attribution, zero API keys or credentials required).
- **External API Firewall**: All HTTP communication is strictly routed through `BaseExternalAdapter` (O1 Firewall) with bounded timeouts, max-1 retry, and circuit breaker protection.
- **Coordinate Registry**: All geographical locations are resolved via `TempleCoordinateRegistry` (O2 Registry) without modifying any of the 417 source temple JSON files.
- **Data & Model Safety**: Zero modifications to Qdrant, BM25, evaluation datasets, or source temple JSON files; zero model downloads to `C:\` or `D:\`.

---

## 2. End-to-End Architecture

```text
User Query
    ↓
/chat Endpoint (FastAPI)
    ↓
MasterAgentCoordinator
    ↓
AgentRouter (Deterministic Keyword & Intent Classifier)
    ↓
LiveWeatherAgent (name="live_weather", BaseAgent lifecycle)
    ↓
TempleCoordinateRegistry (Resolves canonical name & aliases → lat/lon)
    ↓
BaseExternalAdapter (Connect/Read timeouts, Max-1 retry, Circuit breaker, Secret sanitization)
    ↓
Open-Meteo v1 Forecast API (https://api.open-meteo.com/v1/forecast)
    ↓
Deterministic Normalization (WMO condition mapping, metric units: °C, mm, km/h)
    ↓
AgentResponse (Factual weather observations + practical pilgrimage guidance)
    ↓
ResponseAggregator
    ↓
ChatResponse (FastAPI JSON response)
```

---

## 3. Open-Meteo Integration & Attribution

- **Endpoint**: `https://api.open-meteo.com/v1/forecast`
- **Authentication**: None required (Free tier for non-commercial pilgrimage assistance).
- **Timezone**: `Asia/Kolkata` (Indian Standard Time).
- **Attribution**:
  - `Weather data by Open-Meteo.com under CC BY 4.0`
  - Explicitly surfaced in response markdown text, sources array, and response metadata.

---

## 4. Location & Coordinate Resolution

`LiveWeatherAgent` resolves temples using `TempleCoordinateRegistry`:
1. Checks routing metadata for pre-extracted canonical temple names (`detected_temple` / `detected_temples`).
2. Scans user query against canonical names and aliases (e.g., `Yadagirigutta` → `Yadadri`, `Visa Balaji` → `Chilkur`, `Vana Durga Bhavani` → `Edupayala`).
3. Fetches immutable `TempleCoordinate` containing validated latitude `[-90.0, 90.0]` and longitude `[-180.0, 180.0]`.
4. **Anti-Hallucination Rejection**: If a location cannot be resolved or is unregistered, the agent immediately returns a controlled unavailable response. It **never** guesses coordinates or silently substitutes Hyderabad or another city.

---

## 5. Weather Normalization & WMO Condition Mapping

### 5.1 Weather Metrics Normalized
- **Current Weather**:
  - Temperature: Celsius (°C)
  - Relative Humidity: Percentage (%)
  - Precipitation: Millimeters (mm)
  - Rain: Millimeters (mm)
  - Wind Speed: km/h (with wind direction in degrees)
  - Weather Code: WMO numeric code
  - Condition: Human-readable condition description
- **Daily Forecast (7 Days)**:
  - Max Temperature (°C)
  - Min Temperature (°C)
  - Precipitation Sum (mm)
  - Precipitation Probability Max (%)
  - Sunrise & Sunset (ISO-8601 strings)
- **Hourly Forecast**:
  - Temperature, precipitation probability, wind speed preview.

### 5.2 Deterministic WMO Code Mapping
The agent converts numeric WMO weather codes into human-readable descriptions without using an LLM:
- `0`: Clear sky
- `1`: Mainly clear
- `2`: Partly cloudy
- `3`: Overcast
- `45`, `48`: Fog / Depositing rime fog
- `51`, `53`, `55`: Light / Moderate / Dense drizzle
- `61`, `63`, `65`: Slight / Moderate / Heavy rain
- `80`, `81`, `82`: Slight / Moderate / Violent rain showers
- `95`, `96`, `99`: Thunderstorm / Thunderstorm with hail
- **Unmapped/Unknown Codes**: Safely default to `"Unknown weather condition"` without raising exceptions.

---

## 6. Separation: Weather Facts vs Practical Pilgrimage Advice

The agent strictly distinguishes between provider-observed facts and pilgrimage guidance:

### 🌤️ Live Weather Facts
- Directly reflects Open-Meteo values (`Temperature: 31.5°C`, `Condition: Partly cloudy`, `Rain: 0.0 mm`, `Wind: 12.4 km/h`).

### 💡 Practical Pilgrimage Advice
Derived deterministically based on conservative thresholds:
- **Rain/Precipitation**: If `precip_sum > 0.5 mm` or `precip_probability >= 40%`, advise carrying an umbrella or light raincoat.
- **Heat**: If `max_temperature >= 34°C`, advise staying hydrated and planning darshan for cooler morning or evening hours.
- **Cold**: If `min_temperature <= 17°C`, advise carrying light layers/shawls for early morning darshan/suprabhatam.
- **Fog/Visibility**: If fog codes `45/48` are present, advise allowing extra travel time for road transit.
- **Thunderstorms**: If thunderstorm codes `95/96/99` are present, advise seeking indoor shelter on temple premises.
- **General**: Remind pilgrims of dress code and queue timings.
- **Medical/Safety Prohibitions**: Zero medical claims; zero absolute safety/risk claims.

---

## 7. In-Process Caching & Honest Metadata

- **TTL**: Configurable (default 600 seconds / 10 minutes).
- **Cache Key**: `f"{canonical_temple_name.lower()}:{forecast_days}"`.
- **Honest Metadata**:
  - `cache_hit`: `true` for cached responses; `false` for fresh provider fetches.
  - `retrieved_at`: Exact UTC ISO-8601 timestamp when data was fetched from Open-Meteo.
  - `forecast_timestamp`: Provider observation timestamp.
  - Responses never claim to be "retrieved just now" when served from cache.
- `clear_cache()` is provided for deterministic unit testing.

---

## 8. Controlled Failure & Zero Fabricated Weather

If Open-Meteo or network connectivity fails (timeout, HTTP 429, HTTP 5xx, connection error, or circuit open):
- The agent catches typed exceptions from `BaseExternalAdapter`.
- Returns a controlled failure response:
  ```text
  Live weather data for {Temple} is currently unavailable. Please try again shortly.
  ```
- **Zero Fabricated Weather**: No estimated temperatures, no simulated rain numbers, no silent fallback to static RAG documents.

---

## 9. Router Integration & Priority Preservation

### 9.1 Multi-Intent Protection (Non-Swallowing Rule)
- Weather patterns (`weather`, `temperature`, `forecast`, `rain`, `climate`, `humidity`) are added to `_sub_intent_patterns` alongside `itinerary`, `budget`, `timings`, `travel`, etc.
- Queries combining multiple intents (e.g. *"What is the weather in Yadadri and plan a one-day visit?"* or *"weather in Basara and what will the trip cost?"*) are recognized as `multi_intent` (Priority 6) and decomposed sequentially by `SequentialMultiIntentPipeline`. They are **never** swallowed by `LiveWeatherAgent`.

### 9.2 Priority Hierarchy in `AgentRouter`
1. Empty / Whitespace Query → `unsupported`
2. Explicit Unsupported Temple → `unsupported`
3. Explicit Comparison Intent (`compare`, `vs`, multi-temple) → `comparison`
4. Itinerary Planning Intent (`plan visit`, `itinerary`) → `itinerary_planning`
5. Cross-Temple Aggregation Intent (`which temples`, `list all temples`) → `cross_temple_aggregation`
6. Conjoined Multi-Intent (`and`, `also`, `&` with >= 2 sub-intents) → `multi_intent`
7. **Single-Temple Live Weather Intent** (`weather` keyword with exactly 1 registered temple) → `weather` (target: `LiveWeatherAgent`)
8. Single-Temple Factual Information → `temple_information`
9. Ambiguous Temple Query (Keywords present, temple missing) → `clarification`
10. Out-of-Scope Query → `unsupported`

Existing comparison queries (*"Compare the weather of Basara and Yadadri"*, *"Srisailam vs Bhadrachalam accommodation"*) and multi-temple itineraries (*"Plan an itinerary for Basara and Vemulavada"*) remain 100% intact.

---

## 10. MasterAgentCoordinator Integration

- Follows the **Critical Dependency-Injection Rule**:
  `MasterAgentCoordinator.__init__` accepts `live_weather_agent: Optional[Any] = None`.
- **Zero Auto-Creation**: The coordinator does NOT auto-instantiate `LiveWeatherAgent`. When initialized without a weather agent, `live_weather` is not registered.
- Dynamic registration is supported via `coordinator.register_agent(agent)`.
- Existing coordinator tests continue to run completely unaffected.

---

## 11. Test Coverage & Certification

A dedicated suite of 46 tests was created in `tests/test_live_weather_agent.py`:

| Category | Tests | Description |
| :--- | :---: | :--- |
| **Agent Contract** | 5 | Inheritance, agent name, lifecycle execution, empty & whitespace handling |
| **Location Resolution** | 4 | Canonical lookup, alias resolution, unknown temple rejection, missing coordinate safety |
| **Current Normalization** | 7 | Temperature, humidity, precipitation, rain, wind, WMO codes, unknown code fallback |
| **Hourly Forecast** | 5 | Hourly temperature, precipitation probability, precipitation, wind, weather codes |
| **Daily Forecast** | 6 | Daily max/min temp, precipitation sum, rain probability, sunrise, sunset |
| **Reliability & Firewall** | 8 | 500 server error, timeout, connection failure, cache hit, cache miss, cache metadata, secret sanitization |
| **Deterministic Routing** | 6 | Single-intent weather, inactive agent routing, multi-intent preservation (weather+itinerary, weather+budget), comparison protection, itinerary protection |
| **Pipeline Execution** | 1 | Sequential execution of weather + itinerary |
| **Coordinator DI** | 4 | No auto-instantiation, explicit injection, dynamic registration, end-to-end weather execution |
| **Total** | **46** | **All 46 Passed (100% Green, 0 Failures)** |

---

## 12. Verified Regression Results

| Suite | Tests | Result |
| :--- | :---: | :---: |
| **O3 Live Weather Agent** (`tests/test_live_weather_agent.py`) | 46 | **46/46 PASSED** |
| **O1 External Adapter** (`tests/test_external_adapter.py`) | 18 | **18/18 PASSED** |
| **O2 Coordinate Registry** (`tests/test_temple_coordinate_registry.py`) | 16 | **16/16 PASSED** |
| **Legacy Cross-Temple Aggregation** (`tests/test_cross_temple_aggregation.py`) | 13 | **13/13 PASSED** |
| **Phase A–N + Post-Phase-N Modern Suites** (15 test suites) | 311 | **311/311 PASSED** |
| **Combined Total** | **404** | **404/404 PASSED (100% Green)** |

---

## 13. Controlled Live Smoke Test Result

A controlled live network smoke test against Open-Meteo was executed using `Yadadri` coordinates:
- **Result**: `SMOKE TEST RESULT: PASS`
- **Target Coordinates**: Yadadri (`17.587714, 78.948325`)
- **Observed Metrics**: `Temperature: 31.1°C`, `Condition: Overcast`
- **Attribution Verified**: `Weather data by Open-Meteo.com under CC BY 4.0`
- **Credentials Used**: None (0 API keys used or leaked)

---

## 14. Data Integrity Audit

- **417 Source Temple JSON Files**: Verified 100% byte-for-byte identical via SHA-256 pre/post hashing (0 files modified).
- **Qdrant**: `qdrant_db/` unchanged (0 mutations, no re-indexing).
- **BM25**: `bm25_index/` unchanged (0 mutations, no re-indexing).
- **Evaluation**: `evaluation/` unchanged.
- **Protected Files**: `backend/app/rag/`, `backend/app/api/chat.py`, `backend/app/main.py`, `.env`, `frontend/` completely untouched.

---

## 15. Summary of Modified & Created Files

### Files Created:
1. `backend/app/agents/live_weather_agent.py` — `LiveWeatherAgent` implementation.
2. `tests/test_live_weather_agent.py` — Comprehensive 46-test offline suite.
3. `docs/PHASE_O3_LIVE_WEATHER_AGENT.md` — Complete Phase O3 architectural and certification documentation.

### Files Modified:
1. `backend/app/agents/router.py` — Added weather pattern regexes, weather/budget sub-intents, and single-intent weather routing without swallowing multi-intent queries.
2. `backend/app/agents/coordinator.py` — Added optional `live_weather_agent` dependency injection and `register_agent()` method (strictly no auto-instantiation).

### Protected Unchanged Files:
- All 417 source temple JSON files.
- All RAG retrieval modules, models, databases, and evaluation files.
- `backend/app/api/chat.py` and `backend/app/main.py`.
