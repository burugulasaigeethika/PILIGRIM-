# Implementation Plan — Phase O6: VoiceMultilingualAgent

## 1. Overview & Objective

Phase O6 introduces the **`VoiceMultilingualAgent`** (`name = "voice_multilingual"`) to the PilgrimAI ecosystem. It acts as an interface/processing agent providing speech-to-text, language detection, query normalization, translation to canonical English, coordinator-driven grounded execution, and optional translated text/speech response.

### Non-Negotiable Boundaries:
- **Strict Scope**: Implement ONLY `VoiceMultilingualAgent`, provider abstractions/interfaces, and minimal router/coordinator DI. Do NOT implement Phase O7, booking, frontend UI, or RAG changes.
- **Local-First & Offline First**: Zero required paid APIs, zero required cloud API keys (`Bhashini`, `Whisper`, `Google`, `OpenAI`). Deterministic local/mocked providers for testing.
- **Zero Model Downloads**: Do NOT automatically download Whisper, translation, or TTS models during certification. If unavailable, return a controlled `unavailable` / `not_configured` status.
- **Zero-Fabrication Contract**: If translation or transcription is unavailable or unsupported, return a controlled refusal/status. Never fabricate translations, transcriptions, confidence scores, or fake audio files.
- **RAG & Agent Boundary**: `VoiceMultilingualAgent` must never directly access RAG internals (`qdrant_client`, `rank_bm25`, `sentence_transformers`, `LocalQdrantManager`, `PilgrimRAGService`) or source JSON files. All factual knowledge is obtained strictly via `MasterAgentCoordinator` and existing specialist agents (`TempleInformationAgent`, `LiveNavigationAgent`, `LiveWeatherAgent`, `BudgetAgent`, etc.).
- **Data & Index Integrity**: Zero changes to the 417 source temple JSON files, `qdrant_db/`, `bm25_index/`, or `evaluation/`.

---

## 2. Architecture & Design

### 2.1 Workflow Pipeline
```text
Speech / Text Input (e.g. "Answer in Telugu: What are Yadadri timings?" or native Telugu)
       ↓
VoiceMultilingualAgent (name = "voice_multilingual")
       ├── Audio Input Check → SpeechToTextProvider (audio bytes/path → transcribed text)
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
       └── Optional Speech Synthesis → TextToSpeechProvider (Target text → audio reference/bytes)
       ↓
AgentResponse (Translated text + optional audio reference + telemetry metadata)
```

### 2.2 Provider Abstraction Layer
Located in `backend/app/agents/voice_multilingual_agent.py` (or supporting provider classes):
1. **`SpeechToTextProvider` (Interface)**:
   - `transcribe(audio_input: Union[bytes, str, Path]) -> TranscriptionResult`
   - `TranscriptionResult(text: str, detected_language: str, confidence: float, status: ProviderStatus)`
   - Concrete implementations: `MockSpeechToTextProvider`, `LocalSpeechToTextProvider` (checks for local models, returns `not_configured` if absent without downloading).
2. **`LanguageDetectionProvider` (Interface)**:
   - `detect_language(text: str) -> LanguageDetectionResult`
   - `LanguageDetectionResult(language: str, confidence: float, status: ProviderStatus)`
   - Concrete implementation: `DeterministicLanguageDetector` (detects English, Telugu `[\u0C00-\u0C7F]`, Hindi `[\u0900-\u097F]`, with explicit directives e.g. "in Telugu", "in Hindi").
3. **`TranslationProvider` (Interface)**:
   - `translate(text: str, source_lang: str, target_lang: str) -> TranslationResult`
   - `TranslationResult(translated_text: str, source_lang: str, target_lang: str, status: ProviderStatus)`
   - Concrete implementations: `MockTranslationProvider`, `LocalTranslationProvider`. If language pair is unsupported or provider unavailable, returns controlled status without fabricating translations.
4. **`TextToSpeechProvider` (Interface)**:
   - `synthesize(text: str, language: str) -> SpeechSynthesisResult`
   - `SpeechSynthesisResult(audio_bytes: Optional[bytes], audio_format: Optional[str], status: ProviderStatus)`
   - Concrete implementations: `MockTextToSpeechProvider`, `LocalTextToSpeechProvider` (returns `unavailable` / `not_configured` if local engine not installed).
5. **External Provider Safety**:
   - Any external API communication adheres strictly to `BaseExternalAdapter` (O1 firewall) with sanitization of all authorization headers, zero secret leakage in state, traces, or logs.

### 2.3 Audio Security & Privacy
- Zero permanent audio storage.
- Zero raw audio bytes placed in `AgentState`, `ExecutionTrace`, or logs.
- Transcriptions and syntheses are handled in-memory.

### 2.4 Coordinator Dependency Injection
In `backend/app/agents/coordinator.py`:
- `voice_multilingual_agent: Optional[Any] = None` in `MasterAgentCoordinator.__init__`.
- If provided, registered with coordinator and router.
- Default is `None` (zero auto-instantiation, zero heavy model loading on import).

### 2.5 Router Protection
In `backend/app/agents/router.py`:
- Regex triggers for voice, speech, translation directives (`"translate to ..."`, `"answer in ..."`, `"in Telugu"`, etc.) and native Unicode scripts (Telugu `\u0C00-\u0C7F`, Devanagari `\u0900-\u097F`).
- Ordinary queries (`"What are Yadadri timings?"`, `"How far is Yadadri from Hyderabad?"`, `"What will the trip cost?"`) are strictly preserved for existing specialist agents.

---

## 3. Proposed Changes

### [NEW] [backend/app/agents/voice_multilingual_agent.py](file:///d:/pligrim%20ai%20new/backend/app/agents/voice_multilingual_agent.py)
- `ProviderStatus` enum (`AVAILABLE`, `UNAVAILABLE`, `NOT_CONFIGURED`, `FAILED`, `UNSUPPORTED_LANGUAGE`).
- Provider interfaces: `SpeechToTextProvider`, `LanguageDetectionProvider`, `TranslationProvider`, `TextToSpeechProvider`.
- Default deterministic local/mock providers.
- `VoiceMultilingualAgent(BaseAgent)` with `name = "voice_multilingual"`.
- Supports text and audio input, target language extraction, query delegation to coordinator, translation of grounded response, optional TTS synthesis, and metadata propagation.

### [MODIFY] [backend/app/agents/router.py](file:///d:/pligrim%20ai%20new/backend/app/agents/router.py)
- Add voice/multilingual patterns and priority classification for `voice_multilingual`.
- Preserve existing comparison, itinerary, weather, budget, navigation, and temple information queries.

### [MODIFY] [backend/app/agents/coordinator.py](file:///d:/pligrim%20ai%20new/backend/app/agents/coordinator.py)
- Accept `voice_multilingual_agent: Optional[Any] = None` with zero auto-instantiation.

### [NEW] [tests/test_voice_multilingual_agent.py](file:///d:/pligrim%20ai%20new/tests/test_voice_multilingual_agent.py)
- At least 40+ comprehensive offline unit and integration tests covering:
  - Agent contracts, lifecycle, AgentResponse structure.
  - Language detection (English, Telugu, Hindi, unknown, ambiguous).
  - Translation (EN <-> TE, EN <-> HI, unsupported, unavailable provider).
  - Speech-to-text (valid audio, empty, error, unavailable provider).
  - Text-only queries and explicit language directives.
  - Integration with coordinator, specialist agents, and multi-intent queries.
  - Conversation memory preservation.
  - Audio security and secret sanitization.
  - Zero-fabrication enforcement.
  - Determinism across repeated executions.

### [NEW] [docs/PHASE_O6_VOICE_MULTILINGUAL_AGENT.md](file:///d:/pligrim%20ai%20new/docs/PHASE_O6_VOICE_MULTILINGUAL_AGENT.md)
- Complete architectural documentation, local-first strategy, security boundaries, and certification report.

---

## 4. Verification Plan

### Automated Tests
1. **O6 Unit and Integration Tests**:
   ```bash
   pytest tests/test_voice_multilingual_agent.py -v
   ```
2. **Prior Phase Regression Suites**:
   ```bash
   pytest tests/test_external_adapter.py tests/test_temple_coordinate_registry.py -v
   pytest tests/test_live_weather_agent.py -v
   pytest tests/test_budget_agent.py -v
   pytest tests/test_live_navigation_agent.py -v
   ```
3. **Full Regression Suite**:
   ```bash
   python scratch/run_full_regression.py
   ```
   (Must pass 100% green across all 22 suites: 511 baseline + O6 tests).

### Source Data Integrity
- Run `verify_post_hashes.py` to confirm all 417 source temple JSON files remain 100% SHA-256 identical.
- Confirm `qdrant_db/`, `bm25_index/`, and `evaluation/` remain completely unchanged.
