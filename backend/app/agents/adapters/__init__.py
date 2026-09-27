"""
PilgrimAI - External API Adapters (Phase O1)
"""

from app.agents.adapters.external_adapter import (
    BaseExternalAdapter,
    AdapterResponse,
    CircuitBreaker,
    CircuitState,
    ExternalAdapterError,
    ExternalTimeoutError,
    ExternalConnectionError,
    ExternalHTTPError,
    ExternalRateLimitError,
    ExternalCircuitOpenError,
    sanitize_text,
    sanitize_url,
    sanitize_headers,
)

__all__ = [
    "BaseExternalAdapter",
    "AdapterResponse",
    "CircuitBreaker",
    "CircuitState",
    "ExternalAdapterError",
    "ExternalTimeoutError",
    "ExternalConnectionError",
    "ExternalHTTPError",
    "ExternalRateLimitError",
    "ExternalCircuitOpenError",
    "sanitize_text",
    "sanitize_url",
    "sanitize_headers",
]
