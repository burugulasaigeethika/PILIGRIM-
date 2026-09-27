"""
PilgrimAI - Base Agent Contract (Phase A)

Defines the abstract BaseAgent class establishing the standard execution lifecycle,
timing, tracing, and exception handling for all specialist agents.
Strictly decoupled from RAG retrieval and vector databases.
"""

import abc
import time
import logging
from typing import Optional

from app.agents.state import AgentState, AgentResponse

logger = logging.getLogger(__name__)


class BaseAgent(abc.ABC):
    """
    Abstract foundational contract for all specialist agents in the PilgrimAI ecosystem.
    
    Subclasses must define `name`, `description`, and implement `_run(state)`.
    `execute(state)` establishes a standardized lifecycle:
      1. Initializes timing and sets active agent in state.
      2. Calls subclass `_run(state)`.
      3. Captures success or handles exceptions consistently.
      4. Appends execution trace to state.
      5. Stores intermediate output in state.
      6. Returns a normalized AgentResponse.
    """

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abc.abstractmethod
    def _run(self, state: AgentState) -> AgentResponse:
        """
        Subclass-specific agent logic.
        Must be implemented by every concrete specialist agent.
        """
        pass

    def execute(self, state: AgentState) -> AgentResponse:
        """
        Executes the agent lifecycle with timing, state tracing, and error protection.
        """
        previous_agent = state.active_agent
        state.active_agent = self.name
        t0 = time.perf_counter()

        try:
            # Delegate to specialist agent implementation
            response = self._run(state)

            latency_ms = (time.perf_counter() - t0) * 1000.0

            # Normalize response fields
            if not response.agent_name:
                response.agent_name = self.name
            if response.latency_ms is None:
                response.latency_ms = latency_ms

            # Record execution trace
            trace_status = "completed" if response.success else "failed"
            state.add_trace(
                agent_name=self.name,
                step_name="execute",
                status=trace_status,
                latency_ms=latency_ms,
                error=response.error,
                metadata=response.metadata
            )

            # Record intermediate result in shared state
            state.intermediate_results[self.name] = response
            return response

        except Exception as e:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"Error executing agent '{self.name}': {error_msg}", exc_info=True)

            # Record failure in execution trace
            state.add_trace(
                agent_name=self.name,
                step_name="execute",
                status="failed",
                latency_ms=latency_ms,
                error=error_msg
            )

            # Construct standardized error response
            err_response = AgentResponse(
                success=False,
                agent_name=self.name,
                answer="",
                sources=[],
                error=error_msg,
                latency_ms=latency_ms
            )

            state.intermediate_results[self.name] = err_response
            return err_response

        finally:
            state.active_agent = previous_agent
