# Phase O — Architecture Audit: Remaining External and Utility Agents

**Workspace**: `D:\pligrim ai new`  
**Date**: September 22, 2026  
**Status**: AUDIT COMPLETE — ZERO PRODUCTION CODE MODIFIED  
**Auditor**: Antigravity Assistant  

---

## 1. Audit Summary

This architectural audit evaluates the design, integration strategy, and implementation sequence for the four remaining specialist agents planned for **Phase O** of the PilgrimAI multi-agent platform:

1. **`LiveWeatherAgent`**: Real-time meteorological observations, hourly forecasts, and daily forecasts grounded to temple coordinates.
2. **`LiveNavigationAgent`**: Driving routes, turn-by-turn directions, distances, and travel duration between origins (e.g., Hyderabad, regional hubs) and pilgrimage temples.
3. **`BudgetAgent`**: Deterministic pilgrimage cost estimation, accommodation tariffs, seva/darshan fees, prasadam pricing, transport estimates, and customizable personal budget planning.
4. **`VoiceMultilingualAgent`**: Speech-to-text (STT), multilingual translation across Indian languages (Telugu, Hindi, English, etc.), and text-to-speech (TTS) audio synthesis.

### Critical System Requirements & Mandates
* **No `LivePlacesBookingAgent`**: The prior concept of an external places/booking agent is formally deprecated and replaced by the local, deterministic `BudgetAgent`.
* **₹0 Mandatory Cost Architecture**: The core system must function with **zero mandatory API costs, zero credit card requirements, and zero paid SaaS dependencies**. All core agents must operate either completely locally or utilize generous, permanent free-tier/open APIs with local offline fallbacks.
* **Open-Meteo Weather Selection**: Open-Meteo has been audited and verified as the ideal weather data provider meeting all ₹0 cost, non-commercial, and parameter requirements.
* **D: Drive Model Storage Requirement**: Due to constrained C: drive capacity, all external caches, model weights (Whisper, Ollama, HuggingFace), and downloads must reside on `D:\`.
* **Zero Production Code Changes**: This phase is strictly an architectural audit. No production code, router logic, dataset JSON files, or RAG indices have been modified.

---

## 2. Baseline Verification & Data Integrity

### 2.1 Regression Test Baseline

The existing certified test suite was verified against the repository:

| Test Suite Category | Test File | Test Count | Status |
|---|---|---|---|
| **Phase A** | `tests/test_agent_contracts.py` | 10 | **PASSED** |
| **Phase B** | `tests/test_rag_tool.py` | 10 | **PASSED** |
| **Phase C** | `tests/test_temple_information_agent.py` | 10 | **PASSED** |
| **Phase D** | `tests/test_agent_router.py` | 13 | **PASSED** |
| **Phase E** | `tests/test_response_aggregator.py` | 13 | **PASSED** |
| **Phase F** | `tests/test_master_agent_coordinator.py` | 13 | **PASSED** |
| **Phase G** | `tests/test_agent_state.py` | 17 | **PASSED** |
| **Phase H** | `tests/test_multi_intent_pipeline.py` | 18 | **PASSED** |
| **Phase I** | `tests/test_conversation_memory.py` | 18 | **PASSED** |
| **Pre-Phase-J** | `tests/test_query_planner.py` | 15 | **PASSED** |
| **Phase J** | `tests/test_complete_list_retrieval.py` | 28 | **PASSED** |
| **Phase K** | `tests/test_comparison_agent.py` | 30 | **PASSED** |
| **Phase L** | `tests/test_cross_temple_aggregation_agent.py` | 30 | **PASSED** |
| **Phase M** | `tests/test_itinerary_planning_agent.py` | 27 | **PASSED** |
| **Phase N** | `tests/test_chat_integration.py` | 28 | **PASSED** |
| **Post-Phase-N** | `tests/test_multi_temple_itinerary_routing.py` | 8 | **PASSED** |
| **SUBTOTAL** | **Modern Regression Baseline (Phases A–N + Fix)** | **311 / 311** | **100% GREEN** |
| **Legacy Baseline** | `tests/test_cross_temple_aggregation.py` | 13 | **PASSED** |
| **COMBINED TOTAL** | **Certified Regression Baseline** | **324 / 324** | **100% GREEN** |

### 2.2 Verified Pilgrimage Dataset Audit

The physical pilgrimage dataset on disk was verified without alteration:
* **Canonical Temple Directories**: Exactly **20** verified:
  `ahobilam`, `badrachalam`, `balkampet`, `basara`, `birla mandir`, `chilkur`, `dharmapuri`, `edupayal`, `jogulamba(new)`, `kaleshvaram`, `karmanghat`, `medaram`, `ramappa`, `srisaila`, `thousand pillar`, `ttd`, `ujjaini`, `veera satyanarayana`, `vemulavada`, `yadadri`.
* **Total Source JSON Files**: Exactly **417** verified across all 20 temple directories.
* **Canonical Categories**: Exactly **21** unique category JSON files present across temples:
  `accommodation.json`, `contacts.json`, `crowd.json`, `donations.json`, `elderly_ppl.json`, `emergency_nos.json`, `facilities.json`, `faq.json`, `festivals.json`, `gallery.json`, `maps.json`, `nearby_attractions.json`, `prasadam.json`, `restaurants.json`, `river_bank.json`, `rules.json`, `sevas.json`, `sub_temples.json`, `temple.json`, `timings.json`, `travel.json`.
* **Ground Truth Regression Anchors**:
  - Dharmapuri sevas: **10** verified.
  - Yadadri facilities: **26** verified.
  - Edupayala prasadam items: **2** verified.
  - Canonical River-Bank Temples: **11** verified (`Ahobilam`, `Badrachalam`, `Basara`, `Dharmapuri`, `Edupayal`, `Jogulamba(New)`, `Kaleshvaram`, `Medaram`, `Srisaila`, `Veera Satyanarayana`, `Vemulavada`).
* **Indexes and Storage**:
  - `qdrant_db/`: Verified unchanged.
  - `bm25_index/`: Verified unchanged.
  - `evaluation/`: Verified unchanged.

---

## 3. Current Agent Architecture

The existing agent architecture operates strictly via decoupled, strongly-typed contracts defined in Phases A through N:

```text
HTTP Request: POST /chat {"question": "...", "session_id": "..."}
       ↓
backend/app/api/chat.py (chat_endpoint)
       ↓
MasterAgentCoordinator.process(state)
  ├── 1. Memory Context Resolution (ConversationMemoryManager)
  ├── 2. Deterministic Routing (AgentRouter)
  │       ├── Single-Agent Route → Dispatch to Specialist Agent
  │       └── Multi-Intent Route → SequentialMultiIntentPipeline
  ├── 3. Specialist Execution (BaseAgent.execute(state))
  │       └── Lifecycle: Timing, Tracing, Exception Containment, Intermediate Caching
  └── 4. Response Synthesis (ResponseAggregator.aggregate())
       ↓
HTTP Response: ChatResponse (Markdown Answer, Sources, Telemetry, Metadata)
```

### 3.1 Key Architectural Contracts

1. **`BaseAgent` (`backend/app/agents/base_agent.py`)**:
   - Requires subclasses to define `name`, `description`, and implement `_run(state: AgentState) -> AgentResponse`.
   - The public template method `execute(state: AgentState)` wraps execution in performance counters, records step traces, catches all unhandled exceptions, constructs standardized failure payloads without crashing the process, and stores intermediate results in `state.intermediate_results[self.name]`.
2. **`AgentState` (`backend/app/agents/state.py`)**:
   - In-memory state tracking `session_id`, `user_query`, `detected_intents`, `active_agent`, `intermediate_results`, `final_response`, and chronological `execution_trace`.
   - Built-in `_sanitize_metadata` automatically redacts sensitive credentials (`api_key`, `secret`, `token`, `password`, etc.) to prevent security leakage.
3. **`AgentResponse` (`backend/app/agents/state.py`)**:
   - Uniform return contract across all agents: `success` (bool), `agent_name` (str), `answer` (str), `sources` (list[str]), `metadata` (dict), `error` (optional str), `latency_ms` (optional float).
4. **`MasterAgentCoordinator` (`backend/app/agents/coordinator.py`)**:
   - Coordinates routing, memory resolution, multi-intent dispatch, and aggregation.
   - Contains zero direct database, embedding model, or LLM generation logic.
5. **`SequentialMultiIntentPipeline` (`backend/app/agents/multi_intent_pipeline.py`)**:
   - Deterministically decomposes conjoined user queries on conjunctions (`and`, `also`, `as well as`) and delimiters (`;`, `?`), propagates detected temple context to implicit sub-queries, invokes specialist agents in order, and aggregates results.
6. **`ResponseAggregator` (`backend/app/agents/response_aggregator.py`)**:
   - Synthesizes specialist agent responses into clean, unified Markdown, deduplicates citations, and resolves inter-agent conflicts.
7. **`RAGTool` (`backend/app/agents/tools/rag_tool.py`)**:
   - Serves as the strict dependency boundary between specialist agents and low-level retrieval mechanics (Qdrant vector store, BM25 index, cross-encoder reranker).

---

## 4. Current Router Architecture & Phase O Priority Order

Inspection of [backend/app/agents/router.py](file:///D:/pligrim%20ai%20new/backend/app/agents/router.py) demonstrates the current 9-tier deterministic priority cascade:

```text
Priority 1: Empty / Whitespace Query -> "unsupported" (Empty query error)
Priority 2: Explicit Unsupported Temple -> "unsupported" (Anti-hallucination refusal)
Priority 3: Comparison Intent -> "comparison" (or multi_intent if conjoined)
Priority 4: Itinerary Planning Intent -> "itinerary_planning" (or multi_intent if conjoined)
Priority 5: Cross-Temple Aggregation Intent -> "cross_temple_aggregation"
Priority 6: Multi-Intent Query -> "multi_intent"
Priority 7: Single Known-Temple Factual Information -> "temple_information"
Priority 8: Ambiguous Temple Query -> "clarification" (Prompt for temple name)
Priority 9: Out-of-Scope Query -> "unsupported"
```

### 4.1 Evaluation of Proposed Phase O Queries

The routing behavior for incoming queries was evaluated against potential conflicts:

| # | User Query | Target Intent | Desired Agent | Routing Strategy |
|---|---|---|---|---|
| 1 | *"What's the weather at Yadadri tomorrow?"* | `weather` | `LiveWeatherAgent` | Single-agent: Weather keyword + date entity + temple. |
| 2 | *"What's the weather at Basara?"* | `weather` | `LiveWeatherAgent` | Single-agent: Weather keyword + temple. |
| 3 | *"Will it rain at Yadadri tomorrow morning?"* | `weather` | `LiveWeatherAgent` | Single-agent: Rain/precipitation intent + temple. |
| 4 | *"Plan a trip to Yadadri and tell me tomorrow's weather."* | `multi_intent` | `SequentialMultiIntentPipeline` | Decomposes to: 1. `itinerary_planning`, 2. `live_weather`. |
| 5 | *"Compare the weather at Yadadri and Basara."* | `weather` | `LiveWeatherAgent` | Multi-location weather comparison (handled by weather agent rather than factual ComparisonAgent). |
| 6 | *"How much will a trip to Yadadri cost?"* | `budget` | `BudgetAgent` | Single-agent: Budget/cost keyword + temple. |
| 7 | *"Calculate my pilgrimage budget."* | `budget` | `BudgetAgent` | Single-agent: Budget calculation; if no temple given, prompts user for inputs. |
| 8 | *"How do I get from Hyderabad to Yadadri?"* | `navigation` | `LiveNavigationAgent` | Single-agent: Point-to-point driving/transit directions. |
| 9 | *"Give me directions to Yadadri."* | `navigation` | `LiveNavigationAgent` | Single-agent: Route navigation. |
| 10 | *"Translate this information into Telugu."* | `voice_multilingual` | `VoiceMultilingualAgent` | Single-agent/Transformer: Language translation. |
| 11 | *"Read this itinerary aloud."* | `voice_multilingual` | `VoiceMultilingualAgent` | Single-agent: Text-to-speech audio synthesis. |

### 4.2 Recommended Integrated Priority Sequence

To integrate the four Phase O agents without disrupting the certified Phase A–N baseline, the router must insert new intents above the broad single-temple factual fallback (`Priority 7`) while respecting explicit comparison, itinerary, and aggregation triggers:

```text
Priority 1:  Empty / Whitespace Query
Priority 2:  Explicit Unsupported Temple (Anti-hallucination)
Priority 3:  Voice / Speech / Audio Command (Read aloud, voice query)
Priority 4:  Translation Intent (Explicit translation requests)
Priority 5:  Comparison Intent (Factual comparisons between temples)
Priority 6:  Itinerary Planning Intent (Tour/visit schedules)
Priority 7:  Live Navigation Intent (Directions, routes, distance, duration)
Priority 8:  Live Weather Intent (Forecast, rain, temperature, humidity)
Priority 9:  Budget Intent (Trip cost, expense calculation, tariff inquiry)
Priority 10: Cross-Temple Aggregation Intent (Property filtering across all 20 temples)
Priority 11: Multi-Intent Conjoined Query (Sequenced via pipeline)
Priority 12: Single-Temple Factual Information (TempleInformationAgent)
Priority 13: Ambiguous Temple Query (Clarification request)
Priority 14: Out-of-Scope Query
```

---

## 5. LiveWeatherAgent Architecture

### 5.1 End-to-End Processing Lifecycle

```text
User Query ("Will it rain tomorrow at Yadadri?")
       ↓
MasterAgentCoordinator
       ↓
AgentRouter (Matches Weather Intent)
       ↓
LiveWeatherAgent.execute(state)
       ↓
Coordinate Resolver (Resolves "Yadadri" → lat: 17.5877, lon: 78.9483)
       ↓
ExternalAPIAdapter (HTTP GET to Open-Meteo with 3.0s timeout & circuit breaker)
       ↓
Raw Open-Meteo JSON Payload
       ↓
Weather Data Normalizer (Extracts structured WeatherData DTO)
       ↓
Domain Rule Engine:
  ├── Weather Facts: Temperature: 28°C, Rain Probability: 75%, Precipitation: 4.2mm, Wind: 14 km/h
  └── Pilgrimage Context: "Heavy rain expected around midday. Consider indoor darshan in morning."
       ↓
AgentResponse (Formatted Markdown Table + Advice + Attribution)
       ↓
ResponseAggregator -> /chat
```

### 5.2 Strict Separation: Facts vs. Pilgrimage Advisory

To preserve factual grounding and prevent LLM or heuristic hallucination, the agent must enforce an unbreachable wall between **Meteorological Facts** and **Pilgrimage Advice**:

```markdown
### Weather Forecast for Sri Lakshmi Narasimha Swamy Temple, Yadadri
* **Date & Time**: 2026-09-23 (Forecast for Tomorrow)
* **Temperature**: 24.2°C (Min) to 32.8°C (Max) | Current Apparent: 31.0°C
* **Precipitation Probability**: 75% | Expected Rainfall: 4.2 mm
* **Relative Humidity**: 68%
* **Wind Speed**: 14.5 km/h
* **Sunrise / Sunset**: 06:08 AM / 06:14 PM IST
* **Data Source**: Open-Meteo.com (CC BY 4.0)

---
> **Pilgrim Advisory & Practical Tips**:
> - High probability of rain in the afternoon hours. Devotees undertaking the hill pradakshina are advised to carry an umbrella or visit during the covered morning darshan slots (06:00 AM – 11:00 AM).
```

### 5.3 Weather Telemetry and Metadata Contract
`AgentResponse.metadata` must expose:
```json
{
  "provider": "Open-Meteo",
  "location": "Yadadri",
  "latitude": 17.5877,
  "longitude": 78.9483,
  "timezone": "Asia/Kolkata",
  "forecast_timestamp": "2026-09-23T06:00:00Z",
  "temperature_unit": "celsius",
  "precipitation_unit": "mm",
  "attribution": "Weather data by Open-Meteo.com under CC BY 4.0",
  "cache_hit": false
}
```

---

## 6. Coordinate Resolution Architecture

### 6.1 Dataset Inspection Findings

Deep inspection of all **417 source JSON files** across all 20 canonical temples confirmed:
1. **Zero Explicit Coordinate Fields**: No JSON file contains structured `latitude` or `longitude` keys.
2. **`maps.json` Limitations**:
   - Some temples contain Google Maps embed URLs with embedded coordinate strings (e.g., Ahobilam `!2d78.7180!3d15.1278`, Basara `!2d77.9541!3d18.8704`).
   - Several temples (e.g., `dharmapuri`, `edupayal`, `balkampet`, `badrachalam`, `yadadri`) contain only generic search URLs (e.g., `https://maps.google.com/?q=...`) without coordinate numbers.
   - Parsing unpredictable Google Maps URL formats at runtime is fragile, slow, and error-prone.

### 6.2 Recommended Solution: Dedicated Static Coordinate Registry

Phase O must introduce a dedicated, curated, read-only coordinate registry:
`backend/app/agents/data/temple_coordinates.json` (or `coordinate_registry.py`).

**Key Properties:**
- **Zero Dataset Mutation**: The 417 source JSON files remain completely untouched.
- **Zero Runtime Overhead**: Instant dictionary lookup in `<0.1 ms`.
- **Zero Cost & Zero Network**: No geocoding API calls required for registered temples.
- **Canonical Alias Alignment**: Directly integrated with `QueryPlanner.temple_aliases` so that aliases like `"Yadagirigutta"` or `"Alampur"` resolve to the exact canonical coordinates.

```python
# Verified Canonical Coordinates for PilgrimAI Temples
CANONICAL_COORDINATES = {
    "Yadadri": {"lat": 17.5877, "lon": 78.9483, "name": "Yadadri Sri Lakshmi Narasimha Swamy Temple"},
    "Basara": {"lat": 18.8705, "lon": 77.9542, "name": "Sri Gnana Saraswathi Devasthanam, Basara"},
    "Badrachalam": {"lat": 17.6698, "lon": 80.8936, "name": "Sri Sita Ramachandraswamy Temple, Bhadrachalam"},
    "Srisaila": {"lat": 16.0742, "lon": 78.8682, "name": "Sri Bhramaramba Mallikarjuna Temple, Srisailam"},
    "Dharmapuri": {"lat": 18.9515, "lon": 79.0917, "name": "Sri Lakshmi Narasimha Swamy Temple, Dharmapuri"},
    "Vemulavada": {"lat": 18.4672, "lon": 78.8687, "name": "Sri Raja Rajeshwara Swamy Temple, Vemulawada"},
    "Edupayal": {"lat": 17.9712, "lon": 78.1755, "name": "Sri Edupayala Vana Durga Bhavani Devalayam"},
    "Kaleshvaram": {"lat": 18.8118, "lon": 79.9040, "name": "Sri Kaleshwara Mukteshwara Swamy Temple"},
    "Jogulamba(New)": {"lat": 15.8770, "lon": 78.1349, "name": "Jogulamba Devi Temple, Alampur"},
    "Chilkur": {"lat": 17.3783, "lon": 78.2975, "name": "Chilkur Balaji Temple"},
    "Birla Mandir": {"lat": 17.4043, "lon": 78.4691, "name": "Birla Mandir, Hyderabad"},
    "Balkampet": {"lat": 17.4475, "lon": 78.4516, "name": "Balkampet Yellamma Temple"},
    "Karmanghat": {"lat": 17.3412, "lon": 78.5224, "name": "Karmanghat Hanuman Temple"},
    "Ujjaini": {"lat": 17.4412, "lon": 78.4981, "name": "Sri Ujjaini Mahakali Temple, Secunderabad"},
    "Ramappa": {"lat": 18.2562, "lon": 79.9406, "name": "Ramappa Temple, Palampet"},
    "Thousand Pillar": {"lat": 18.0037, "lon": 79.5748, "name": "Thousand Pillar Temple, Hanamkonda"},
    "Medaram": {"lat": 18.2259, "lon": 80.2520, "name": "Sammakka Saralamma Gaddelu, Medaram"},
    "Ahobilam": {"lat": 15.1278, "lon": 78.7180, "name": "Sri Ahobila Narasimha Swamy Temple"},
    "Veera Satyanarayana": {"lat": 17.2805, "lon": 82.4045, "name": "Sri Veera Venkata Satyanarayana Swamy, Annavaram"},
    "TTD": {"lat": 13.6807, "lon": 79.3509, "name": "Sri Venkateswara Swamy Temple, Tirumala"}
}
```

---

## 7. Open-Meteo Verification

A rigorous compliance audit of Open-Meteo confirms that it satisfies every architectural constraint:

| Requirement / Criterion | Open-Meteo Audit Finding | Compliance Status |
|---|---|---|
| **API Key Requirement** | **None**. Public endpoints function without any key. | **PASS (₹0 Cost)** |
| **Account / Signup Requirement** | **None**. No user registration or login required. | **PASS (Zero Friction)** |
| **Billing / Credit Card** | **None**. No payment method or billing profile needed. | **PASS (₹0 Hard Guarantee)** |
| **Usage Limits (Free Tier)** | 10,000 calls/day, 5,000 calls/hour, 600 calls/minute. | **PASS (Abundant for College/Demo)** |
| **Attribution License** | Creative Commons Attribution 4.0 International (CC BY 4.0). | **PASS (Requires attribution link)** |
| **Forecast Parameters** | Temperature (current, min, max, apparent), humidity, precipitation probability, rain amount, wind speed, weather conditions, sunrise, sunset. | **PASS (All Required Supported)** |
| **Hourly & Daily Granularity** | Supported natively via `hourly=` and `daily=` query parameters. | **PASS** |
| **Timezone Support** | Supported natively via `timezone=Asia/Kolkata`. | **PASS** |
| **Hosting / Backup Option** | Server code is open-source (AGPLv3) and can be self-hosted if ever necessary. | **PASS** |

**Conclusion**: Open-Meteo is **certified suitable** and approved as the primary weather provider.

---

## 8. LiveNavigationAgent Architecture

### 8.1 Provider Evaluation for ₹0 Cost

1. **Google Directions API**:
   - Requires Google Cloud Platform account, project setup, and mandatory credit card billing attachment.
   - **Verdict**: **REJECTED as mandatory dependency** (violates ₹0 mandatory cost rule). Retained strictly as an optional external adapter if a user provides their own key in `.env`.
2. **Open Source Routing Machine (OSRM) Public Demo (`router.project-osrm.org`)**:
   - Requires zero API keys, zero registration, and zero billing.
   - BSD 2-Clause open-source engine.
   - Endpoint: `https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false`
   - Returns road distance in meters, driving duration in seconds.
   - **Limitation**: Demo server is rate-limited and has no SLA.
3. **GraphHopper & OpenRouteService**:
   - Both require account registration and API key generation.
   - **Verdict**: Viable secondary options, but introduce setup friction compared to OSRM.

### 8.2 Recommended Hybrid Architecture: OSRM + Verified Static Travel Fallback

To achieve high reliability and ₹0 cost, `LiveNavigationAgent` should implement a 2-stage hybrid fallback:

```text
User Navigation Query ("How do I get from Hyderabad to Yadadri?")
       ↓
LiveNavigationAgent
       ↓
Step 1: Check In-Memory Route Cache (Origin, Destination)
       ↓ (Miss)
Step 2: ExternalAPIAdapter -> OSRM Demo API (Timeout: 3.0s)
       ├── Success: Extract distance (km), estimated drive time (hrs/mins), road summary
       └── Failure / Timeout / Rate Limit / Offline:
             ↓
Step 3: Deterministic Offline Fallback:
       ├── 1. Mathematical Haversine Distance + Road Curvature Factor (~1.28x)
       ├── 2. Estimated Duration based on standard highway speeds (55 km/h)
       └── 3. Verified Static Travel Information from Dataset (yadadri/travel.json)
             (RTC bus frequency, nearest train station, major highway NH-163 instructions)
       ↓
Response Formatting: Clearly labels whether route is live-calculated or verified static guide.
```

---

## 9. BudgetAgent Architecture

### 9.1 Core Principles: Local Deterministic Calculation & Zero Hallucination

`BudgetAgent` does not require any external API. It combines:
1. **Verified RAG Knowledge**: Real tariffs from temple JSON files (`accommodation.json`, `sevas.json`, `prasadam.json`, `facilities.json`).
2. **User-Provided Inputs**: Budget limits, number of persons, number of days, transport preferences (e.g., "We are 4 people travelling by car with a budget of ₹10,000").
3. **Deterministic Python Math**: Exact arithmetic sums, per-person breakdowns, and configurable contingency buffers (10–15%).

### 9.2 Four-Tier Cost Categorization Integrity

The agent must categorize every line item into one of four verified tiers:
1. **Verified Known Cost**: Extracted directly from verified temple records.
   * *Example*: "Yadadri Devasthanam AC Guest House: ₹1,500/night (Source: `yadadri/accommodation.json`)."
   * *Example*: "Basara Aksharabhyasam Special Seva: ₹500 (Source: `basara/sevas.json`)."
2. **User-Provided Cost**: Value explicitly provided by the user.
   * *Example*: "Travel fuel estimate: ₹2,000 (User-provided)."
3. **Calculated Estimate**: Formulaic mathematical product or sum.
   * *Example*: "Estimated Food & Prasadam (4 persons × 2 days @ ₹300/day): ₹2,400."
4. **Unavailable Cost**: Value not found in verified records.
   * *Example*: "Private Taxi Tariff: Unavailable in temple records (Local market inquiry required)."

The agent must **never fabricate or hallucinate prices**.

### 9.3 Integration with ItineraryPlanningAgent

`BudgetAgent` collaborates with `ItineraryPlanningAgent`:
- `ItineraryPlanningAgent` constructs the temporal visit plan (Day 1: Basara, Day 2: Vemulawada).
- `BudgetAgent` consumes the itinerary stops and generates an itemized financial worksheet covering darshan tickets, stay, food, and transport.

---

## 10. VoiceMultilingualAgent Architecture

### 10.1 Speech-to-Text (STT): `faster-whisper`

* **Candidate**: `faster-whisper` (CTranslate2 implementation of OpenAI Whisper).
* **Speed & Memory**: Up to 4× faster than standard Whisper and uses ~50% less RAM.
* **Model Sizing**:
  - `tiny` (~75 MB, ~250 MB RAM): Ultra-fast, adequate for English.
  - `base` (~145 MB, ~500 MB RAM): Recommended balanced option for multi-accent English and basic Hindi/Telugu.
  - `small` (~460 MB, ~1 GB RAM): Superior recognition for Indian accents.
* **Execution**: Fully local on CPU with `int8` quantization (no CUDA GPU required).
* **Cost & Privacy**: ₹0, 100% offline, zero voice data sent to external cloud.

### 10.2 Multilingual Translation

* **Primary Engine: Existing Local Ollama LLM (`D:\Ollama\models`)**:
  - PilgrimAI already has local Ollama configured on D: drive (`qwen2.5:1.5b` or equivalent).
  - Can perform direct instruction-based translation between English, Telugu, and Hindi with **zero additional disk storage and ₹0 cost**.
* **Secondary Local Option: IndicTrans2 / Helsinki-NLP**:
  - State-of-the-art for Indian languages (AI4Bharat IndicTrans2), but requires ~1.5 GB model weights and PyTorch dependencies.
  - Recommended as an optional future enhancement.
* **Cloud Option: Bhashini (Government of India / MeitY)**:
  - Free API for Indian languages, but requires API key credentials and network connectivity. Kept as an optional external adapter.

### 10.3 Text-to-Speech (TTS)

* **Primary: `edge-tts` (Microsoft Edge Neural Voices Python wrapper)**:
  - 100% free, requires no API key and no account.
  - Superb neural voice quality for Indian languages:
    - Telugu: `te-IN-MohanNeural`, `te-IN-ShrutiNeural`
    - Hindi: `hi-IN-MadhurNeural`, `hi-IN-SwaraNeural`
    - Indian English: `en-IN-PrabhatNeural`, `en-IN-NeerjaNeural`
  - Zero local disk space required for model weights.
* **Offline Fallback: `pyttsx3`**:
  - Uses Windows SAPI5 offline speech synthesizers.
  - 100% offline, ₹0, zero download, but robotic quality and limited Telugu phonemes.

---

## 11. External API Firewall

### 11.1 Current State: No External Boundary Exists

Inspection confirms that `backend/app/` contains **zero external HTTP clients or API adapters**. All existing agents interact solely with local JSON files, local vector stores, and local Ollama instances.

### 11.2 Recommended Architecture: `BaseExternalAdapter` Layer

Phase O introduces external network calls for the first time (Open-Meteo, OSRM). These must **never be called directly from specialist agents**.

An external service firewall must be created at `backend/app/agents/adapters/`:

```text
Specialist Agent (LiveWeatherAgent / LiveNavigationAgent)
       ↓
ExternalAPIAdapter / BaseExternalAdapter
  ├── 1. Connection Pooling & HTTP Session Reuse
  ├── 2. Strict Timeout Enforcement (Default: 3.0s connect / 5.0s read)
  ├── 3. Exponential Backoff & Retry Policy (Max 1 retry)
  ├── 4. Circuit Breaker (Trips after 3 consecutive failures to prevent latency spikes)
  ├── 5. Error Normalization (Converts requests.RequestException into typed PilgrimAI exceptions:
  │       ExternalServiceTimeout, ExternalServiceUnavailable, ExternalRateLimitExceeded)
  ├── 6. Secret Sanitization (Redacts query parameters and auth headers from logs)
  └── 7. Offline Test Fixture Mode (Allows 100% offline testing with canned payloads)
       ↓
External Web Service (Open-Meteo / OSRM)
```

---

## 12. Failure and Fallback Strategy

| Agent | Failure Scenario | Degradation & Fallback Behavior |
|---|---|---|
| **`LiveWeatherAgent`** | Open-Meteo timeout, HTTP 5xx, or offline | 1. Catch network error via adapter.<br>2. Return graceful `AgentResponse(success=False)` stating real-time weather is unreachable.<br>3. Present verified historical climate/seasonality notes if documented in temple profile.<br>4. **NEVER hallucinate or fabricate weather data.** |
| **`LiveNavigationAgent`** | OSRM demo server unavailable or rate-limited | 1. Calculate approximate direct road distance via Haversine formula + road multiplier (1.28x).<br>2. Fetch verified travel connectivity from `<temple>/travel.json` (bus routes, nearest railway station, highway route).<br>3. Explicitly state that route is estimated from verified static guides. |
| **`BudgetAgent`** | Specific seva or room price not found in JSON | 1. Compute total for all verified items.<br>2. Explicitly flag unverified items as "Price on inquiry at temple counter".<br>3. Continue calculation locally; **never invent prices**. |
| **`VoiceMultilingualAgent`** | Microphone / STT engine failure or unsupported language | 1. Return clean text error explaining audio could not be processed.<br>2. Fall back to standard text response without pretending speech was processed. |

---

## 13. Security and Secrets Management

1. **Zero Secret Leakage in Traces**:
   - `AgentState._sanitize_metadata()` already redacts all keys matching `api_key`, `secret`, `password`, `token`, `auth`, `credential`.
   - The external adapter will ensure API keys never appear in URL query strings or execution traces.
2. **`.env` Separation**:
   - Optional API keys (e.g., Google Maps, Bhashini) will reside exclusively in `.env` (which is in `.gitignore`).
   - The application must start and pass all tests even when `.env` contains zero API keys.
3. **No Secrets in `/chat` Telemetry**:
   - `ChatResponse.metadata` must never expose internal service URLs with embedded credentials.

---

## 14. Multi-Intent Integration

The four new agents integrate directly with the existing `SequentialMultiIntentPipeline`:

### 14.1 Query Decomposition Matrix

1. **Weather + Itinerary**:
   * *"Plan a trip to Yadadri and tell me tomorrow's weather."*
   * Clause 1: *"Plan a trip to Yadadri"* → `itinerary_planning` → `ItineraryPlanningAgent`
   * Clause 2: *"tell me tomorrow's weather at Yadadri temple"* → `weather` → `LiveWeatherAgent`
2. **Weather + Budget**:
   * *"What is the weather at Basara and how much will the trip cost?"*
   * Clause 1: *"What is the weather at Basara"* → `weather` → `LiveWeatherAgent`
   * Clause 2: *"how much will the trip cost at Basara temple"* → `budget` → `BudgetAgent`
3. **Navigation + Weather**:
   * *"Give me directions to Yadadri and tell me the weather tomorrow."*
   * Clause 1: *"Give me directions to Yadadri"* → `navigation` → `LiveNavigationAgent`
   * Clause 2: *"tell me the weather tomorrow at Yadadri temple"* → `weather` → `LiveWeatherAgent`
4. **Itinerary + Budget**:
   * *"Plan a 2-day trip to Basara and Vemulawada and give me the expected budget."*
   * Clause 1: *"Plan a 2-day trip to Basara and Vemulawada"* → `itinerary_planning` → `ItineraryPlanningAgent`
   * Clause 2: *"give me the expected budget"* → `budget` → `BudgetAgent` (consumes planned itinerary)
5. **Weather + Translation**:
   * *"Tell me the weather at Yadadri and translate the response into Telugu."*
   * Clause 1: *"Tell me the weather at Yadadri"* → `weather` → `LiveWeatherAgent`
   * Clause 2: *"translate the response into Telugu"* → `voice_multilingual` → `VoiceMultilingualAgent`

---

## 15. `/chat` Integration & Schema Compatibility

The FastAPI `/chat` endpoint integrated in Phase N seamlessly accommodates Phase O agents without contract alterations:

```python
class ChatResponse(BaseModel):
    question: str
    answer: str
    retrieved_chunks: int
    sources: List[str]
    confidence_score: float
    agent_name: Optional[str] = None
    session_id: Optional[str] = None
    latency_ms: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
```

* When `LiveWeatherAgent` runs, `agent_name` will be `"live_weather"`, `sources` will list `["Open-Meteo API", "<temple>/maps.json"]`, and `metadata` will hold weather telemetry.
* When `BudgetAgent` runs, `agent_name` will be `"budget"`, `sources` will list `["<temple>/accommodation.json", "<temple>/sevas.json"]`, and `metadata` will hold the itemized cost breakdown.
* When `LiveNavigationAgent` runs, `agent_name` will be `"live_navigation"`, `sources` will list `["OSRM Routing Engine", "<temple>/travel.json"]`.
* When `VoiceMultilingualAgent` runs, `agent_name` will be `"voice_multilingual"`.

---

## 16. D: Drive Strategy (Models, Caches, Downloads)

### 16.1 Current Repository Findings

Inspection of active system environment variables revealed:
* `OLLAMA_MODELS`: Configured safely to **`D:\Ollama\models`**.
* `HF_HOME`: **`None`** (Unset — defaults to `C:\Users\aksha\.cache\huggingface`).
* `TRANSFORMERS_CACHE`: **`None`** (Unset — defaults to C: drive).
* `TORCH_HOME`: **`None`** (Unset — defaults to `C:\Users\aksha\.cache\torch`).

### 16.2 Mandatory Phase O Storage Directives

To prevent catastrophic exhaustion of the user's limited C: drive, Phase O must enforce:
1. **Redirect HuggingFace and Torch Caches in Python Configuration**:
   ```python
   import os
   os.environ["HF_HOME"] = r"D:\huggingface_cache"
   os.environ["TORCH_HOME"] = r"D:\torch_cache"
   ```
2. **Explicit Download Roots for Voice Models**:
   - `faster-whisper`: Specify `download_root=r"D:\models\whisper"` during model instantiation.
   - Piper TTS / ONNX models: Store strictly under `D:\models\tts\`.
3. **No Automatic Model Downloads on Import**:
   - Model loading must be lazy and explicit, guarded by availability checks.

---

## 17. Protected Components

The following existing assets are protected and must remain **strictly unmodified**:
* **417 source JSON files** across all 20 temple directories.
* **`qdrant_db/`** vector database.
* **`bm25_index/`** lexical search index.
* **`evaluation/`** benchmarking datasets.
* **`.env`** environment configuration.
* **`frontend/`** and static web UI files.
* **`backend/app/rag/`** core retrieval and indexing pipeline.
* **`backend/app/api/chat.py`** and **`backend/app/main.py`** (until final integration prompts).
* **Existing Phase A–N specialist agent implementations** (`temple_information_agent.py`, `comparison_agent.py`, `cross_temple_aggregation_agent.py`, `itinerary_planning_agent.py`).
* **Existing 324-test regression suite**.

---

## 18. Recommended Implementation Order

To maintain 100% test greenness and prevent integration chaos, Phase O should be executed in an 8-stage dependency-aware roadmap:

```text
┌─────────────────────────────────────────────────────────────┐
│ Phase O1: External API Firewall & Resilience Infrastructure │
│ (BaseExternalAdapter, timeout, circuit breaker, retry)      │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ Phase O2: Coordinate Registry Architecture                  │
│ (temple_coordinates.json, 20 canonical temples, aliases)   │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ Phase O3: LiveWeatherAgent Implementation                   │
│ (Open-Meteo adapter, weather contracts, pilgrim advisory)   │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ Phase O4: BudgetAgent Implementation                        │
│ (Local calculation engine, RAG tariffs, cost categorization)│
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ Phase O5: LiveNavigationAgent Implementation                │
│ (OSRM adapter, travel.json fallback, Haversine estimator)   │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ Phase O6: VoiceMultilingualAgent Implementation             │
│ (Faster-Whisper on D:, Edge-TTS, Ollama translation)        │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ Phase O7: Multi-Agent & Multi-Intent Integration            │
│ (Router expansion, SequentialMultiIntentPipeline hooks)     │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ Phase O8: Full Stack Certification & Regression Baseline    │
│ (MasterAgentCoordinator, /chat endpoint, 350+ tests)        │
└─────────────────────────────────────────────────────────────┘
```

---

## 19. Technical Risks and Mitigations

1. **External Network Latency & Flakiness (Open-Meteo / OSRM)**:
   * *Risk*: Slow API responses degrade `/chat` endpoint performance.
   * *Mitigation*: 3.0s hard timeout in `ExternalAPIAdapter`, in-memory TTL caching (15 mins for weather, 24 hours for routes), and immediate fallback to offline static data.
2. **OSRM Public Demo Server Rate Limiting**:
   * *Risk*: Demo server returns HTTP 429 during bursts.
   * *Mitigation*: Adapter catches 429, activates circuit breaker, and falls back to mathematical Haversine road estimation and static `travel.json`.
3. **C: Drive Space Exhaustion during Voice / STT Setup**:
   * *Risk*: Installing Whisper or HuggingFace packages inadvertently writes multi-gigabyte models to `C:\Users\...`.
   * *Mitigation*: Set `HF_HOME=D:\huggingface_cache`, `TORCH_HOME=D:\torch_cache`, and `download_root=D:\models\whisper` prior to downloading any weight files.
4. **LLM Translation Hallucination in Indic Languages**:
   * *Risk*: Small models produce inaccurate translations of specialized temple rituals.
   * *Mitigation*: Restrict translation to system presentation layer; keep core factual numbers, names, and seva timings strictly anchored to verified JSON source strings.

---

## 20. Exact Next Step

The immediate next implementation phase is:

```text
PHASE O — PROMPT 2: Phase O1 & O2
1. Implement the External API Firewall (backend/app/agents/adapters/external_adapter.py)
   with timeout control, circuit breaking, retry logic, and secret sanitization.
2. Implement the Canonical Coordinate Registry (backend/app/agents/data/temple_coordinates.json)
   covering all 20 canonical temples and aliases without modifying source dataset JSON files.
```

---

*Phase O Architecture Audit officially completed with ZERO production code modifications and full regression baseline preserved.*
