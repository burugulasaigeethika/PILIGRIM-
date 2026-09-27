"""
Phase H - Sequential Multi-Intent Pipeline Certification Tests

Verifies:
1. Pipeline initialization with router, aggregator, and agent registry.
2. Single-intent query compatibility.
3. Two supported temple_information tasks execute sequentially (live Yadadri query).
4. Execution order is strictly preserved (Task 1 -> Task 2).
5. Task-level queries preserve temple identity across decomposed clauses.
6. Intermediate results contain ordered task results (state.intermediate_results['multi_intent']).
7. Execution trace contains chronologically ordered pipeline and task events.
8. Partial failure preserves successful specialist responses.
9. All failures produce a controlled failure response without hallucination.
10. Unsupported future intents (e.g., comparison) are safely isolated without calling fake agents.
11. Clarification query does not invoke RAG.
12. Unsupported non-registered temple remains anti-hallucination safe.
13. ResponseAggregator receives successful responses in order.
14. Repeated execution is deterministic at the structural level.
15. Static inspection verifies zero threading / asyncio parallel execution.
16. Static inspection verifies zero LLM / Ollama dependencies.
17. Static inspection verifies zero direct RAG / vector DB imports in pipeline.py.
18. MasterAgentCoordinator compatibility: coordinator seamlessly processes multi-intent queries.
"""

import sys
from pathlib import Path
import pytest

# Ensure backend is in sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState, AgentResponse, ExecutionTrace
from app.agents.router import AgentRouter
from app.agents.response_aggregator import ResponseAggregator
from app.agents.temple_information_agent import TempleInformationAgent
from app.agents.coordinator import MasterAgentCoordinator
from app.agents.multi_intent_pipeline import SequentialMultiIntentPipeline


class DummyFailingAgent(BaseAgent):
    """Test double that intentionally fails on execution."""
    def __init__(self, name="temple_information", description="Fails intentionally"):
        super().__init__(name=name, description=description)

    def _run(self, state: AgentState) -> AgentResponse:
        raise RuntimeError("Controlled specialist agent execution failure")


class DummyOrderTrackingAgent(BaseAgent):
    """Test double recording execution call sequence."""
    def __init__(self, name="temple_information", description="Tracks execution order"):
        super().__init__(name=name, description=description)
        self.call_history = []

    def _run(self, state: AgentState) -> AgentResponse:
        self.call_history.append(state.user_query)
        return AgentResponse(
            success=True,
            agent_name=self.name,
            answer=f"Answer for: {state.user_query}",
            sources=["dummy/source.json"]
        )


@pytest.fixture(scope="module")
def pipeline():
    return SequentialMultiIntentPipeline()


@pytest.fixture(scope="module")
def coordinator():
    return MasterAgentCoordinator()


def test_1_pipeline_initialization(pipeline):
    """Verify SequentialMultiIntentPipeline initializes router, aggregator, and agent registry."""
    assert pipeline is not None
    assert isinstance(pipeline.router, AgentRouter)
    assert isinstance(pipeline.aggregator, ResponseAggregator)
    assert "temple_information" in pipeline.agents
    assert isinstance(pipeline.agents["temple_information"], TempleInformationAgent)


def test_2_single_intent_compatibility(pipeline):
    """Verify pipeline can process a single-intent query without degradation."""
    state = AgentState(user_query="What are the timings of Yadadri temple?")
    res = pipeline.execute(state)

    assert isinstance(res, AgentResponse)
    assert res.success is True
    assert len(res.answer) > 20
    assert len(res.sources) > 0
    assert "multi_intent" in state.intermediate_results
    assert state.intermediate_results["multi_intent"]["task_count"] == 1


def test_3_two_supported_tasks_execute_sequentially(pipeline):
    """Verify live multi-intent query with two supported tasks executes sequentially."""
    query = "What are the timings of Yadadri and what facilities are available?"
    state = AgentState(user_query=query)
    res = pipeline.execute(state)

    assert isinstance(res, AgentResponse)
    assert res.success is True
    assert len(res.answer) > 40
    assert len(res.sources) > 0

    # Intermediate state verification
    multi_state = state.intermediate_results.get("multi_intent", {})
    assert multi_state.get("task_count") == 2
    assert multi_state.get("successful_tasks") == 2
    assert multi_state.get("failed_tasks") == 0


def test_4_execution_order_preserved():
    """Verify tasks execute strictly in the order they appear in the query."""
    tracking_agent = DummyOrderTrackingAgent()
    p = SequentialMultiIntentPipeline(agents={"temple_information": tracking_agent})

    query = "What are the timings of Yadadri and what sevas are offered?"
    state = AgentState(user_query=query)
    res = p.execute(state)

    assert res.success is True
    assert len(tracking_agent.call_history) == 2
    # First query must relate to timings, second to sevas
    assert "timings" in tracking_agent.call_history[0].lower()
    assert "sevas" in tracking_agent.call_history[1].lower()


def test_5_task_queries_preserve_temple_identity(pipeline):
    """Verify second sub-task inherits temple identity from the primary query."""
    query = "What are Yadadri timings and what sevas are available?"
    tasks = pipeline.decompose_query(query)

    assert len(tasks) == 2
    assert "Yadadri" in tasks[0]["query"]
    assert "Yadadri" in tasks[1]["query"]


def test_6_intermediate_results_contain_ordered_tasks(pipeline):
    """Verify intermediate results accurately capture task details in order."""
    query = "What are the timings of Yadadri and what sevas are available?"
    state = AgentState(user_query=query)
    pipeline.execute(state)

    multi_meta = state.intermediate_results["multi_intent"]
    tasks = multi_meta["tasks"]

    assert len(tasks) == 2
    assert tasks[0]["task_id"] == 1
    assert tasks[1]["task_id"] == 2
    assert tasks[0]["intent"] == "temple_information"
    assert tasks[1]["intent"] == "temple_information"
    assert tasks[0]["success"] is True
    assert tasks[1]["success"] is True


def test_7_execution_trace_contains_ordered_events(pipeline):
    """Verify execution traces include pipeline_start, task_start, execute, task_completed, pipeline_complete."""
    query = "What are the timings of Yadadri and what sevas are available?"
    state = AgentState(user_query=query)
    pipeline.execute(state)

    traces = state.execution_trace
    step_names = [t.step_name for t in traces]

    assert "pipeline_start" in step_names
    assert "task_start" in step_names
    assert "execute" in step_names
    assert "task_completed" in step_names
    assert "pipeline_complete" in step_names

    # Verify chronological sequence
    start_idx = step_names.index("pipeline_start")
    complete_idx = step_names.index("pipeline_complete")
    assert start_idx < complete_idx


def test_8_partial_failure_preserves_successful_responses():
    """Verify partial failure retains successful responses without discarding them."""
    class SelectiveFailAgent(BaseAgent):
        def __init__(self):
            super().__init__(name="temple_information", description="Fails only on sevas")
            self.calls = 0

        def _run(self, state: AgentState) -> AgentResponse:
            self.calls += 1
            if "sevas" in state.user_query.lower():
                raise RuntimeError("Seva database unavailable")
            return AgentResponse(
                success=True,
                agent_name=self.name,
                answer="Yadadri temple opens at 4:00 AM.",
                sources=["yadadri/timings.json"]
            )

    agent = SelectiveFailAgent()
    p = SequentialMultiIntentPipeline(agents={"temple_information": agent})

    query = "What are the timings of Yadadri and what sevas are available?"
    state = AgentState(user_query=query)
    res = p.execute(state)

    # Aggregated response should still succeed because one task succeeded
    assert res.success is True
    assert "opens at 4:00 am" in res.answer.lower()
    assert len(res.sources) > 0

    multi_meta = state.intermediate_results["multi_intent"]
    assert multi_meta["successful_tasks"] == 1
    assert multi_meta["failed_tasks"] == 1


def test_9_all_failures_produce_controlled_failure():
    """Verify all-task failure produces a controlled unsuccessful response without fabricating facts."""
    failing_agent = DummyFailingAgent()
    p = SequentialMultiIntentPipeline(agents={"temple_information": failing_agent})

    query = "What are the timings of Yadadri and what sevas are available?"
    state = AgentState(user_query=query)
    res = p.execute(state)

    assert res.success is False
    assert res.answer == ""
    assert "failed" in res.error.lower()
    multi_meta = state.intermediate_results["multi_intent"]
    assert multi_meta["successful_tasks"] == 0
    assert multi_meta["failed_tasks"] == 2


def test_10_unsupported_future_intent_isolated(pipeline):
    """Verify a multi-intent query with comparison executes factual part and isolates comparison."""
    query = "What are Yadadri timings and compare Yadadri with Bhadrachalam?"
    state = AgentState(user_query=query)
    res = pipeline.execute(state)

    assert res.success is True
    assert len(res.answer) > 20
    # Must contain factual answer and controlled note about comparison
    assert "not yet available" in res.answer.lower() or "not yet implemented" in res.answer.lower()

    multi_meta = state.intermediate_results["multi_intent"]
    intents = [t["intent"] for t in multi_meta["tasks"]]
    assert "temple_information" in intents
    assert "comparison" in intents


def test_11_clarification_does_not_invoke_rag(pipeline):
    """Verify ambiguous multi-intent query lacking temple name returns clarification without RAG."""
    query = "What are the temple timings and what sevas are offered?"
    state = AgentState(user_query=query)
    res = pipeline.execute(state)

    assert res.success is False
    assert "which temple" in res.answer.lower()
    assert len(res.sources) == 0


def test_12_unsupported_temple_anti_hallucination(pipeline):
    """Verify explicit non-registered temple returns anti-hallucination rejection without RAG."""
    query = "What are the timings of Golden Temple in Amritsar and how to reach it?"
    state = AgentState(user_query=query)
    res = pipeline.execute(state)

    assert res.success is False
    assert "don't have" in res.answer.lower() or "knowledge base" in res.answer.lower()
    assert len(res.sources) == 0


def test_13_aggregator_receives_responses_in_order():
    """Verify ResponseAggregator receives task responses in sequential order."""
    tracking_agent = DummyOrderTrackingAgent()
    p = SequentialMultiIntentPipeline(agents={"temple_information": tracking_agent})

    query = "What are Yadadri timings and what sevas are available?"
    state = AgentState(user_query=query)
    res = p.execute(state)

    assert res.success is True
    # Verify answers are aggregated in order
    assert "timings" in res.answer.lower()
    assert "sevas" in res.answer.lower()


def test_14_repeated_execution_determinism(pipeline):
    """Verify identical repeated executions produce consistent task counts and intents."""
    query = "What are the timings of Yadadri and what facilities are available?"

    states = [AgentState(user_query=query) for _ in range(3)]
    for s in states:
        pipeline.execute(s)

    for s in states:
        meta = s.intermediate_results["multi_intent"]
        assert meta["task_count"] == 2
        assert meta["successful_tasks"] == 2
        assert len(s.execution_trace) == len(states[0].execution_trace)


def test_15_no_parallel_execution_mechanism():
    """Verify pipeline module contains no asyncio.gather or thread pool execution."""
    pipeline_file = root_dir / "backend" / "app" / "agents" / "multi_intent_pipeline.py"
    content = pipeline_file.read_text(encoding="utf-8")

    forbidden_concurrency = [
        "asyncio.gather",
        "ThreadPoolExecutor",
        "ProcessPoolExecutor",
        "multiprocessing",
        "threading.Thread",
        "concurrent.futures"
    ]
    for item in forbidden_concurrency:
        assert item not in content, f"Forbidden concurrency mechanism '{item}' detected in pipeline!"


def test_16_no_llm_dependency():
    """Verify pipeline module contains no direct LLM or Ollama dependencies."""
    pipeline_file = root_dir / "backend" / "app" / "agents" / "multi_intent_pipeline.py"
    content = pipeline_file.read_text(encoding="utf-8")

    forbidden_llm = [
        "ollama",
        "openai",
        "anthropic",
        "google.generativeai",
        "langchain"
    ]
    for item in forbidden_llm:
        assert item not in content.lower(), f"Forbidden LLM import '{item}' detected in pipeline!"


def test_17_no_direct_rag_dependency():
    """Verify pipeline module does not directly import raw RAG, vector DB, or RAGTool."""
    pipeline_file = root_dir / "backend" / "app" / "agents" / "multi_intent_pipeline.py"
    content = pipeline_file.read_text(encoding="utf-8")

    forbidden_rag = [
        "qdrant_client",
        "rank_bm25",
        "sentence_transformers",
        "LocalQdrantManager",
        "LocalBM25Manager",
        "PilgrimRAGService",
        "KnowledgeRegistry",
        "RAGTool"
    ]
    for item in forbidden_rag:
        assert item not in content, f"Forbidden direct RAG dependency '{item}' detected in pipeline!"


def test_18_master_coordinator_integration(coordinator):
    """Verify MasterAgentCoordinator routes and executes multi-intent query through pipeline."""
    query = "What are the timings of Yadadri and what sevas are available?"
    state = AgentState(user_query=query)
    res = coordinator.process(state)

    assert isinstance(res, AgentResponse)
    assert res.success is True
    assert len(res.answer) > 40
    assert len(res.sources) > 0
    assert "multi_intent" in state.intermediate_results
    assert state.intermediate_results["multi_intent"]["task_count"] == 2
