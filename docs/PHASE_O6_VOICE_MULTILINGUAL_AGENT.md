# Phase O6 — Voice Multilingual Agent Documentation

## 1. Objective & Scope

Phase O6 introduces the **`VoiceMultilingualAgent`** (`name = "voice_multilingual"`) to the PilgrimAI ecosystem. It operates as an interface and processing agent providing speech-to-text, deterministic language detection, query normalization, translation to canonical English, coordinator-driven domain execution, and optional translated text/speech response.

### Non-Negotiable Boundaries:
- **Strict Scope**: Implements ONLY `VoiceMultilingualAgent`, provider abstractions, and coordinator/router dependency injection. Does NOT implement Phase O7, booking, or frontend voice UI.
- **Local-First & Offline First**: Zero required paid APIs, zero required cloud API keys (`Bhashini`, `Whisper`, `Google`, `OpenAI`). All automated unit and regression tests run offline with deterministic local/mock providers.
- **Zero Model Downloads**: Never automatically downloads Whisper, translation, or TTS models during certification. If models are absent, providers report a controlled `not_configured` or `unavailable` status.
- **Zero Fabrication**: If translation or transcription is unavailable or unsupported, the agent returns a controlled refusal or status message. It never manufactures translations, fake audio files, or fake confidence scores.
- **RAG & Agent Boundary**: `VoiceMultilingualAgent` never directly accesses RAG internals (`qdrant_client`, `rank_bm25`, `sentence_transformers`, `LocalQdrantManager`, `PilgrimRAGService`) or source JSON files. All factual knowledge is obtained strictly through `MasterAgentCoordinator` and existing specialist agents (`TempleInformationAgent`, `LiveNavigationAgent`, `LiveWeatherAgent`, `BudgetAgent`, etc.).
- **Dataset & Database Integrity**: Zero changes to the 417 source temple JSON files, `qdrant_db/`, `bm25_index/`, or `evaluation/`.

---

## 2. End-to-End Architecture

```text
Speech / Text Input (e.g. "Answer in Telugu: What are Yadadri timings?" or native Telugu)
       ↓
VoiceMultilingualAgent (name = "voice_multilingual")
       ├── Audio Input Check → SpeechToTextProvider (audio bytes/ref → transcribed text)
       ├── Language Detection → LanguageDetectionProvider (detects te, hi, en, or unknown)
       ├── Target Language Extraction (e.g., "te", "hi", "en")
       ├── Query Normalization (translates non-English to canonical English if needed)
       ↓
MasterAgentCoordinator.process(normalized_state)
       ├── AgentRouter.route(normalized_query)
       ├── Specialist Agent (TempleInformationAgent, LiveNavigationAgent, etc.)
       └── ResponseAggregator / MultiIntentPipeline
       ↓
English Grounded Response
       ↓
VoiceMultilingualAgent
       ├── Translation → TranslationProvider (English → Target Language)
       └── Optional Speech Synthesis → TextToSpeechProvider (Target text → audio reference)
       ↓
AgentResponse (Translated text + optional audio reference + telemetry metadata)
```

---

## 3. Provider Abstraction Layer

### 3.1 Status Model
All provider operations return strongly typed result models anchored on `ProviderStatus`:
- `AVAILABLE`: Provider operational and response computed.
- `UNAVAILABLE`: Provider temporarily or structurally offline.
- `NOT_CONFIGURED`: Missing local model or API credentials without crashing.
- `FAILED`: Execution or transcription error.
- `UNSUPPORTED_LANGUAGE`: Requested language pair is not supported.

### 3.2 Provider Interfaces
1. **`BaseSpeechToTextProvider`**:
   - `transcribe(audio_input: Any, language: Optional[str]) -> TranscriptionResult`
   - Implementations: `MockSpeechToTextProvider`, `LocalSpeechToTextProvider`.
2. **`BaseLanguageDetectionProvider`**:
   - `detect_language(text: str) -> LanguageDetectionResult`
   - Implementation: `DeterministicLanguageDetector` (inspects Telugu Unicode range `[\u0C00-\u0C7F]`, Devanagari range `[\u0900-\u097F]`, Latin range, and explicit language directives).
3. **`BaseTranslationProvider`**:
   - `translate(text: str, source_language: str, target_language: str) -> TranslationResult`
   - Implementations: `MockTranslationProvider`, `LocalTranslationProvider`.
4. **`BaseTextToSpeechProvider`**:
   - `synthesize(text: str, language: str) -> SpeechSynthesisResult`
   - Implementations: `MockTextToSpeechProvider`, `LocalTextToSpeechProvider`.

---

## 4. Audio Security & Privacy

1. **Zero Permanent Audio Storage**: Audio input is processed ephemerally in-memory.
2. **Zero Raw Audio Bytes in State/Logs**: Audio payloads are never written into `AgentState`, `ExecutionTrace`, logs, or `AgentResponse.metadata`.
3. **Sanitized Telemetry**: Only metadata tokens (`audio_ref`, `audio_response: "available"|"unavailable"`, `input_language`, `output_language`) are propagated.
4. **Secret Sanitization**: Authorization headers and credentials are scrubbed from all traces.

---

## 5. Router & Coordinator Integration

### 5.1 Router Protection (Non-Stealing of Domain Queries)
In `backend/app/agents/router.py`:
- Priority 2.5 routes queries containing explicit voice/multilingual directives or non-English script to `voice_multilingual` when active.
- Ordinary queries strictly preserve existing specialist routing:
  - `"What are Yadadri timings?"` → `temple_information`
  - `"How far is Yadadri from Hyderabad?"` → `live_navigation`
  - `"What will the trip cost for Yadadri?"` → `budget`
  - `"What is the weather at Yadadri?"` → `live_weather`
  - `"Compare Yadadri and Basara"` → `comparison`
  - `"Plan a 2-day tour to Yadadri"` → `itinerary_planning`

### 5.2 Coordinator Dependency Injection
In `backend/app/agents/coordinator.py`:
- `MasterAgentCoordinator.__init__` accepts `voice_multilingual_agent: Optional[Any] = None`.
- If not provided, defaults to `None` with zero auto-instantiation and zero model loading.
- Recursion guard: inner state sets `_skip_voice_agent = True` so normalized queries route directly to domain specialists.
- Memory propagation: previous turn response summary is forwarded for follow-up translation directives (e.g., Turn 1: *"What are Yadadri timings?"* → Turn 2: *"Translate that to Telugu"*).

---

## 6. Verification & Certification Results

### 6.1 Test Suite Summary
- **Phase O6 Test Suite (`tests/test_voice_multilingual_agent.py`)**: **52 tests, 100% passing**
  - Contract & lifecycle (BaseAgent inheritance, latency, traces).
  - Language detection (English, Telugu, Hindi, unknown, ambiguous).
  - Directive extraction ("Answer in Telugu", "Tell me in Hindi", "in Telugu", "translate to Telugu").
  - Translation abstraction (EN ↔ TE, EN ↔ HI, unsupported, unavailable, not configured).
  - Speech-to-text abstraction (valid audio, empty, failure, unavailable).
  - Text-to-speech abstraction (valid synthesis, unavailable TTS, safe text preservation).
  - Router protection (ordinary domain queries strictly not stolen).
  - Coordinator integration & intent preservation (Telugu + temple info, Hindi + navigation, Telugu + weather, Hindi + budget).
  - Multi-intent compound queries wrapped in language directives.
  - Conversation memory multi-turn follow-up translation.
  - Audio security, privacy, and secret sanitization.
  - Zero-fabrication enforcement.
  - Determinism across repeated executions.
- **Phase O1/O2 Tests**: 34 passed.
- **Phase O3 Tests**: 46 passed.
- **Phase O4 Tests**: 55 passed.
- **Phase O5 Tests**: 52 passed.
- **Combined Regression Total**: **563 / 563 tests passing (100% green)** across all 22 test suites.

### 6.2 Data Integrity
- **417/417 Source Temple JSON Files**: 100% SHA-256 byte-for-byte identical (0 modifications).
- **`qdrant_db/`**: Unchanged.
- **`bm25_index/`**: Unchanged.
- **`evaluation/`**: Unchanged.

---

## 7. Files Created & Modified

### Files Created:
1. `backend/app/agents/voice_multilingual_agent.py` — Core VoiceMultilingualAgent and provider abstractions.
2. `tests/test_voice_multilingual_agent.py` — 52 comprehensive offline unit and integration tests.
3. `docs/PHASE_O6_VOICE_MULTILINGUAL_AGENT.md` — Architectural documentation and certification audit.

### Files Modified:
1. `backend/app/agents/coordinator.py` — Added `voice_multilingual_agent` dependency injection, recursion guard, and memory turn propagation.
2. `backend/app/agents/router.py` — Added `_voice_multilingual_patterns` and Priority 2.5 routing.

---

## 8. Known Limitations

1. **Offline Mock Providers for Test Certification**: In offline test mode, canned/deterministic translation and speech synthesis are used to satisfy zero-external-network and zero-model-download constraints.
2. **Local Model Setup**: To use real local offline models in production, models must be placed manually on the `D:` drive without automatic downloads during service execution.
3. **Supported Languages**: Primary deterministic support covers English, Telugu, and Hindi. Other languages gracefully trigger controlled unsupported-language notices.

---

## 9. Hard Stop

Phase O6 certification is complete. Phase O7 has NOT been implemented.
