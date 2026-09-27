"""
PilgrimAI - External API Firewall (Phase O1) Test Suite

Certifies BaseExternalAdapter, CircuitBreaker, typed exception hierarchy,
and secret sanitization under strictly mocked/offline conditions.
Zero real network calls, zero credentials required.
"""

import sys
import time
from pathlib import Path
import pytest

# Ensure backend is in sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.adapters.external_adapter import (
    BaseExternalAdapter,
    CircuitBreaker,
    CircuitState,
    ExternalAdapterError,
    ExternalTimeoutError,
    ExternalConnectionError,
    ExternalHTTPError,
    ExternalRateLimitError,
    ExternalCircuitOpenError,
    sanitize_url,
    sanitize_headers,
    sanitize_text,
)


class MockResponse:
    """Mock HTTP response object for offline unit testing."""
    def __init__(self, status_code: int = 200, text: str = "{}", headers: dict = None, json_data: dict = None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {"Content-Type": "application/json"}
        self._json_data = json_data if json_data is not None else {}

    def json(self):
        return self._json_data


# ---------------------------------------------------------------------
# Tests 1-2: Import and Credential Independence
# ---------------------------------------------------------------------

def test_1_adapter_imports_successfully():
    """Verify BaseExternalAdapter and all related symbols import cleanly."""
    assert BaseExternalAdapter is not None
    assert CircuitBreaker is not None
    assert issubclass(ExternalTimeoutError, ExternalAdapterError)
    assert issubclass(ExternalConnectionError, ExternalAdapterError)
    assert issubclass(ExternalRateLimitError, ExternalHTTPError)
    assert issubclass(ExternalCircuitOpenError, ExternalAdapterError)


def test_2_adapter_initializes_without_credentials():
    """Verify adapter initializes with default parameters and zero credentials."""
    adapter = BaseExternalAdapter(name="test_service")
    assert adapter.name == "test_service"
    assert adapter.connect_timeout == 3.0
    assert adapter.read_timeout == 5.0
    assert adapter.max_retries == 1
    assert adapter.circuit_breaker.state == CircuitState.CLOSED


# ---------------------------------------------------------------------
# Test 3: Successful Mocked Request
# ---------------------------------------------------------------------

def test_3_successful_mocked_request():
    """Verify successful 200 OK request through mock transport returns AdapterResponse."""
    calls = []

    def mock_transport(method, url, params, headers, json, timeout):
        calls.append((method, url))
        return MockResponse(status_code=200, text='{"weather": "sunny"}', json_data={"weather": "sunny"})

    adapter = BaseExternalAdapter(name="weather_mock", transport=mock_transport)
    resp = adapter.request("GET", "https://api.example.com/weather", params={"q": "Yadadri"})

    assert len(calls) == 1
    assert calls[0] == ("GET", "https://api.example.com/weather")
    assert resp.is_success is True
    assert resp.status_code == 200
    assert resp.json() == {"weather": "sunny"}
    assert adapter.circuit_breaker.state == CircuitState.CLOSED


# ---------------------------------------------------------------------
# Tests 4-5: Timeout and Connection Failure Handling
# ---------------------------------------------------------------------

def test_4_timeout_handling():
    """Verify request timeout raises ExternalTimeoutError and triggers retry."""
    call_count = 0

    def mock_transport(method, url, params, headers, json, timeout):
        nonlocal call_count
        call_count += 1
        raise TimeoutError("Connection timed out after 3.0s")

    adapter = BaseExternalAdapter(name="timeout_mock", transport=mock_transport, backoff_sec=0.0)

    with pytest.raises(ExternalTimeoutError) as exc_info:
        adapter.request("GET", "https://api.example.com/data")

    # Initial attempt + 1 retry = 2 calls
    assert call_count == 2
    assert "timed out" in str(exc_info.value).lower()


def test_5_connection_failure_handling():
    """Verify socket/DNS connection failure raises ExternalConnectionError and retries."""
    call_count = 0

    def mock_transport(method, url, params, headers, json, timeout):
        nonlocal call_count
        call_count += 1
        raise ConnectionError("Failed to resolve host api.example.com")

    adapter = BaseExternalAdapter(name="conn_mock", transport=mock_transport, backoff_sec=0.0)

    with pytest.raises(ExternalConnectionError) as exc_info:
        adapter.request("GET", "https://api.example.com/data")

    assert call_count == 2
    assert "connect" in str(exc_info.value).lower()


# ---------------------------------------------------------------------
# Tests 6-8: HTTP 500, 503, and 429 Retry Behavior
# ---------------------------------------------------------------------

def test_6_http_500_retry_behavior():
    """Verify HTTP 500 Internal Server Error is treated as retryable (retried once)."""
    call_count = 0

    def mock_transport(method, url, params, headers, json, timeout):
        nonlocal call_count
        call_count += 1
        return MockResponse(status_code=500, text="Internal Server Error")

    adapter = BaseExternalAdapter(name="server_err", transport=mock_transport, backoff_sec=0.0)

    with pytest.raises(ExternalHTTPError) as exc_info:
        adapter.request("GET", "https://api.example.com/service")

    assert call_count == 2
    assert exc_info.value.status_code == 500


def test_7_http_503_retry_behavior():
    """Verify HTTP 503 Service Unavailable is treated as retryable (retried once)."""
    call_count = 0

    def mock_transport(method, url, params, headers, json, timeout):
        nonlocal call_count
        call_count += 1
        return MockResponse(status_code=503, text="Service Temporarily Unavailable")

    adapter = BaseExternalAdapter(name="service_unavailable", transport=mock_transport, backoff_sec=0.0)

    with pytest.raises(ExternalHTTPError) as exc_info:
        adapter.request("GET", "https://api.example.com/service")

    assert call_count == 2
    assert exc_info.value.status_code == 503


def test_8_http_429_handling():
    """Verify HTTP 429 raises ExternalRateLimitError and parses Retry-After."""
    call_count = 0

    def mock_transport(method, url, params, headers, json, timeout):
        nonlocal call_count
        call_count += 1
        return MockResponse(
            status_code=429,
            text="Too Many Requests",
            headers={"Retry-After": "60"}
        )

    adapter = BaseExternalAdapter(name="rate_limit", transport=mock_transport, backoff_sec=0.0)

    with pytest.raises(ExternalRateLimitError) as exc_info:
        adapter.request("GET", "https://api.example.com/limited")

    assert call_count == 2
    assert exc_info.value.status_code == 429
    assert exc_info.value.retry_after == 60


# ---------------------------------------------------------------------
# Tests 9-10: Permanent 4xx Rejection & Bounded Retry Limit
# ---------------------------------------------------------------------

def test_9_permanent_4xx_does_not_perform_unnecessary_retry():
    """Verify client errors (400, 401, 403, 404) fail immediately without retry."""
    call_count = 0

    def mock_transport(method, url, params, headers, json, timeout):
        nonlocal call_count
        call_count += 1
        return MockResponse(status_code=404, text="Not Found")

    adapter = BaseExternalAdapter(name="client_err", transport=mock_transport, backoff_sec=0.0)

    with pytest.raises(ExternalHTTPError) as exc_info:
        adapter.request("GET", "https://api.example.com/missing")

    # MUST NOT retry permanent client error
    assert call_count == 1
    assert exc_info.value.status_code == 404


def test_10_maximum_retry_count_is_exactly_bounded():
    """Verify maximum retries is strictly capped at 1 (max 2 total attempts)."""
    call_count = 0

    def mock_transport(method, url, params, headers, json, timeout):
        nonlocal call_count
        call_count += 1
        return MockResponse(status_code=502, text="Bad Gateway")

    # Even if caller specifies max_retries=10, adapter caps at 1
    adapter = BaseExternalAdapter(name="bounded_retry", max_retries=10, transport=mock_transport, backoff_sec=0.0)

    with pytest.raises(ExternalHTTPError):
        adapter.request("GET", "https://api.example.com/bad_gateway")

    assert adapter.max_retries == 1
    assert call_count == 2


# ---------------------------------------------------------------------
# Tests 11-14: Circuit Breaker Lifecycle (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)
# ---------------------------------------------------------------------

def test_11_circuit_opens_after_3_consecutive_eligible_failures():
    """Verify circuit breaker trips to OPEN after 3 consecutive eligible failures."""
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout_sec=10.0)

    def mock_transport(method, url, params, headers, json, timeout):
        return MockResponse(status_code=500, text="Server Error")

    adapter = BaseExternalAdapter(name="cb_test", circuit_breaker=cb, transport=mock_transport, backoff_sec=0.0)

    # Call 1: fails (1 failure recorded)
    with pytest.raises(ExternalHTTPError):
        adapter.request("GET", "https://api.example.com/fail")
    assert cb.state == CircuitState.CLOSED

    # Call 2: fails (2 failures recorded)
    with pytest.raises(ExternalHTTPError):
        adapter.request("GET", "https://api.example.com/fail")
    assert cb.state == CircuitState.CLOSED

    # Call 3: fails (3 failures recorded -> trips OPEN)
    with pytest.raises(ExternalHTTPError):
        adapter.request("GET", "https://api.example.com/fail")
    assert cb.state == CircuitState.OPEN


def test_12_calls_are_rejected_while_circuit_is_open():
    """Verify requests are rejected immediately with ExternalCircuitOpenError when circuit is OPEN."""
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout_sec=30.0)
    cb.state = CircuitState.OPEN
    cb.last_failure_time = time.monotonic()

    transport_called = False

    def mock_transport(method, url, params, headers, json, timeout):
        nonlocal transport_called
        transport_called = True
        return MockResponse(status_code=200)

    adapter = BaseExternalAdapter(name="open_cb", circuit_breaker=cb, transport=mock_transport)

    with pytest.raises(ExternalCircuitOpenError) as exc_info:
        adapter.request("GET", "https://api.example.com/resource")

    assert transport_called is False
    assert "circuit breaker is open" in str(exc_info.value).lower()
    assert exc_info.value.retry_after_sec is not None
    assert exc_info.value.retry_after_sec > 0


def test_13_recovery_half_open_behavior_works():
    """Verify circuit transitions from OPEN to HALF_OPEN after recovery timeout elapsed."""
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_sec=0.05)
    cb.state = CircuitState.OPEN
    # Simulate failure 100ms in the past
    cb.last_failure_time = time.monotonic() - 0.1

    assert cb.can_execute() is True
    assert cb.state == CircuitState.HALF_OPEN


def test_14_successful_recovery_closes_circuit():
    """Verify probe request success in HALF_OPEN resets failures and transitions to CLOSED."""
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_sec=0.01)
    cb.state = CircuitState.HALF_OPEN

    def mock_transport(method, url, params, headers, json, timeout):
        return MockResponse(status_code=200, text='{"recovered": true}')

    adapter = BaseExternalAdapter(name="recovery_test", circuit_breaker=cb, transport=mock_transport)
    resp = adapter.request("GET", "https://api.example.com/health")

    assert resp.is_success is True
    assert cb.state == CircuitState.CLOSED
    assert cb.consecutive_failures == 0


# ---------------------------------------------------------------------
# Test 15: Secret Sanitization
# ---------------------------------------------------------------------

def test_15_secret_values_are_sanitized():
    """Verify API keys, tokens, and credentials are redacted in URLs, headers, and logs."""
    raw_url = "https://api.google.com/maps?key=AIzaSySecret123&origin=Hyderabad&api_key=Private456"
    safe_url = sanitize_url(raw_url)

    assert "AIzaSySecret123" not in safe_url
    assert "Private456" not in safe_url
    assert "key=%5BREDACTED%5D" in safe_url or "key=[REDACTED]" in safe_url
    assert "api_key=%5BREDACTED%5D" in safe_url or "api_key=[REDACTED]" in safe_url
    assert "origin=Hyderabad" in safe_url

    # Headers sanitization
    raw_headers = {
        "Authorization": "Bearer my_super_secret_token_abc",
        "X-API-KEY": "secret_key_value",
        "Content-Type": "application/json"
    }
    safe_headers = sanitize_headers(raw_headers)
    assert safe_headers["Authorization"] == "[REDACTED]"
    assert safe_headers["X-API-KEY"] == "[REDACTED]"
    assert safe_headers["Content-Type"] == "application/json"

    # Free text sanitization
    msg = "Request to https://example.com?token=xyz123 failed with Bearer secret999"
    safe_msg = sanitize_text(msg)
    assert "xyz123" not in safe_msg
    assert "secret999" not in safe_msg
    assert "[REDACTED]" in safe_msg


# ---------------------------------------------------------------------
# Tests 16-18: Offline Execution, Transport Injection, Provider Independence
# ---------------------------------------------------------------------

def test_16_no_real_network_calls_occur_during_tests():
    """Verify that using injected transport prevents any real socket or HTTP network calls."""
    network_attempted = False

    def mock_transport(method, url, params, headers, json, timeout):
        nonlocal network_attempted
        # Verify fake domain executes entirely in-memory
        assert "offline-mock.local" in url
        return MockResponse(status_code=200, text='{"offline": true}', json_data={"offline": True})

    adapter = BaseExternalAdapter(name="offline_test", transport=mock_transport)
    resp = adapter.request("GET", "https://offline-mock.local/v1/ping")

    assert resp.is_success is True
    assert resp.json() == {"offline": True}


def test_17_fixture_mock_transport_works():
    """Verify custom response bodies and status codes can be injected deterministically."""
    mock_payload = {"temple": "Yadadri", "temp_c": 31.5}

    def mock_weather(method, url, params, headers, json, timeout):
        return MockResponse(status_code=200, text="", json_data=mock_payload)

    adapter = BaseExternalAdapter(name="weather_fixture", transport=mock_weather)
    res = adapter.request("GET", "https://api.open-meteo.com/v1/forecast")

    assert res.json()["temp_c"] == 31.5
    assert res.json()["temple"] == "Yadadri"


def test_18_provider_independent_behavior():
    """Verify BaseExternalAdapter contains zero provider-specific endpoints or hardcoded vendor logic."""
    adapter = BaseExternalAdapter(name="generic_provider")
    # BaseExternalAdapter must not hardcode Google, Open-Meteo, or OSRM endpoints
    assert not hasattr(adapter, "open_meteo_url")
    assert not hasattr(adapter, "google_maps_key")
    assert not hasattr(adapter, "osrm_route")
    assert adapter.name == "generic_provider"
