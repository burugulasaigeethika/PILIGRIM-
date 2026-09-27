"""
PilgrimAI - MasterAgentCoordinator (Phase F)

Central orchestration engine coordinating query routing, specialist agent dispatch,
execution lifecycle management, and response aggregation.

Core Principles:
- Orchestration Only: Delegates routing to AgentRouter, factual processing to specialist
  agents, and response composition to ResponseAggregator.
- Lifecycle Preservation: Executes specialist agents via BaseAgent.execute(state) to ensure
  standardized timing, tracing, state tracking, and exception containment.
- Zero Direct RAG / Database Access: Interacts with RAG knowledge strictly through specialist agents.
- Zero LLM Generation: Performs no natural language generation directly.
"""

import time
import logging
from typing import Dict, Any, List, Optional

from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState, AgentResponse, AgentRouteDecision
from app.agents.router import AgentRouter
from app.agents.response_aggregator import ResponseAggregator
from app.agents.temple_information_agent import TempleInformationAgent

logger = logging.getLogger(__name__)


class MasterAgentCoordinator:
    """
    Master Coordinator orchestrating the multi-agent execution lifecycle for PilgrimAI.
    """

    def __init__(
        self,
        router: Optional[AgentRouter] = None,
        aggregator: Optional[ResponseAggregator] = None,
        temple_info_agent: Optional[TempleInformationAgent] = None,
        comparison_agent: Optional[Any] = None,
        cross_temple_agent: Optional[Any] = None,
        itinerary_agent: Optional[Any] = None,
        live_weather_agent: Optional[Any] = None,
        budget_agent: Optional[Any] = None,
        live_navigation_agent: Optional[Any] = None,
        voice_multilingual_agent: Optional[Any] = None,
        emergency_agent: Optional[Any] = None,
        recommendation_agent: Optional[Any] = None,
        agents: Optional[Dict[str, BaseAgent]] = None,
        pipeline: Optional[Any] = None,
        memory_manager: Optional[Any] = None
    ):
        self.router = router or AgentRouter()
        self.aggregator = aggregator or ResponseAggregator()
        self.memory_manager = memory_manager

        # Initialize registry of active specialist agents
        if agents is not None:
            self.agents: Dict[str, BaseAgent] = dict(agents)
        else:
            default_temple_agent = temple_info_agent or TempleInformationAgent()
            self.agents = {
                default_temple_agent.name: default_temple_agent
            }
            if comparison_agent is not None:
                self.agents[comparison_agent.name] = comparison_agent
            if cross_temple_agent is not None:
                self.agents[cross_temple_agent.name] = cross_temple_agent
            if itinerary_agent is not None:
                self.agents[itinerary_agent.name] = itinerary_agent
            if live_weather_agent is not None:
                self.agents[live_weather_agent.name] = live_weather_agent
            if budget_agent is not None:
                self.agents[budget_agent.name] = budget_agent
            if live_navigation_agent is not None:
                self.agents[live_navigation_agent.name] = live_navigation_agent
            if voice_multilingual_agent is not None:
                self.agents[voice_multilingual_agent.name] = voice_multilingual_agent
                if hasattr(voice_multilingual_agent, "set_coordinator"):
                    voice_multilingual_agent.set_coordinator(self)
            if emergency_agent is not None:
                self.agents[emergency_agent.name] = emergency_agent
            if recommendation_agent is not None:
                self.agents[recommendation_agent.name] = recommendation_agent

        # Sync active agents with router
        if hasattr(self.router, "register_agent"):
            for agent_name in self.agents:
                self.router.register_agent(agent_name)

        # Initialize sequential multi-intent pipeline
        if pipeline is not None:
            self.pipeline = pipeline
        else:
            from app.agents.multi_intent_pipeline import SequentialMultiIntentPipeline
            self.pipeline = SequentialMultiIntentPipeline(
                router=self.router,
                aggregator=self.aggregator,
                agents=self.agents
            )

    def register_agent(self, agent: BaseAgent) -> None:
        """Dynamically registers an active specialist agent with coordinator, router, and pipeline."""
        self.agents[agent.name] = agent
        if hasattr(self.router, "register_agent"):
            self.router.register_agent(agent.name)
        if hasattr(self.pipeline, "agents"):
            self.pipeline.agents[agent.name] = agent

    def process(self, state: AgentState) -> AgentResponse:
        """
        Main entry point for processing a user request.
        Orchestrates routing, specialist execution, and response aggregation.
        """
        t0 = time.perf_counter()

        # -------------------------------------------------------------
        # 1. State and Query Validation
        # -------------------------------------------------------------
        if not state or not isinstance(state, AgentState):
            err_resp = AgentResponse(
                success=False,
                agent_name="coordinator",
                answer="Invalid agent state provided.",
                sources=[],
                error="Invalid state object",
                latency_ms=0.0
            )
            return self.aggregator.aggregate([err_resp])

        query = state.user_query.strip() if state.user_query else ""
        if not query:
            state.add_trace(
                agent_name="coordinator",
                step_name="validate_input",
                status="failed",
                error="Empty user query"
            )
            empty_resp = AgentResponse(
                success=False,
                agent_name="coordinator",
                answer="Please provide a valid question.",
                sources=[],
                error="Empty query",
                latency_ms=0.0
            )
            state.final_response = empty_resp
            return self.aggregator.aggregate([empty_resp])

        orig_query = query

        # -------------------------------------------------------------
        # 1.1 Memory Context Resolution (Phase I)
        # -------------------------------------------------------------
        if self.memory_manager is not None and state.session_id:
            resolution = self.memory_manager.resolve_query(state.session_id, query)
            if resolution.get("is_ambiguous"):
                clarification_text = resolution.get(
                    "clarification_message",
                    "Which temple are you referring to?"
                )
                ambiguous_resp = AgentResponse(
                    success=False,
                    agent_name="coordinator",
                    answer=clarification_text,
                    sources=[],
                    error="Ambiguous pronoun reference across multiple recent temples.",
                    metadata={"memory_ambiguity": True},
                    latency_ms=(time.perf_counter() - t0) * 1000.0
                )
                state.add_trace(
                    agent_name="coordinator",
                    step_name="memory_ambiguity",
                    status="completed",
                    latency_ms=ambiguous_resp.latency_ms
                )
                state.final_response = ambiguous_resp
                self._record_memory(state.session_id, orig_query, query, ambiguous_resp)
                return ambiguous_resp

            resolved_query = resolution.get("resolved_query", query)
            if resolved_query != query:
                state.intermediate_results["memory"] = {
                    "original_query": orig_query,
                    "resolved_query": resolved_query,
                    "referenced_temple": resolution.get("referenced_temple")
                }
                state.add_trace(
                    agent_name="coordinator",
                    step_name="memory_resolved",
                    status="completed",
                    metadata={
                        "original_query": orig_query,
                        "resolved_query": resolved_query,
                        "referenced_temple": resolution.get("referenced_temple")
                    }
                )
                query = resolved_query
                # Update state query with resolved query for downstream execution
                state.user_query = resolved_query

            # Propagate most recent turn answer for follow-up translation or voice queries
            recent_turns = self.memory_manager.get_recent_turns(state.session_id, limit=1)
            if recent_turns:
                state.intermediate_results["previous_turn_answer"] = recent_turns[-1].response_summary
                state.intermediate_results["previous_turn_query"] = recent_turns[-1].user_query

        # -------------------------------------------------------------
        # 2. Query Routing
        # -------------------------------------------------------------
        t_route_start = time.perf_counter()
        try:
            route_decision: AgentRouteDecision = self.router.route(query)
            if state.intermediate_results.get("_skip_voice_agent") and route_decision.selected_agent == "voice_multilingual":
                # Temporarily unregister voice_multilingual to find underlying domain agent
                self.router.active_agents.discard("voice_multilingual")
                route_decision = self.router.route(query)
                self.router.active_agents.add("voice_multilingual")
            route_latency_ms = (time.perf_counter() - t_route_start) * 1000.0

            # Store routing decision in state
            state.detected_intents = [route_decision.intent]
            state.intermediate_results["route_decision"] = route_decision
            state.add_trace(
                agent_name="coordinator",
                step_name="route",
                status="completed",
                latency_ms=route_latency_ms,
                metadata={
                    "intent": route_decision.intent,
                    "selected_agent": route_decision.selected_agent,
                    "confidence": route_decision.confidence,
                    "reason": route_decision.reason
                }
            )
        except Exception as e:
            route_latency_ms = (time.perf_counter() - t_route_start) * 1000.0
            error_msg = f"Router error: {type(e).__name__}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            state.add_trace(
                agent_name="coordinator",
                step_name="route",
                status="failed",
                latency_ms=route_latency_ms,
                error=error_msg
            )
            fail_resp = AgentResponse(
                success=False,
                agent_name="coordinator",
                answer="An error occurred during query classification.",
                sources=[],
                error=error_msg,
                latency_ms=route_latency_ms
            )
            final_resp = self.aggregator.aggregate([fail_resp])
            state.final_response = final_resp
            return final_resp

        # -------------------------------------------------------------
        # 3. Ambiguous Query Handling (Clarification Route)
        # -------------------------------------------------------------
        if route_decision.intent == "clarification":
            clarification_text = (
                "Which temple would you like information about? "
                "PilgrimAI currently covers 20 major temples in Telangana (e.g., Yadadri, Basara, Bhadrachalam, Srisailam, Dharmapuri, etc.)."
            )
            clarification_resp = AgentResponse(
                success=False,
                agent_name="coordinator",
                answer=clarification_text,
                sources=[],
                error=route_decision.reason,
                metadata=dict(route_decision.metadata),
                latency_ms=(time.perf_counter() - t0) * 1000.0
            )
            state.add_trace(
                agent_name="coordinator",
                step_name="clarification",
                status="completed",
                latency_ms=clarification_resp.latency_ms,
                metadata={"intent": route_decision.intent}
            )
            state.final_response = clarification_resp
            return clarification_resp

        # -------------------------------------------------------------
        # 4. Explicit Unsupported Temple / Out-of-Scope Route
        # -------------------------------------------------------------
        if route_decision.intent == "unsupported":
            unknown_temple = route_decision.metadata.get("detected_unknown_temple")
            if unknown_temple:
                unsupported_text = (
                    f"I don't have verified information for '{unknown_temple}' in the current PilgrimAI knowledge base. "
                    f"PilgrimAI currently covers 20 major pilgrimage temples in Telangana (such as Yadadri, Basara, Bhadrachalam, Srisailam, Dharmapuri, etc.)."
                )
            else:
                unsupported_text = (
                    "I am the PilgrimAI Assistant. I can only provide factual assistance regarding registered pilgrimage temples in Telangana."
                )

            unsupported_resp = AgentResponse(
                success=False,
                agent_name="coordinator",
                answer=unsupported_text,
                sources=[],
                error=route_decision.reason,
                metadata=dict(route_decision.metadata),
                latency_ms=(time.perf_counter() - t0) * 1000.0
            )
            state.add_trace(
                agent_name="coordinator",
                step_name="unsupported",
                status="completed",
                latency_ms=unsupported_resp.latency_ms,
                metadata={"intent": route_decision.intent}
            )
            state.final_response = unsupported_resp
            return unsupported_resp

        # -------------------------------------------------------------
        # 5. Multi-Intent Pipeline Execution
        # -------------------------------------------------------------
        if route_decision.intent == "multi_intent":
            res = self.pipeline.execute(state)
            self._record_memory(state.session_id, orig_query, query, res)
            return res

        # -------------------------------------------------------------
        # 6. Future Unimplemented Intents (Comparison, Itinerary, Aggregation)
        # -------------------------------------------------------------
        is_unimplemented = (
            (route_decision.intent == "itinerary_planning" and "itinerary_planning" not in self.agents) or
            (route_decision.intent == "cross_temple_aggregation" and "cross_temple_aggregation" not in self.agents) or
            (route_decision.intent == "comparison" and "comparison" not in self.agents) or
            route_decision.selected_agent not in self.agents
        )
        if is_unimplemented:
            target_agent = route_decision.metadata.get("target_agent", route_decision.intent)
            future_text = (
                f"The requested capability ('{route_decision.intent.replace('_', ' ').title()}') "
                f"is not yet available in the current agent build."
            )
            future_resp = AgentResponse(
                success=False,
                agent_name="coordinator",
                answer=future_text,
                sources=[],
                error=route_decision.reason,
                metadata=dict(route_decision.metadata),
                latency_ms=(time.perf_counter() - t0) * 1000.0
            )
            state.add_trace(
                agent_name="coordinator",
                step_name="unimplemented_intent",
                status="completed",
                latency_ms=future_resp.latency_ms,
                metadata={"intent": route_decision.intent, "selected_agent": route_decision.selected_agent}
            )
            state.final_response = future_resp
            return future_resp

        # -------------------------------------------------------------
        # 6. Specialist Agent Execution
        # -------------------------------------------------------------
        selected_agent = self.agents[route_decision.selected_agent]
        state.add_trace(
            agent_name="coordinator",
            step_name="dispatch",
            status="started",
            metadata={"target_agent": selected_agent.name}
        )

        t_agent_start = time.perf_counter()
        # Execute specialist via public BaseAgent.execute lifecycle
        specialist_response = selected_agent.execute(state)
        agent_latency_ms = (time.perf_counter() - t_agent_start) * 1000.0

        state.add_trace(
            agent_name="coordinator",
            step_name="dispatch",
            status="completed" if specialist_response.success else "failed",
            latency_ms=agent_latency_ms,
            error=specialist_response.error
        )

        # -------------------------------------------------------------
        # 7. Response Aggregation
        # -------------------------------------------------------------
        t_agg_start = time.perf_counter()
        try:
            final_aggregated_response = self.aggregator.aggregate([specialist_response])
            agg_latency_ms = (time.perf_counter() - t_agg_start) * 1000.0
            state.add_trace(
                agent_name="coordinator",
                step_name="aggregate",
                status="completed",
                latency_ms=agg_latency_ms
            )
        except Exception as e:
            agg_latency_ms = (time.perf_counter() - t_agg_start) * 1000.0
            error_msg = f"Aggregator error: {type(e).__name__}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            state.add_trace(
                agent_name="coordinator",
                step_name="aggregate",
                status="failed",
                latency_ms=agg_latency_ms,
                error=error_msg
            )
            agg_fail_resp = AgentResponse(
                success=False,
                agent_name="coordinator",
                answer="I encountered an unexpected error assembling the response. Please try asking again.",
                sources=[],
                error=error_msg,
                latency_ms=agg_latency_ms
            )
            state.final_response = agg_fail_resp
            return agg_fail_resp

        # Safety guard: ensure final aggregated response answer is never empty
        if not final_aggregated_response.answer or not final_aggregated_response.answer.strip():
            final_aggregated_response.answer = (
                "I could not retrieve details for this request. Please specify a temple name (e.g., Yadadri, Basara) "
                "or rephrase your question regarding timings, budget, weather, or navigation."
            )

        # Record coordinator total execution time in metadata
        total_latency_ms = (time.perf_counter() - t0) * 1000.0
        final_aggregated_response.metadata["coordinator_latency_ms"] = total_latency_ms

        state.add_trace(
            agent_name="coordinator",
            step_name="complete",
            status="completed" if final_aggregated_response.success else "failed",
            latency_ms=total_latency_ms
        )

        # -------------------------------------------------------------
        # 8. State Finalization
        # -------------------------------------------------------------
        self._record_memory(state.session_id, orig_query, query, final_aggregated_response)
        state.final_response = final_aggregated_response
        return final_aggregated_response

    def _record_memory(
        self,
        session_id: str,
        orig_query: str,
        resolved_query: str,
        response: AgentResponse
    ):
        """Records a completed turn in the conversation memory manager if present."""
        if self.memory_manager is not None and session_id:
            try:
                temples = self.router._detect_temples(resolved_query)
                self.memory_manager.add_turn(
                    session_id=session_id,
                    user_query=orig_query,
                    resolved_query=resolved_query,
                    detected_intents=[response.agent_name] if response.agent_name else [],
                    identified_temples=temples,
                    response_summary=response.answer[:200] if response.answer else "",
                    metadata=dict(response.metadata)
                )
            except Exception as e:
                logger.warning(f"Failed to record turn in memory: {e}")
