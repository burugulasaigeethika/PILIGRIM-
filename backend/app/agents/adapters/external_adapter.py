"""
PilgrimAI - External API Firewall / BaseExternalAdapter (Phase O1)

Provides a lightweight, provider-independent, resilient gateway for external web requests.
Protects the PilgrimAI ecosystem with:
- Configurable connect and read timeout bounds.
- Bounded retry policy (max 1 retry) for transient errors (timeout, connection error, 5xx, 429).
- Immediate failure for non-retryable client errors (permanent 4xx).
- Lightweight in-process circuit breaker (CLOSED -> OPEN -> HALF_OPEN -> CLOSED).
- Strictly sanitized logs, exceptions, and telemetry (zero secret/credential leakage).
- Deterministic offline test / mock transport dependency injection.
- Zero network calls during import or initialization.
"""

import time
import re
import urllib.parse
import logging
from enum import Enum
from typing import Dict, Any, Optional, Tuple, Callable

logger = logging.getLogger(__name__)

# Sensitive token identifiers that must be redacted from URLs, headers, and logs
_SENSITIVE_TOKENS = {
    "api_key", "apikey", "key", "secret", "password",
    "token", "authorization", "credential", "auth"
}


# =====================================================================
# Typed Exception Hierarchy
# =====================================================================

class ExternalAdapterError(Exception):
    """Base exception for all external API adapter failures."""
    def __init__(self, message: str, sanitized_url: str = ""):
        self.raw_message = message
        self.sanitized_url = sanitize_url(sanitized_url) if sanitized_url else ""
        safe_msg = sanitize_text(message)
        super().__init__(safe_msg)


class ExternalTimeoutError(ExternalAdapterError):
    """Raised when an external request exceeds connect or read timeout."""
    pass


class ExternalConnectionError(ExternalAdapterError):
    """Raised when an external service is unreachable due to network/socket/DNS issues."""
    pass


class ExternalHTTPError(ExternalAdapterError):
    """Raised when an external service returns an unhandled HTTP 4xx or 5xx status."""
    def __init__(self, message: str, status_code: int, response_body: Optional[str] = None, sanitized_url: str = ""):
        self.status_code = status_code
        self.response_body = sanitize_text(response_body) if response_body else None
        super().__init__(message, sanitized_url=sanitized_url)


class ExternalRateLimitError(ExternalHTTPError):
    """Raised when an external service returns HTTP 429 Too Many Requests."""
    def __init__(self, message: str, retry_after: Optional[int] = None, sanitized_url: str = ""):
        self.retry_after = retry_after
        super().__init__(message, status_code=429, sanitized_url=sanitized_url)


class ExternalCircuitOpenError(ExternalAdapterError):
    """Raised when requests are rejected because the circuit breaker is OPEN."""
    def __init__(self, message: str, retry_after_sec: Optional[float] = None):
        self.retry_after_sec = retry_after_sec
        super().__init__(message)


# =====================================================================
# Secret Sanitization Helpers
# =====================================================================

def sanitize_url(url: str) -> str:
    """
    Sanitizes URL query parameters by redacting any sensitive parameter keys.
    Example: https://api.example.com/v1?query=Basara&key=AIzaSy123 -> ...&key=[REDACTED]
    """
    if not url:
        return ""
    try:
        parsed = urllib.parse.urlparse(url)
        if not parsed.query:
            return url
        params = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        sanitized_params = []
        for k, v in params:
            k_lower = k.lower().replace("-", "_")
            if any(sens in k_lower for sens in _SENSITIVE_TOKENS):
                sanitized_params.append((k, "[REDACTED]"))
            else:
                sanitized_params.append((k, v))
        new_query = urllib.parse.urlencode(sanitized_params)
        return urllib.parse.urlunparse((
            parsed.scheme, parsed.netloc, parsed.path,
            parsed.params, new_query, parsed.fragment
        ))
    except Exception:
        return "[URL_SANITIZATION_FAILED]"


def sanitize_headers(headers: Optional[Dict[str, str]]) -> Dict[str, str]:
    """
    Sanitizes HTTP headers by masking authorization tokens, API keys, and secrets.
    """
    if not headers:
        return {}
    safe_headers = {}
    for k, v in headers.items():
        k_lower = k.lower().replace("-", "_")
        if any(sens in k_lower for sens in _SENSITIVE_TOKENS):
            safe_headers[k] = "[REDACTED]"
        else:
            safe_headers[k] = str(v)
    return safe_headers


def sanitize_text(text: Optional[str]) -> str:
    """
    Redacts obvious credential patterns from error messages and log outputs.
    """
    if not text:
        return ""
    s = str(text)
    # Redact query params in free text
    for token in _SENSITIVE_TOKENS:
        pattern = rf"(?i)\b({token}=)([^&\s]+)"
        s = re.sub(pattern, r"\1[REDACTED]", s)
        header_pattern = rf"(?i)\b({token}:\s*)([^\r\n,]+)"
        s = re.sub(header_pattern, r"\1[REDACTED]", s)
    # Redact Bearer tokens
    s = re.sub(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*", "Bearer [REDACTED]", s)
    return s


# =====================================================================
# Circuit Breaker Infrastructure
# =====================================================================

class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """
    Lightweight in-process circuit breaker preventing cascade failures.
    
    Transitions:
      CLOSED --(failures >= threshold)--> OPEN
      OPEN   --(elapsed >= recovery_timeout)--> HALF_OPEN
      HALF_OPEN --(probe success)--> CLOSED
      HALF_OPEN --(probe failure)--> OPEN
    """

    def __init__(self, failure_threshold: int = 3, recovery_timeout_sec: float = 30.0):
        self.failure_threshold = max(1, failure_threshold)
        self.recovery_timeout_sec = max(0.1, recovery_timeout_sec)
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.last_failure_time: Optional[float] = None

    def can_execute(self) -> bool:
        """
        Determines whether a new execution attempt is permitted.
        """
        if self.state == CircuitState.CLOSED:
            return True

        now = time.monotonic()
        if self.state == CircuitState.OPEN:
            if self.last_failure_time and (now - self.last_failure_time) >= self.recovery_timeout_sec:
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker transitioning from OPEN to HALF_OPEN (probing recovery).")
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            # Allow single probe request
            return True

        return False

    def record_success(self) -> None:
        """Records a successful call, resetting the circuit breaker."""
        if self.state != CircuitState.CLOSED:
            logger.info("Circuit breaker recovered successfully: transitioning to CLOSED.")
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.last_failure_time = None

    def record_failure(self) -> None:
        """Records an eligible failure. Trips to OPEN if threshold reached."""
        self.consecutive_failures += 1
        self.last_failure_time = time.monotonic()

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning("Circuit breaker probe failed in HALF_OPEN: reverting to OPEN.")
        elif self.consecutive_failures >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker tripped to OPEN after {self.consecutive_failures} consecutive failures. "
                f"Rejecting requests for {self.recovery_timeout_sec}s."
            )

    def reset(self) -> None:
        """Manually forces the circuit breaker back to CLOSED."""
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.last_failure_time = None


# =====================================================================
# Standardized Adapter Response DTO
# =====================================================================

class AdapterResponse:
    """Strongly-typed response payload from an external adapter call."""

    def __init__(
        self,
        status_code: int,
        text: str,
        json_data: Any = None,
        headers: Optional[Dict[str, str]] = None,
        latency_ms: float = 0.0
    ):
        self.status_code = status_code
        self.text = text
        self.json_data = json_data
        self.headers = headers or {}
        self.latency_ms = latency_ms

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> Any:
        if self.json_data is not None:
            return self.json_data
        import json
        self.json_data = json.loads(self.text)
        return self.json_data


# =====================================================================
# BaseExternalAdapter
# =====================================================================

class BaseExternalAdapter:
    """
    Provider-independent, resilient gateway for all external web API integrations.
    Provides strict timeout bounding, max-1 retry policy, circuit breaker isolation,
    typed exception mapping, and secret sanitization.
    """

    def __init__(
        self,
        name: str = "generic",
        connect_timeout: float = 3.0,
        read_timeout: float = 5.0,
        max_retries: int = 1,
        backoff_sec: float = 0.1,
        circuit_breaker: Optional[CircuitBreaker] = None,
        transport: Optional[Callable] = None
    ):
        self.name = name
        self.connect_timeout = float(connect_timeout)
        self.read_timeout = float(read_timeout)
        # Strictly bounded: maximum automatic retries = 1 (prompt requirement)
        self.max_retries = min(1, max(0, int(max_retries)))
        self.backoff_sec = max(0.0, float(backoff_sec))
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.transport = transport
        self._session = None

    def _get_session(self):
        """Lazy initialization of requests.Session to avoid network/socket init at import time."""
        if self._session is None:
            import requests
            self._session = requests.Session()
        return self._session

    def is_retryable(self, exc: Exception) -> bool:
        """
        Classifies whether an exception or HTTP response is eligible for retry:
        - Retryable: Timeout, Connection Error, HTTP 5xx, HTTP 429.
        - Non-retryable: Permanent 4xx (400, 401, 403, 404, 422, etc.).
        """
        if isinstance(exc, (ExternalTimeoutError, ExternalConnectionError, ExternalRateLimitError)):
            return True
        if isinstance(exc, ExternalHTTPError):
            return exc.status_code >= 500
        return False

    def request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Any] = None,
        timeout: Optional[Tuple[float, float]] = None
    ) -> AdapterResponse:
        """
        Executes an HTTP request protected by circuit breaker, timeouts, and bounded retries.
        """
        safe_url = sanitize_url(url)

        # 1. Circuit Breaker Check
        if not self.circuit_breaker.can_execute():
            remaining_sec = None
            if self.circuit_breaker.last_failure_time:
                elapsed = time.monotonic() - self.circuit_breaker.last_failure_time
                remaining_sec = max(0.0, self.circuit_breaker.recovery_timeout_sec - elapsed)
            err_msg = (
                f"External service '{self.name}' circuit breaker is OPEN. "
                f"Request rejected without network dispatch."
            )
            logger.warning(err_msg)
            raise ExternalCircuitOpenError(err_msg, retry_after_sec=remaining_sec)

        effective_timeout = timeout or (self.connect_timeout, self.read_timeout)
        attempts = 0
        max_attempts = 1 + self.max_retries  # At most 2 attempts (1 initial + 1 retry)

        last_exception: Optional[Exception] = None

        while attempts < max_attempts:
            attempts += 1
            t0 = time.perf_counter()

            try:
                # 2. Dispatch via Mock Transport (Offline/Test) or Real Session
                raw_resp = self._dispatch_transport(
                    method=method.upper(),
                    url=url,
                    params=params,
                    headers=headers,
                    json_data=json_data,
                    timeout=effective_timeout
                )

                latency_ms = (time.perf_counter() - t0) * 1000.0

                # 3. Classify HTTP Status Code
                status_code = getattr(raw_resp, "status_code", 200)
                resp_text = getattr(raw_resp, "text", "")
                resp_headers = dict(getattr(raw_resp, "headers", {}))

                # Check for rate limit (429)
                if status_code == 429:
                    retry_after = None
                    if "Retry-After" in resp_headers:
                        try:
                            retry_after = int(resp_headers["Retry-After"])
                        except (ValueError, TypeError):
                            retry_after = None
                    raise ExternalRateLimitError(
                        f"External service '{self.name}' returned HTTP 429 (Rate Limit Exceeded)",
                        retry_after=retry_after,
                        sanitized_url=safe_url
                    )

                # Check for Server Error (5xx)
                if status_code >= 500:
                    raise ExternalHTTPError(
                        f"External service '{self.name}' returned HTTP {status_code} (Server Error)",
                        status_code=status_code,
                        response_body=resp_text,
                        sanitized_url=safe_url
                    )

                # Check for Permanent Client Error (4xx except 429)
                if 400 <= status_code < 500:
                    # Non-retryable permanent client error
                    raise ExternalHTTPError(
                        f"External service '{self.name}' returned HTTP {status_code} (Client Error)",
                        status_code=status_code,
                        response_body=resp_text,
                        sanitized_url=safe_url
                    )

                # 4. Request Succeeded
                parsed_json = None
                if hasattr(raw_resp, "json"):
                    try:
                        parsed_json = raw_resp.json()
                    except Exception:
                        parsed_json = None

                adapter_response = AdapterResponse(
                    status_code=status_code,
                    text=resp_text,
                    json_data=parsed_json,
                    headers=resp_headers,
                    latency_ms=latency_ms
                )

                # Record success on circuit breaker
                self.circuit_breaker.record_success()
                return adapter_response

            except Exception as e:
                # Map low-level library errors to typed adapter exceptions
                typed_exc = self._normalize_exception(e, safe_url)
                last_exception = typed_exc

                # Check if eligible for bounded retry
                if attempts < max_attempts and self.is_retryable(typed_exc):
                    logger.warning(
                        f"ExternalAdapter '{self.name}' attempt {attempts} failed with retryable error: "
                        f"{type(typed_exc).__name__}: {typed_exc}. Retrying in {self.backoff_sec}s..."
                    )
                    if self.backoff_sec > 0:
                        time.sleep(self.backoff_sec)
                    continue

                # Permanent failure or retries exhausted
                self.circuit_breaker.record_failure()
                raise typed_exc

        # Safety fallback
        if last_exception:
            self.circuit_breaker.record_failure()
            raise last_exception
        raise ExternalAdapterError(f"Request to '{safe_url}' failed without explicit exception.", sanitized_url=safe_url)

    def _dispatch_transport(
        self,
        method: str,
        url: str,
        params: Optional[Dict],
        headers: Optional[Dict],
        json_data: Optional[Any],
        timeout: Tuple[float, float]
    ):
        """Dispatches request via injected transport or requests session."""
        if self.transport is not None:
            return self.transport(
                method=method,
                url=url,
                params=params,
                headers=headers,
                json=json_data,
                timeout=timeout
            )

        session = self._get_session()
        return session.request(
            method=method,
            url=url,
            params=params,
            headers=headers,
            json=json_data,
            timeout=timeout
        )

    def _normalize_exception(self, exc: Exception, safe_url: str) -> ExternalAdapterError:
        """Normalizes any library-specific or system exception into a strongly-typed adapter error."""
        if isinstance(exc, ExternalAdapterError):
            return exc

        exc_str = str(exc)
        exc_type_name = type(exc).__name__.lower()

        if "timeout" in exc_type_name or "timed out" in exc_str.lower():
            return ExternalTimeoutError(
                f"External request to '{safe_url}' timed out: {exc_str}",
                sanitized_url=safe_url
            )

        if "connection" in exc_type_name or "connect" in exc_str.lower() or "socket" in exc_str.lower() or "dns" in exc_str.lower():
            return ExternalConnectionError(
                f"Failed to connect to external service at '{safe_url}': {exc_str}",
                sanitized_url=safe_url
            )

        return ExternalAdapterError(
            f"ExternalAdapter '{self.name}' error during request to '{safe_url}': {exc_str}",
            sanitized_url=safe_url
        )
