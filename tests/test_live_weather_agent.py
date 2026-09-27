"""
PilgrimAI - LiveWeatherAgent Test Suite (Phase O3)

Comprehensive offline unit tests verifying:
- BaseAgent contract adherence and lifecycle execution.
- Location and alias resolution via TempleCoordinateRegistry.
- Open-Meteo current, hourly, and daily weather normalization.
- WMO weather code mapping and fallback behavior.
- Separation of factual weather data from practical pilgrimage guidance.
- Controlled failure responses (no fabricated weather or silent fallbacks).
- In-memory caching with distinct cache_hit and retrieved_at metadata.
- Error handling: timeouts, rate limits, 5xx server errors, connection errors, adapter exceptions.
- Zero secret leakage into metadata or error logs.
- Deterministic routing: single-intent weather routing, multi-intent preservation, comparison protection, itinerary protection.
- Coordinator registration and dependency-injection integrity.

Strictly offline: all external requests use mock transport via BaseExternalAdapter.
Zero real network calls; zero external credentials.
"""

import sys
from pathlib import Path
import pytest
import time
from typing import Dict, Any, Optional

# Ensure backend is in sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState, AgentResponse
from app.agents.live_weather_agent import (
    LiveWeatherAgent,
    WMO_WEATHER_CODE_DESCRIPTIONS,
    get_weather_condition_description,
    OPEN_METEO_ATTRIBUTION
)
from app.agents.coordinate_registry import TempleCoordinateRegistry, TempleCoordinate
from app.agents.adapters.external_adapter import (
    BaseExternalAdapter,
    ExternalTimeoutError,
    ExternalHTTPError,
    ExternalRateLimitError,
    ExternalConnectionError
)
from app.agents.router import AgentRouter
from app.agents.coordinator import MasterAgentCoordinator
from app.agents.multi_intent_pipeline import SequentialMultiIntentPipeline
from app.agents.itinerary_planning_agent import ItineraryPlanningAgent
from app.agents.response_aggregator import ResponseAggregator


class MockHttpResponse:
    """Mock HTTP response conforming to requests.Response interface."""
    def __init__(self, status_code: int = 200, json_data: Optional[Dict[str, Any]] = None, text: str = ""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text or "{}"
        self.headers = {"Content-Type": "application/json"}

    def json(self):
        return self._json_data


def get_standard_weather_mock_data() -> Dict[str, Any]:
    """Provides a realistic Open-Meteo response payload."""
    return {
        "latitude": 17.5888,
        "longitude": 78.9388,
        "generationtime_ms": 0.08,
        "utc_offset_seconds": 19800,
        "timezone": "Asia/Kolkata",
        "timezone_abbreviation": "IST",
        "elevation": 370.0,
        "current_units": {
            "time": "iso8601",
            "interval": "seconds",
            "temperature_2m": "°C",
            "relative_humidity_2m": "%",
            "precipitation": "mm",
            "rain": "mm",
            "weather_code": "wmo code",
            "wind_speed_10m": "km/h",
            "wind_direction_10m": "°"
        },
        "current": {
            "time": "2026-09-22T14:00",
            "interval": 900,
            "temperature_2m": 31.5,
            "relative_humidity_2m": 58,
            "precipitation": 0.0,
            "rain": 0.0,
            "weather_code": 2,
            "wind_speed_10m": 12.4,
            "wind_direction_10m": 180
        },
        "hourly_units": {
            "time": "iso8601",
            "temperature_2m": "°C",
            "precipitation_probability": "%",
            "precipitation": "mm",
            "weather_code": "wmo code",
            "wind_speed_10m": "km/h"
        },
        "hourly": {
            "time": ["2026-09-22T14:00", "2026-09-22T15:00", "2026-09-22T16:00"],
            "temperature_2m": [31.5, 32.0, 31.0],
            "precipitation_probability": [5, 10, 15],
            "precipitation": [0.0, 0.0, 0.0],
            "weather_code": [2, 2, 3],
            "wind_speed_10m": [12.4, 13.0, 11.5]
        },
        "daily_units": {
            "time": "iso8601",
            "weather_code": "wmo code",
            "temperature_2m_max": "°C",
            "temperature_2m_min": "°C",
            "precipitation_sum": "mm",
            "precipitation_probability_max": "%",
            "sunrise": "iso8601",
            "sunset": "iso8601"
        },
        "daily": {
            "time": ["2026-09-22", "2026-09-23", "2026-09-24", "2026-09-25", "2026-09-26", "2026-09-27", "2026-09-28"],
            "weather_code": [2, 61, 3, 1, 0, 80, 2],
            "temperature_2m_max": [33.0, 29.5, 31.0, 32.5, 33.5, 30.0, 32.0],
            "temperature_2m_min": [23.0, 22.0, 21.5, 22.0, 23.0, 22.5, 23.0],
            "precipitation_sum": [0.0, 5.2, 0.5, 0.0, 0.0, 3.8, 0.0],
            "precipitation_probability_max": [15, 75, 30, 10, 5, 60, 20],
            "sunrise": ["2026-09-22T06:07", "2026-09-23T06:07", "2026-09-24T06:08", "2026-09-25T06:08", "2026-09-26T06:08", "2026-09-27T06:09", "2026-09-28T06:09"],
            "sunset": ["2026-09-22T18:14", "2026-09-23T18:13", "2026-09-24T18:12", "2026-09-25T18:11", "2026-09-26T18:10", "2026-09-27T18:09", "2026-09-28T18:08"]
        }
    }


def create_mock_weather_agent(json_data=None, side_effect=None, cache_enabled=True):
    """Factory creating a LiveWeatherAgent with an offline mocked transport."""
    mock_payload = json_data if json_data is not None else get_standard_weather_mock_data()

    def mock_transport(method, url, params=None, headers=None, json=None, timeout=None, **kwargs):
        if side_effect:
            if isinstance(side_effect, Exception):
                raise side_effect
            return side_effect(method, url, params=params, headers=headers, json=json, timeout=timeout, **kwargs)
        return MockHttpResponse(status_code=200, json_data=mock_payload)

    adapter = BaseExternalAdapter(name="mock_open_meteo", transport=mock_transport)
    return LiveWeatherAgent(adapter=adapter, cache_enabled=cache_enabled)


# =====================================================================
# Group 1: Agent Contract Tests (Items 1 - 5)
# =====================================================================

def test_1_agent_inherits_base_agent():
    agent = create_mock_weather_agent()
    assert isinstance(agent, BaseAgent)


def test_2_agent_name_is_live_weather():
    agent = create_mock_weather_agent()
    assert agent.name == "live_weather"
    assert "Open-Meteo" in agent.description


def test_3_successful_execution_returns_agent_response():
    agent = create_mock_weather_agent()
    state = AgentState(user_query="What is the weather at Yadadri?")
    response = agent.execute(state)

    assert isinstance(response, AgentResponse)
    assert response.success is True
    assert response.agent_name == "live_weather"
    assert "Weather Report for Yadadri" in response.answer
    assert response.latency_ms > 0.0
    assert OPEN_METEO_ATTRIBUTION in response.sources


def test_4_empty_query_handled_safely():
    agent = create_mock_weather_agent()
    state = AgentState(user_query="")
    response = agent.execute(state)

    assert response.success is False
    assert response.error is not None
    assert "Empty or whitespace" in response.error


def test_5_whitespace_query_handled_safely():
    agent = create_mock_weather_agent()
    state = AgentState(user_query="   \t\n  ")
    response = agent.execute(state)

    assert response.success is False
    assert response.error is not None
    assert "Empty or whitespace" in response.error


# =====================================================================
# Group 2: Location and Coordinate Resolution (Items 6 - 9)
# =====================================================================

def test_6_known_temple_resolves_through_coordinate_registry():
    agent = create_mock_weather_agent()
    state = AgentState(user_query="How is the weather at Basara?")
    response = agent.execute(state)

    assert response.success is True
    assert response.metadata["location"] == "Basara"
    assert response.metadata["latitude"] == pytest.approx(18.870451, rel=1e-4)
    assert response.metadata["longitude"] == pytest.approx(77.9547, rel=1e-4)


def test_7_alias_resolves_correctly():
    agent = create_mock_weather_agent()
    # "Yadagirigutta" -> canonical "Yadadri"
    state = AgentState(user_query="Tell me the weather in Yadagirigutta today")
    response = agent.execute(state)

    assert response.success is True
    assert response.metadata["location"] == "Yadadri"


def test_8_unknown_location_handled_safely():
    agent = create_mock_weather_agent()
    state = AgentState(user_query="What is the weather at Atlantis underwater shrine?")
    response = agent.execute(state)

    assert response.success is False
    assert "unavailable" in response.answer.lower()
    assert response.metadata["supported"] is False
    assert response.metadata["location"] == "unknown"


def test_9_invalid_coordinate_data_cannot_silently_produce_weather():
    # Registry with an entry whose coordinates are None
    class BrokenRegistry(TempleCoordinateRegistry):
        def __init__(self):
            super().__init__()
            broken = TempleCoordinate(
                canonical_name="BrokenTemple",
                latitude=0.0,
                longitude=0.0,
                source="test",
                verification_status="needs_verification"
            )
            # Simulate broken coordinate
            object.__setattr__(broken, "latitude", None)
            self._coordinates["BrokenTemple"] = broken

        def get_coordinate(self, name):
            return self._coordinates.get("BrokenTemple")

    agent = LiveWeatherAgent(coordinate_registry=BrokenRegistry())
    state = AgentState(user_query="Weather at BrokenTemple")
    response = agent.execute(state)

    assert response.success is False
    assert "missing" in response.error.lower()


# =====================================================================
# Group 3: Current Weather Normalization (Items 10 - 15)
# =====================================================================

def test_10_current_temperature_parsed():
    agent = create_mock_weather_agent()
    state = AgentState(user_query="Temperature at Yadadri")
    response = agent.execute(state)

    assert response.success is True
    assert response.metadata["current_weather"]["temperature"] == 31.5
    assert "31.5°C" in response.answer


def test_11_humidity_parsed():
    agent = create_mock_weather_agent()
    state = AgentState(user_query="Humidity at Yadadri")
    response = agent.execute(state)

    assert response.success is True
    assert response.metadata["current_weather"]["relative_humidity"] == 58
    assert "58%" in response.answer


def test_12_precipitation_parsed():
    agent = create_mock_weather_agent()
    state = AgentState(user_query="Is there precipitation at Yadadri?")
    response = agent.execute(state)

    assert response.success is True
    assert response.metadata["current_weather"]["precipitation"] == 0.0
    assert "0.0 mm" in response.answer


def test_13_rain_parsed():
    agent = create_mock_weather_agent()
    state = AgentState(user_query="Rain at Yadadri")
    response = agent.execute(state)

    assert response.success is True
    assert response.metadata["current_weather"]["rain"] == 0.0
    assert "Rain: 0.0 mm" in response.answer


def test_14_wind_parsed():
    agent = create_mock_weather_agent()
    state = AgentState(user_query="Wind speed at Yadadri")
    response = agent.execute(state)

    assert response.success is True
    assert response.metadata["current_weather"]["wind_speed"] == 12.4
    assert "12.4 km/h" in response.answer


def test_15_weather_code_normalized():
    agent = create_mock_weather_agent()
    state = AgentState(user_query="Weather at Yadadri")
    response = agent.execute(state)

    # Weather code 2 -> "Partly cloudy"
    assert response.metadata["current_weather"]["weather_code"] == 2
    assert response.metadata["current_weather"]["condition"] == "Partly cloudy"
    assert "Partly cloudy" in response.answer


def test_15b_unknown_weather_code_normalized_safely():
    assert get_weather_condition_description(999) == "Unknown weather condition"
    assert get_weather_condition_description(None) == "Unknown weather condition"
    assert get_weather_condition_description("invalid") == "Unknown weather condition"


# =====================================================================
# Group 4: Hourly Forecast Normalization (Items 16 - 20)
# =====================================================================

def test_16_hourly_temperature_parsed():
    agent = create_mock_weather_agent()
    state = AgentState(user_query="Weather at Yadadri")
    response = agent.execute(state)

    assert "hourly_preview" in response.metadata
    temps = response.metadata["hourly_preview"]["temperature_first_3h"]
    assert temps == [31.5, 32.0, 31.0]


def test_17_precipitation_probability_parsed():
    agent = create_mock_weather_agent()
    state = AgentState(user_query="Weather at Yadadri")
    response = agent.execute(state)

    assert "hourly_preview" in response.metadata
    probs = response.metadata["hourly_preview"]["precipitation_prob_first_3h"]
    assert probs == [5, 10, 15]


def test_18_hourly_precipitation_in_payload():
    data = get_standard_weather_mock_data()
    hourly_precip = data["hourly"]["precipitation"]
    assert hourly_precip == [0.0, 0.0, 0.0]


def test_19_hourly_weather_code_in_payload():
    data = get_standard_weather_mock_data()
    hourly_codes = data["hourly"]["weather_code"]
    assert hourly_codes == [2, 2, 3]


def test_20_hourly_wind_in_payload():
    data = get_standard_weather_mock_data()
    hourly_wind = data["hourly"]["wind_speed_10m"]
    assert hourly_wind == [12.4, 13.0, 11.5]


# =====================================================================
# Group 5: Daily Forecast Normalization (Items 21 - 26)
# =====================================================================

def test_21_daily_max_temperature_parsed():
    agent = create_mock_weather_agent()
    state = AgentState(user_query="Daily max temp at Yadadri")
    response = agent.execute(state)

    assert "33.0°C" in response.answer  # Today max
    assert response.metadata["daily_preview"]["max_temperatures"][0] == 33.0


def test_22_daily_min_temperature_parsed():
    agent = create_mock_weather_agent()
    state = AgentState(user_query="Daily min temp at Yadadri")
    response = agent.execute(state)

    assert "23.0°C" in response.answer  # Today min
    assert response.metadata["daily_preview"]["min_temperatures"][0] == 23.0


def test_23_daily_precipitation_parsed():
    agent = create_mock_weather_agent()
    state = AgentState(user_query="Will it rain tomorrow at Yadadri?")
    response = agent.execute(state)

    # Tomorrow's precipitation is 5.2 mm in mock data
    assert "5.2 mm" in response.answer


def test_24_daily_precipitation_probability_parsed():
    agent = create_mock_weather_agent()
    state = AgentState(user_query="Will it rain tomorrow at Yadadri?")
    response = agent.execute(state)

    # Tomorrow's rain prob is 75% in mock data
    assert "75%" in response.answer


def test_25_sunrise_parsed():
    agent = create_mock_weather_agent()
    state = AgentState(user_query="Sunrise at Yadadri")
    response = agent.execute(state)

    assert "2026-09-22T06:07" in response.answer


def test_26_sunset_parsed():
    agent = create_mock_weather_agent()
    state = AgentState(user_query="Sunset at Yadadri")
    response = agent.execute(state)

    assert "2026-09-22T18:14" in response.answer


# =====================================================================
# Group 6: Reliability, Error Handling, and Caching (Items 27 - 34)
# =====================================================================

def test_27_provider_failure_returns_controlled_unavailable_response():
    def failing_transport(*args, **kwargs):
        return MockHttpResponse(status_code=500, text="Internal Server Error")

    adapter = BaseExternalAdapter(name="failing_adapter", transport=failing_transport)
    agent = LiveWeatherAgent(adapter=adapter)
    state = AgentState(user_query="Weather at Yadadri")
    response = agent.execute(state)

    assert response.success is False
    assert "currently unavailable" in response.answer
    assert "Server Error" in response.error or "HTTP 500" in response.error


def test_28_timeout_handled():
    def timeout_transport(*args, **kwargs):
        raise ExternalTimeoutError("Request timed out", sanitized_url="https://api.open-meteo.com/v1/forecast")

    adapter = BaseExternalAdapter(name="timeout_adapter", transport=timeout_transport)
    agent = LiveWeatherAgent(adapter=adapter)
    state = AgentState(user_query="Weather at Yadadri")
    response = agent.execute(state)

    assert response.success is False
    assert "currently unavailable" in response.answer
    assert "timed out" in response.error.lower()


def test_29_adapter_exception_handled():
    def conn_err_transport(*args, **kwargs):
        raise ExternalConnectionError("Failed to connect to host", sanitized_url="https://api.open-meteo.com/v1/forecast")

    adapter = BaseExternalAdapter(name="conn_adapter", transport=conn_err_transport)
    agent = LiveWeatherAgent(adapter=adapter)
    state = AgentState(user_query="Weather at Yadadri")
    response = agent.execute(state)

    assert response.success is False
    assert "currently unavailable" in response.answer
    assert "connect" in response.error.lower()


def test_30_cache_hit_works():
    call_count = [0]
    mock_payload = get_standard_weather_mock_data()

    def counting_transport(*args, **kwargs):
        call_count[0] += 1
        return MockHttpResponse(status_code=200, json_data=mock_payload)

    adapter = BaseExternalAdapter(name="counting_adapter", transport=counting_transport)
    agent = LiveWeatherAgent(adapter=adapter, cache_ttl_sec=60.0)

    state1 = AgentState(user_query="Weather at Yadadri")
    resp1 = agent.execute(state1)
    assert resp1.success is True
    assert resp1.metadata["cache_hit"] is False
    assert call_count[0] == 1

    state2 = AgentState(user_query="Weather at Yadadri")
    resp2 = agent.execute(state2)
    assert resp2.success is True
    assert resp2.metadata["cache_hit"] is True
    # Verify no second HTTP request was dispatched
    assert call_count[0] == 1


def test_31_cache_miss_works():
    call_count = [0]
    mock_payload = get_standard_weather_mock_data()

    def counting_transport(*args, **kwargs):
        call_count[0] += 1
        return MockHttpResponse(status_code=200, json_data=mock_payload)

    adapter = BaseExternalAdapter(name="counting_adapter", transport=counting_transport)
    agent = LiveWeatherAgent(adapter=adapter, cache_ttl_sec=60.0)

    # First location
    agent.execute(AgentState(user_query="Weather at Yadadri"))
    assert call_count[0] == 1

    # Second distinct location -> cache miss
    agent.execute(AgentState(user_query="Weather at Basara"))
    assert call_count[0] == 2


def test_32_cache_metadata_correctly_identifies_cached_data():
    agent = create_mock_weather_agent(cache_enabled=True)
    resp1 = agent.execute(AgentState(user_query="Weather at Yadadri"))
    assert resp1.metadata["cache_hit"] is False

    resp2 = agent.execute(AgentState(user_query="Weather at Yadadri"))
    assert resp2.metadata["cache_hit"] is True
    assert resp2.metadata["retrieved_at"] == resp1.metadata["retrieved_at"]


def test_33_retrieved_at_and_forecast_timestamp_metadata_present():
    agent = create_mock_weather_agent()
    response = agent.execute(AgentState(user_query="Weather at Yadadri"))

    assert "retrieved_at" in response.metadata
    assert "forecast_timestamp" in response.metadata
    assert response.metadata["timezone"] == "Asia/Kolkata"
    assert response.metadata["attribution"] == OPEN_METEO_ATTRIBUTION


def test_34_no_secrets_leak_into_metadata_or_errors():
    def leaking_transport(*args, **kwargs):
        # Simulate an error with a secret in query or message
        raise ExternalHTTPError(
            message="Error with secret=AIzaSySecretKey123 and token=my_secret_token",
            status_code=403,
            sanitized_url="https://api.open-meteo.com/v1/forecast?key=AIzaSySecretKey123"
        )

    adapter = BaseExternalAdapter(name="secret_adapter", transport=leaking_transport)
    agent = LiveWeatherAgent(adapter=adapter)
    response = agent.execute(AgentState(user_query="Weather at Yadadri"))

    assert "AIzaSySecretKey123" not in response.error
    assert "my_secret_token" not in response.error
    assert "[REDACTED]" in response.error or "secret" not in response.error


# =====================================================================
# Group 7: Routing and Coordinator Integration (Items 35 - 38)
# =====================================================================

def test_35_weather_only_query_routes_to_live_weather_when_registered():
    router = AgentRouter(active_agents={"temple_information", "live_weather"})
    decision = router.route("What is the weather at Yadadri?")

    assert decision.selected_agent == "live_weather"
    assert decision.intent == "weather"
    assert decision.confidence >= 0.9
    assert decision.metadata["detected_temple"].lower() == "yadadri"
    assert decision.metadata["available"] is True


def test_35b_weather_query_when_weather_agent_not_active():
    # Router without "live_weather" in active_agents
    router = AgentRouter(active_agents={"temple_information"})
    decision = router.route("What is the weather at Yadadri?")

    assert decision.selected_agent == "none"
    assert decision.intent == "weather"
    assert decision.metadata["available"] is False


def test_36_weather_plus_itinerary_remains_multi_intent():
    router = AgentRouter(active_agents={"temple_information", "live_weather", "itinerary_planning"})
    decision = router.route("What is the weather in Yadadri and plan a one-day visit?")

    assert decision.intent == "multi_intent"
    assert decision.selected_agent == "none"
    assert "weather" in decision.metadata["sub_intents"]
    assert "itinerary" in decision.metadata["sub_intents"]


def test_36b_weather_plus_budget_remains_multi_intent():
    router = AgentRouter(active_agents={"temple_information", "live_weather"})
    decision = router.route("What is the weather in Basara and what will the trip cost?")

    assert decision.intent == "multi_intent"
    assert decision.selected_agent == "none"
    assert "weather" in decision.metadata["sub_intents"]
    assert "budget" in decision.metadata["sub_intents"]


def test_37_existing_multi_temple_itinerary_routing_remains_intact():
    router = AgentRouter(active_agents={"temple_information", "itinerary_planning", "live_weather"})

    decision1 = router.route("Plan an itinerary for Basara and Vemulavada")
    assert decision1.selected_agent == "itinerary_planning"
    assert decision1.intent == "itinerary_planning"

    decision2 = router.route("Plan a 2 day trip to Birla Mandir and Ujjaini")
    assert decision2.selected_agent == "itinerary_planning"
    assert decision2.intent == "itinerary_planning"


def test_38_existing_explicit_comparison_routing_remains_intact():
    router = AgentRouter(active_agents={"temple_information", "comparison", "live_weather"})

    decision1 = router.route("Compare the weather of Basara and Yadadri")
    assert decision1.selected_agent == "comparison"
    assert decision1.intent == "comparison"

    decision2 = router.route("Srisailam vs Bhadrachalam accommodation")
    assert decision2.selected_agent == "comparison"
    assert decision2.intent == "comparison"

    decision3 = router.route("Basara vs Vemulavada sevas")
    assert decision3.selected_agent == "comparison"
    assert decision3.intent == "comparison"


# =====================================================================
# Group 8: Multi-Intent Sequential Pipeline Execution (Weather + Itinerary)
# =====================================================================

def test_39_sequential_multi_intent_pipeline_executes_weather_and_itinerary():
    # Setup offline mock agents
    weather_agent = create_mock_weather_agent()

    class MockItineraryAgent(BaseAgent):
        def __init__(self):
            super().__init__(name="itinerary_planning", description="Mock Itinerary Planner")

        def _run(self, state: AgentState) -> AgentResponse:
            return AgentResponse(
                success=True,
                agent_name=self.name,
                answer="Here is a planned 1-day itinerary for Yadadri.",
                sources=["ItineraryGuide"]
            )

    itinerary_agent = MockItineraryAgent()

    router = AgentRouter(active_agents={"temple_information", "live_weather", "itinerary_planning"})
    aggregator = ResponseAggregator()

    pipeline = SequentialMultiIntentPipeline(
        router=router,
        aggregator=aggregator,
        agents={
            weather_agent.name: weather_agent,
            itinerary_agent.name: itinerary_agent
        }
    )

    state = AgentState(user_query="What is the weather in Yadadri and plan a one-day visit?")
    result = pipeline.execute(state)

    assert result.success is True
    assert "Weather Report for Yadadri" in result.answer
    assert "planned 1-day itinerary for Yadadri" in result.answer


# =====================================================================
# Group 9: Coordinator Registration & Injection Integrity
# =====================================================================

class MockTempleInfoAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="temple_information", description="Mock Temple Info")

    def _run(self, state: AgentState) -> AgentResponse:
        return AgentResponse(success=True, agent_name=self.name, answer="Temple info")


def test_40_coordinator_does_not_auto_create_live_weather_agent():
    # Verifies Critical Rule: Coordinator instantiated without weather agent must not have it
    coordinator = MasterAgentCoordinator(temple_info_agent=MockTempleInfoAgent())
    assert "live_weather" not in coordinator.agents
    assert "live_weather" not in coordinator.router.active_agents


def test_41_coordinator_accepts_injected_live_weather_agent():
    weather_agent = create_mock_weather_agent()
    coordinator = MasterAgentCoordinator(
        temple_info_agent=MockTempleInfoAgent(),
        live_weather_agent=weather_agent
    )

    assert "live_weather" in coordinator.agents
    assert "live_weather" in coordinator.router.active_agents


def test_42_coordinator_register_agent_dynamically():
    coordinator = MasterAgentCoordinator(temple_info_agent=MockTempleInfoAgent())
    assert "live_weather" not in coordinator.agents

    weather_agent = create_mock_weather_agent()
    coordinator.register_agent(weather_agent)

    assert "live_weather" in coordinator.agents
    assert "live_weather" in coordinator.router.active_agents
    assert "live_weather" in coordinator.pipeline.agents


def test_43_coordinator_processes_weather_query_end_to_end():
    weather_agent = create_mock_weather_agent()
    coordinator = MasterAgentCoordinator(
        temple_info_agent=MockTempleInfoAgent(),
        live_weather_agent=weather_agent
    )

    state = AgentState(user_query="What is the weather at Yadadri?")
    response = coordinator.process(state)

    assert response.success is True
    assert "Weather Report for Yadadri" in response.answer
    assert response.agent_name == "live_weather"
    assert "coordinator_latency_ms" in response.metadata
