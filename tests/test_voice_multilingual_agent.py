"""
Phase O6 - VoiceMultilingualAgent Certification Tests

Certifies:
1. BaseAgent contract compliance (inheritance, name, AgentResponse lifecycle).
2. Language detection: English, Telugu script, Hindi/Devanagari script, ambiguous/empty.
3. Directive parsing: "Answer in Telugu", "Tell me in Hindi", "in Telugu", "translate to Telugu".
4. Translation abstraction: EN -> TE, EN -> HI, TE -> EN, HI -> EN.
5. Translation fallback: unsupported language, provider unavailable, provider not configured.
6. Speech-to-text abstraction: valid audio, empty audio, failure, unavailable provider.
7. Zero automatic model downloads: local providers report NOT_CONFIGURED safely.
8. Text-to-speech abstraction: valid synthesis, unavailable TTS, safe text preservation.
9. Text-only input compatibility.
10. Router protection: normal queries (temple info, navigation, budget, weather, comparison, itinerary)
    are strictly NOT captured by VoiceMultilingualAgent.
11. Intent preservation: Telugu + temple info, Hindi + navigation, Telugu + weather, Hindi + budget.
12. Multi-intent compound queries wrapped in language directives.
13. Conversation memory integration: Turn 1 query -> Turn 2 "Answer that in Telugu".
14. Audio privacy & security: zero raw audio bytes in state, trace, or metadata; secret sanitization.
15. Zero fabrication: never invents translations, fake audio, or manufactured confidence scores.
16. Coordinator dependency injection and backwards compatibility.
17. Determinism across repeated executions.
"""

import sys
from pathlib import Path
import pytest

# Ensure root and backend are in sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState, AgentResponse
from app.agents.router import AgentRouter
from app.agents.coordinator import MasterAgentCoordinator
from app.agents.memory import ConversationMemoryManager
from app.agents.voice_multilingual_agent import (
    VoiceMultilingualAgent,
    ProviderStatus,
    TranscriptionResult,
    LanguageDetectionResult,
    TranslationResult,
    SpeechSynthesisResult,
    DeterministicLanguageDetector,
    MockSpeechToTextProvider,
    LocalSpeechToTextProvider,
    MockTranslationProvider,
    LocalTranslationProvider,
    MockTextToSpeechProvider,
    LocalTextToSpeechProvider,
)


# =============================================================================
# 1. Agent Contract & Lifecycle Tests
# =============================================================================

def test_01_agent_inheritance_and_name():
    """Verify VoiceMultilingualAgent inherits from BaseAgent and has correct name."""
    agent = VoiceMultilingualAgent()
    assert isinstance(agent, BaseAgent)
    assert agent.name == "voice_multilingual"
    assert "multilingual" in agent.description.lower()


def test_02_agent_state_lifecycle_and_timing():
    """Verify execution lifecycle produces standardized AgentResponse with latency."""
    agent = VoiceMultilingualAgent()
    state = AgentState(user_query="Translate to Telugu: Hello pilgrim")
    response = agent.execute(state)

    assert isinstance(response, AgentResponse)
    assert response.agent_name == "voice_multilingual"
    assert response.success is True
    assert response.latency_ms > 0.0
    assert len(state.execution_trace) == 1
    assert state.execution_trace[0].agent_name == "voice_multilingual"
    assert state.execution_trace[0].status == "completed"


# =============================================================================
# 2. Language Detection Tests
# =============================================================================

def test_03_detect_english():
    """Verify standard Latin English text is detected as 'en'."""
    detector = DeterministicLanguageDetector()
    res = detector.detect_language("What are the timings of Yadadri temple?")
    assert res.language == "en"
    assert res.status == ProviderStatus.AVAILABLE
    assert res.confidence is not None and res.confidence > 0.8


def test_04_detect_telugu_script():
    """Verify native Telugu script is detected as 'te'."""
    detector = DeterministicLanguageDetector()
    res = detector.detect_language("యాదాద్రి ఆలయ సమయాలు ఏమిటి?")
    assert res.language == "te"
    assert res.status == ProviderStatus.AVAILABLE
    assert res.confidence is not None and res.confidence > 0.8


def test_05_detect_hindi_script():
    """Verify native Devanagari script is detected as 'hi'."""
    detector = DeterministicLanguageDetector()
    res = detector.detect_language("यादाद्री मंदिर का समय क्या है?")
    assert res.language == "hi"
    assert res.status == ProviderStatus.AVAILABLE
    assert res.confidence is not None and res.confidence > 0.8


def test_06_detect_empty_or_whitespace():
    """Verify empty input returns 'unknown' safely without error."""
    detector = DeterministicLanguageDetector()
    res = detector.detect_language("   ")
    assert res.language == "unknown"
    assert res.confidence is None


def test_07_detect_ambiguous_or_numeric():
    """Verify numeric/symbol-only input returns 'unknown' safely."""
    detector = DeterministicLanguageDetector()
    res = detector.detect_language("12345 67890 ??? !!!")
    assert res.language == "unknown"
    assert res.confidence is None


# =============================================================================
# 3. Directive Extraction Tests
# =============================================================================

def test_08_directive_answer_in_telugu():
    """Verify 'Answer in Telugu: What are Yadadri timings?' extracts 'te' and cleans query."""
    agent = VoiceMultilingualAgent()
    lang, core = agent.extract_language_directives("Answer in Telugu: What are Yadadri timings?")
    assert lang == "te"
    assert core.strip() == "What are Yadadri timings?"


def test_09_directive_tell_me_in_hindi():
    """Verify 'Tell me in Hindi how far Yadadri is from Hyderabad' extracts 'hi'."""
    agent = VoiceMultilingualAgent()
    lang, core = agent.extract_language_directives("Tell me in Hindi how far Yadadri is from Hyderabad")
    assert lang == "hi"
    assert "how far Yadadri is from Hyderabad" in core


def test_10_directive_in_telugu_prefix():
    """Verify 'In Telugu, what is the weather at Yadadri?' extracts 'te'."""
    agent = VoiceMultilingualAgent()
    lang, core = agent.extract_language_directives("In Telugu, what is the weather at Yadadri?")
    assert lang == "te"
    assert "what is the weather at Yadadri?" in core


def test_11_directive_translate_to_telugu():
    """Verify 'Translate this to Telugu' extracts target language 'te'."""
    agent = VoiceMultilingualAgent()
    lang, core = agent.extract_language_directives("Translate this to Telugu")
    assert lang == "te"


def test_12_directive_no_directive():
    """Verify ordinary text returns None for target language."""
    agent = VoiceMultilingualAgent()
    lang, core = agent.extract_language_directives("What are the sevas at Basara temple?")
    assert lang is None
    assert core == "What are the sevas at Basara temple?"


# =============================================================================
# 4. Translation Abstraction Tests
# =============================================================================

def test_13_mock_translation_english_to_telugu():
    """Verify English to Telugu translation."""
    provider = MockTranslationProvider()
    res = provider.translate("Temple Timings", source_language="en", target_language="te")
    assert res.status == ProviderStatus.AVAILABLE
    assert "[తెలుగు అనువాదం]" in res.translated_text
    assert "Temple Timings" in res.translated_text


def test_14_mock_translation_english_to_hindi():
    """Verify English to Hindi translation."""
    provider = MockTranslationProvider()
    res = provider.translate("Temple Timings", source_language="en", target_language="hi")
    assert res.status == ProviderStatus.AVAILABLE
    assert "[हिंदी अनुवाद]" in res.translated_text


def test_15_mock_translation_telugu_to_english():
    """Verify Telugu to English normalization."""
    provider = MockTranslationProvider()
    res = provider.translate("[తెలుగు అనువాదం] Yadadri Timings", source_language="te", target_language="en")
    assert res.status == ProviderStatus.AVAILABLE
    assert res.translated_text == "Yadadri Timings"


def test_16_translation_same_language_identity():
    """Verify translating to same language returns original text without modification."""
    provider = MockTranslationProvider()
    res = provider.translate("Same Text", source_language="en", target_language="en")
    assert res.status == ProviderStatus.AVAILABLE
    assert res.translated_text == "Same Text"


def test_17_translation_unsupported_language():
    """Verify requesting an unsupported language returns UNSUPPORTED_LANGUAGE status."""
    provider = MockTranslationProvider(unsupported_languages=["fr", "de"])
    res = provider.translate("Hello", source_language="en", target_language="fr")
    assert res.status == ProviderStatus.UNSUPPORTED_LANGUAGE
    assert res.translated_text == ""
    assert "not supported" in res.error_message.lower()


def test_18_translation_provider_unavailable():
    """Verify unavailable translation provider returns UNAVAILABLE status."""
    provider = MockTranslationProvider(status=ProviderStatus.UNAVAILABLE)
    res = provider.translate("Hello", source_language="en", target_language="te")
    assert res.status == ProviderStatus.UNAVAILABLE
    assert res.translated_text == ""


def test_19_local_translation_provider_zero_download():
    """Verify LocalTranslationProvider returns NOT_CONFIGURED when no local model exists."""
    provider = LocalTranslationProvider(model_dir=None)
    res = provider.translate("Hello", source_language="en", target_language="te")
    assert res.status == ProviderStatus.NOT_CONFIGURED
    assert "no local translation model" in res.error_message.lower()


# =============================================================================
# 5. Speech-to-Text Abstraction Tests
# =============================================================================

def test_20_mock_stt_transcription_success():
    """Verify valid audio input is transcribed to text."""
    provider = MockSpeechToTextProvider(default_text="What are Yadadri timings?")
    res = provider.transcribe(b"MOCK_AUDIO_BYTES")
    assert res.status == ProviderStatus.AVAILABLE
    assert res.text == "What are Yadadri timings?"
    assert res.confidence == 0.95


def test_21_mock_stt_empty_audio():
    """Verify empty audio input returns FAILED status."""
    provider = MockSpeechToTextProvider()
    res = provider.transcribe(None)
    assert res.status == ProviderStatus.FAILED
    assert res.text == ""


def test_22_mock_stt_provider_unavailable():
    """Verify unavailable STT provider returns UNAVAILABLE status."""
    provider = MockSpeechToTextProvider(status=ProviderStatus.UNAVAILABLE)
    res = provider.transcribe(b"AUDIO")
    assert res.status == ProviderStatus.UNAVAILABLE
    assert res.text == ""


def test_23_local_stt_provider_zero_download():
    """Verify LocalSpeechToTextProvider returns NOT_CONFIGURED without downloading models."""
    provider = LocalSpeechToTextProvider(model_path=None)
    res = provider.transcribe(b"AUDIO")
    assert res.status == ProviderStatus.NOT_CONFIGURED
    assert "not configured" in res.error_message.lower()


# =============================================================================
# 6. Text-to-Speech Abstraction Tests
# =============================================================================

def test_24_mock_tts_synthesis_success():
    """Verify valid text produces mock speech synthesis result."""
    provider = MockTextToSpeechProvider()
    res = provider.synthesize("Grounded temple answer", language="te")
    assert res.status == ProviderStatus.AVAILABLE
    assert res.audio_ref is not None
    assert res.audio_format == "audio/wav"


def test_25_mock_tts_empty_text():
    """Verify synthesizing empty text returns FAILED."""
    provider = MockTextToSpeechProvider()
    res = provider.synthesize("", language="te")
    assert res.status == ProviderStatus.FAILED


def test_26_mock_tts_unavailable():
    """Verify unavailable TTS returns UNAVAILABLE without failing."""
    provider = MockTextToSpeechProvider(status=ProviderStatus.UNAVAILABLE)
    res = provider.synthesize("Some text", language="te")
    assert res.status == ProviderStatus.UNAVAILABLE


def test_27_local_tts_provider_zero_download():
    """Verify LocalTextToSpeechProvider returns NOT_CONFIGURED when engine not installed."""
    provider = LocalTextToSpeechProvider(engine_available=False)
    res = provider.synthesize("Some text", language="te")
    assert res.status == ProviderStatus.NOT_CONFIGURED


# =============================================================================
# 7. Agent Execution & Routing Integration Tests
# =============================================================================

def test_28_agent_text_only_query_in_telugu():
    """Verify text query with 'Answer in Telugu' produces translated response."""
    agent = VoiceMultilingualAgent()
    state = AgentState(user_query="Answer in Telugu: What are the timings of Yadadri?")
    res = agent.execute(state)

    assert res.success is True
    assert "[తెలుగు అనువాదం]" in res.answer
    assert res.metadata["output_language"] == "te"
    assert res.metadata["translation_used"] is True


def test_29_agent_text_only_query_in_hindi():
    """Verify text query with 'Tell me in Hindi' produces Hindi response."""
    agent = VoiceMultilingualAgent()
    state = AgentState(user_query="Tell me in Hindi: What are the sevas at Yadadri?")
    res = agent.execute(state)

    assert res.success is True
    assert "[हिंदी अनुवाद]" in res.answer
    assert res.metadata["output_language"] == "hi"


def test_30_agent_native_telugu_script_input():
    """Verify native Telugu query is detected and processed."""
    agent = VoiceMultilingualAgent()
    state = AgentState(user_query="యాదాద్రి ఆలయ సమయాలు ఏమిటి?")
    res = agent.execute(state)

    assert res.success is True
    assert res.metadata["input_language"] == "te"
    assert res.metadata["output_language"] == "te"


def test_31_agent_audio_input_transcription_and_answer():
    """Verify audio input triggers STT transcription and returns answer."""
    agent = VoiceMultilingualAgent(
        stt_provider=MockSpeechToTextProvider(default_text="What are Yadadri timings?")
    )
    state = AgentState(
        user_query="",
        metadata={"audio_input": b"VALID_AUDIO_BYTES"}
    )
    res = agent.execute(state)

    assert res.success is True
    assert res.metadata["transcription_used"] is True
    assert res.metadata["speech_to_text_provider"] == "MockSpeechToTextProvider"


def test_32_agent_audio_input_stt_failure_handling():
    """Verify STT failure returns controlled error response without crashing."""
    agent = VoiceMultilingualAgent(
        stt_provider=MockSpeechToTextProvider(status=ProviderStatus.FAILED, error_message="Noise error")
    )
    state = AgentState(
        user_query="",
        metadata={"audio_input": b"CORRUPT_AUDIO"}
    )
    res = agent.execute(state)

    assert res.success is False
    assert "unavailable" in res.answer.lower() or "error" in res.answer.lower()


def test_33_agent_voice_output_requested():
    """Verify voice_requested produces audio_ref without storing permanent audio bytes."""
    agent = VoiceMultilingualAgent()
    state = AgentState(
        user_query="Answer in Telugu: What are Yadadri timings?",
        metadata={"voice_requested": True}
    )
    res = agent.execute(state)

    assert res.success is True
    assert res.metadata["audio_response"] == "available"
    assert "audio_ref" in res.metadata
    # Confirm no raw audio bytes in response metadata
    assert "audio_bytes" not in res.metadata


def test_34_agent_voice_output_tts_unavailable_preserves_text():
    """Verify text response is preserved even if TTS synthesis is unavailable."""
    agent = VoiceMultilingualAgent(
        tts_provider=MockTextToSpeechProvider(status=ProviderStatus.UNAVAILABLE)
    )
    state = AgentState(
        user_query="Answer in Telugu: What are Yadadri timings?",
        metadata={"voice_requested": True}
    )
    res = agent.execute(state)

    # Text answer must still succeed
    assert res.success is True
    assert "[తెలుగు అనువాదం]" in res.answer
    assert res.metadata["audio_response"] == "unavailable"


# =============================================================================
# 8. Router Protection Tests (Non-Stealing of Existing Queries)
# =============================================================================

def test_35_router_does_not_steal_temple_information():
    """Verify 'What are Yadadri timings?' routes to temple_information, NOT voice_multilingual."""
    router = AgentRouter()
    router.register_agent("voice_multilingual")
    decision = router.route("What are Yadadri timings?")
    assert decision.selected_agent == "temple_information"
    assert decision.intent == "temple_information"


def test_36_router_does_not_steal_navigation():
    """Verify 'How far is Yadadri from Hyderabad?' routes to live_navigation."""
    router = AgentRouter()
    router.register_agent("voice_multilingual")
    router.register_agent("live_navigation")
    decision = router.route("How far is Yadadri from Hyderabad?")
    assert decision.selected_agent == "live_navigation"
    assert decision.intent == "live_navigation"


def test_37_router_does_not_steal_budget():
    """Verify 'What will the trip cost for Yadadri?' routes to budget."""
    router = AgentRouter()
    router.register_agent("voice_multilingual")
    router.register_agent("budget")
    decision = router.route("What will the trip cost for Yadadri?")
    assert decision.selected_agent == "budget"
    assert decision.intent == "budget"


def test_38_router_does_not_steal_weather():
    """Verify 'What is the weather at Yadadri?' routes to live_weather."""
    router = AgentRouter()
    router.register_agent("voice_multilingual")
    router.register_agent("live_weather")
    decision = router.route("What is the weather at Yadadri?")
    assert decision.selected_agent == "live_weather"
    assert decision.intent == "weather"


def test_39_router_does_not_steal_comparison():
    """Verify 'Compare Yadadri and Basara' routes to comparison."""
    router = AgentRouter()
    router.register_agent("voice_multilingual")
    router.register_agent("comparison")
    decision = router.route("Compare Yadadri and Basara")
    assert decision.selected_agent == "comparison"
    assert decision.intent == "comparison"


def test_40_router_does_not_steal_itinerary():
    """Verify 'Plan a 2-day tour to Yadadri' routes to itinerary_planning."""
    router = AgentRouter()
    router.register_agent("voice_multilingual")
    router.register_agent("itinerary_planning")
    decision = router.route("Plan a 2-day tour to Yadadri")
    assert decision.selected_agent == "itinerary_planning"
    assert decision.intent == "itinerary_planning"


def test_41_router_captures_explicit_multilingual_directives():
    """Verify explicit multilingual queries route to voice_multilingual."""
    router = AgentRouter()
    router.register_agent("voice_multilingual")

    queries = [
        "Answer in Telugu: What are Yadadri timings?",
        "Tell me in Hindi how far Yadadri is from Hyderabad",
        "In Telugu, what is the weather in Yadadri?",
        "Translate this to Telugu",
        "యాదాద్రి ఆలయ దర్శనం సమయాలు",
        "यादाद्री मंदिर दर्शन का समय"
    ]
    for q in queries:
        decision = router.route(q)
        assert decision.selected_agent == "voice_multilingual", f"Query '{q}' failed to route to voice_multilingual"
        assert decision.intent == "voice_multilingual"


# =============================================================================
# 9. Intent Preservation & Coordinator Delegation Tests
# =============================================================================

def test_42_coordinator_integration_with_telugu_temple_info():
    """Verify coordinator processes 'Answer in Telugu: What are Yadadri timings?' via TempleInformationAgent."""
    coord = MasterAgentCoordinator()
    voice_agent = VoiceMultilingualAgent(coordinator=coord)
    coord.register_agent(voice_agent)

    state = AgentState(user_query="Answer in Telugu: What are the timings of Yadadri temple?")
    res = coord.process(state)

    assert res.success is True
    assert "[తెలుగు అనువాదం]" in res.answer
    assert res.metadata["output_language"] == "te"


def test_43_coordinator_integration_with_hindi_navigation():
    """Verify coordinator processes 'Tell me in Hindi how far Yadadri is from Hyderabad'."""
    from app.agents.adapters.navigation_adapter import NavigationAdapter
    from app.agents.live_navigation_agent import LiveNavigationAgent
    from tests.test_live_navigation_agent import MockNavigationTransport
    mock_transport = MockNavigationTransport()
    adapter = NavigationAdapter(transport=mock_transport)
    nav_agent = LiveNavigationAgent(adapter=adapter)
    coord = MasterAgentCoordinator(live_navigation_agent=nav_agent)
    voice_agent = VoiceMultilingualAgent(coordinator=coord)
    coord.register_agent(voice_agent)

    state = AgentState(user_query="Tell me in Hindi how far Yadadri is from Hyderabad")
    res = coord.process(state)

    assert res.success is True
    assert "[हिंदी अनुवाद]" in res.answer
    assert res.metadata["output_language"] == "hi"


def test_44_coordinator_integration_with_telugu_weather():
    """Verify coordinator processes 'In Telugu, what is the weather at Yadadri?'."""
    from app.agents.live_weather_agent import LiveWeatherAgent
    weather_agent = LiveWeatherAgent()
    coord = MasterAgentCoordinator(live_weather_agent=weather_agent)
    voice_agent = VoiceMultilingualAgent(coordinator=coord)
    coord.register_agent(voice_agent)

    state = AgentState(user_query="In Telugu, what is the weather at Yadadri?")
    res = coord.process(state)

    assert res.success is True
    assert "[తెలుగు అనువాదం]" in res.answer
    assert res.metadata["output_language"] == "te"


def test_45_coordinator_multi_intent_wrapped_in_language():
    """Verify multi-intent compound query wrapped in language directive executes properly."""
    from app.agents.live_weather_agent import LiveWeatherAgent
    from app.agents.budget_agent import BudgetAgent

    weather_agent = LiveWeatherAgent()
    budget_agent = BudgetAgent()
    coord = MasterAgentCoordinator(
        live_weather_agent=weather_agent,
        budget_agent=budget_agent
    )
    voice_agent = VoiceMultilingualAgent(coordinator=coord)
    coord.register_agent(voice_agent)

    state = AgentState(user_query="In Telugu, what is the weather in Yadadri and what will the trip cost?")
    res = coord.process(state)

    assert res.success is True
    assert "[తెలుగు అనువాదం]" in res.answer
    assert res.metadata["output_language"] == "te"


# =============================================================================
# 10. Conversation Memory & Follow-up Translation Tests
# =============================================================================

def test_46_conversation_memory_followup_translation():
    """
    Verify multi-turn memory:
    Turn 1: 'Tell me about Yadadri temple'
    Turn 2: 'Answer that in Telugu' -> translates Turn 1 answer to Telugu.
    """
    mem = ConversationMemoryManager()
    coord = MasterAgentCoordinator(memory_manager=mem)
    voice_agent = VoiceMultilingualAgent(coordinator=coord)
    coord.register_agent(voice_agent)

    session_id = "test_voice_memory_turn"

    # Turn 1
    state1 = AgentState(session_id=session_id, user_query="What are the timings of Yadadri temple?")
    res1 = coord.process(state1)
    assert res1.success is True
    assert len(res1.answer) > 0

    # Turn 2: Follow-up translation
    state2 = AgentState(session_id=session_id, user_query="Translate that to Telugu")
    res2 = coord.process(state2)

    assert res2.success is True
    assert "[తెలుగు అనువాదం]" in res2.answer
    assert res2.metadata["output_language"] == "te"


# =============================================================================
# 11. Security, Privacy & Zero-Fabrication Tests
# =============================================================================

def test_47_audio_privacy_no_raw_audio_bytes_in_state_or_trace():
    """Verify raw audio bytes are never retained in AgentState or ExecutionTrace."""
    agent = VoiceMultilingualAgent()
    raw_bytes = b"SECRET_AUDIO_PAYLOAD_123456"
    state = AgentState(
        user_query="",
        metadata={"audio_input": raw_bytes, "voice_requested": True}
    )
    res = agent.execute(state)

    # Check response metadata
    assert "audio_bytes" not in res.metadata
    assert raw_bytes not in str(res.metadata).encode()

    # Check trace
    trace_str = " ".join([str(t.metadata) for t in state.execution_trace])
    assert "SECRET_AUDIO_PAYLOAD" not in trace_str


def test_48_zero_fabrication_unavailable_translation_fallback():
    """Verify when translation provider is unavailable, controlled notice is given without fake translation."""
    agent = VoiceMultilingualAgent(
        translation_provider=MockTranslationProvider(status=ProviderStatus.UNAVAILABLE)
    )
    state = AgentState(user_query="Answer in Telugu: What are Yadadri timings?")
    res = agent.execute(state)

    assert res.success is True
    # Shows original English response with notice, never fabricated Telugu
    assert "translation is currently unavailable" in res.answer.lower()
    assert "[తెలుగు అనువాదం]" not in res.answer


def test_49_zero_fabrication_unsupported_language_fallback():
    """Verify unsupported language gives explicit unsupported notice rather than fake translation."""
    agent = VoiceMultilingualAgent(
        translation_provider=MockTranslationProvider(unsupported_languages=["fr"])
    )
    # Force target language to unsupported 'fr'
    agent.extract_language_directives = lambda q: ("fr", "What are Yadadri timings?")
    state = AgentState(user_query="Answer in French: What are Yadadri timings?")
    res = agent.execute(state)

    assert res.success is True
    assert "not supported" in res.answer.lower()


def test_50_secret_sanitization():
    """Verify API keys / tokens are never leaked into metadata or answer."""
    agent = VoiceMultilingualAgent()
    state = AgentState(
        user_query="Answer in Telugu: What are Yadadri timings?",
        metadata={"api_key": "SECRET_KEY_DO_NOT_LEAK"}
    )
    res = agent.execute(state)

    assert "SECRET_KEY" not in res.answer
    assert "api_key" not in res.metadata


# =============================================================================
# 12. Coordinator Dependency Injection & Inactive Safety Tests
# =============================================================================

def test_51_coordinator_without_voice_agent_runs_cleanly():
    """Verify MasterAgentCoordinator with voice_multilingual_agent=None preserves baseline."""
    coord = MasterAgentCoordinator(voice_multilingual_agent=None)
    assert "voice_multilingual" not in coord.agents

    state = AgentState(user_query="What are Yadadri timings?")
    res = coord.process(state)
    assert res.success is True
    assert res.agent_name == "temple_information"


def test_52_determinism_repeated_execution():
    """Verify repeated execution produces identical deterministic output."""
    agent = VoiceMultilingualAgent()
    state1 = AgentState(user_query="Answer in Telugu: What are the timings of Yadadri?")
    res1 = agent.execute(state1)

    state2 = AgentState(user_query="Answer in Telugu: What are the timings of Yadadri?")
    res2 = agent.execute(state2)

    assert res1.answer == res2.answer
    assert res1.metadata["output_language"] == res2.metadata["output_language"]
    assert res1.metadata["translation_used"] == res2.metadata["translation_used"]
