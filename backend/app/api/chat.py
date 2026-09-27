import logging
import uuid
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.rag.chat import PilgrimRAGService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat"])

class ChatRequest(BaseModel):
    question: str = Field(..., description="User query about temple details", json_schema_extra={"example": "What are the timings of Basara Temple?"})
    session_id: Optional[str] = Field(default=None, description="Optional conversation session identifier for multi-turn context")

class ChatResponse(BaseModel):
    question: str
    answer: str
    retrieved_chunks: int
    sources: List[str]
    confidence_score: float
    agent_name: Optional[str] = None
    session_id: Optional[str] = None
    latency_ms: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

_service_instance: Optional[Any] = None
_coordinator_instance: Optional[Any] = None

def get_rag_service() -> Any:
    global _service_instance
    if _service_instance is None:
        try:
            from app.rag.chat import PilgrimRAGService
            _service_instance = PilgrimRAGService()
        except FileNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Local vector DB or BM25 index not found. Please run ingestion first. Error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize local RAG service: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error initializing local RAG service: {str(e)}"
            )
    return _service_instance

def get_coordinator() -> Any:
    global _coordinator_instance
    if _coordinator_instance is None:
        try:
            from app.agents.coordinator import MasterAgentCoordinator
            from app.agents.temple_information_agent import TempleInformationAgent
            from app.agents.comparison_agent import ComparisonAgent
            from app.agents.cross_temple_aggregation_agent import CrossTempleAggregationAgent
            from app.agents.itinerary_planning_agent import ItineraryPlanningAgent
            from app.agents.live_weather_agent import LiveWeatherAgent
            from app.agents.budget_agent import BudgetAgent
            from app.agents.live_navigation_agent import LiveNavigationAgent
            from app.agents.voice_multilingual_agent import VoiceMultilingualAgent, LocalTranslationProvider
            from app.agents.emergency_agent import EmergencyAgent
            from app.agents.recommendation_agent import RecommendationAgent
            from app.agents.memory import ConversationMemoryManager
            from app.agents.router import AgentRouter
            from app.agents.response_aggregator import ResponseAggregator

            memory_manager = ConversationMemoryManager()
            router = AgentRouter()
            aggregator = ResponseAggregator()
            temple_info = TempleInformationAgent()
            comparison = ComparisonAgent()
            cross_temple = CrossTempleAggregationAgent()
            itinerary = ItineraryPlanningAgent()
            weather = LiveWeatherAgent()
            budget = BudgetAgent()
            navigation = LiveNavigationAgent()
            voice_multilingual = VoiceMultilingualAgent(translation_provider=LocalTranslationProvider())
            emergency = EmergencyAgent()
            recommendation = RecommendationAgent(weather_agent=weather)

            _coordinator_instance = MasterAgentCoordinator(
                router=router,
                aggregator=aggregator,
                temple_info_agent=temple_info,
                comparison_agent=comparison,
                cross_temple_agent=cross_temple,
                itinerary_agent=itinerary,
                live_weather_agent=weather,
                budget_agent=budget,
                live_navigation_agent=navigation,
                voice_multilingual_agent=voice_multilingual,
                emergency_agent=emergency,
                recommendation_agent=recommendation,
                memory_manager=memory_manager
            )
        except Exception as e:
            logger.error(f"Failed to initialize MasterAgentCoordinator: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error initializing agent coordinator: {str(e)}"
            )
    return _coordinator_instance

def set_coordinator(coordinator: Optional[Any]) -> None:
    """Sets or overrides the coordinator instance (used for testing / dependency injection)."""
    global _coordinator_instance
    _coordinator_instance = coordinator

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    POST /chat endpoint to receive user questions and return AI answers
    routed through the MasterAgentCoordinator multi-agent architecture.
    """
    cleaned_question = request.question.strip()
    if not cleaned_question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question field cannot be empty."
        )

    session_id = request.session_id.strip() if request.session_id and request.session_id.strip() else str(uuid.uuid4())

    coordinator = get_coordinator()

    try:
        from app.agents.state import AgentState
        state = AgentState(user_query=cleaned_question, session_id=session_id)
        agent_resp = coordinator.process(state)

        # Extract retrieved chunks count safely
        retrieved_chunks = 0
        if "retrieved_chunks" in agent_resp.metadata:
            try:
                retrieved_chunks = int(agent_resp.metadata["retrieved_chunks"])
            except (ValueError, TypeError):
                retrieved_chunks = len(agent_resp.sources)
        elif agent_resp.sources:
            retrieved_chunks = len(agent_resp.sources)

        # Extract confidence score safely
        confidence_score = 1.0
        if "confidence_score" in agent_resp.metadata:
            try:
                confidence_score = float(agent_resp.metadata["confidence_score"])
            except (ValueError, TypeError):
                confidence_score = 1.0
        elif "route_decision" in state.intermediate_results:
            rd = state.intermediate_results["route_decision"]
            if hasattr(rd, "confidence") and rd.confidence is not None:
                confidence_score = float(rd.confidence)

        return ChatResponse(
            question=cleaned_question,
            answer=agent_resp.answer,
            retrieved_chunks=retrieved_chunks,
            sources=agent_resp.sources,
            confidence_score=confidence_score,
            agent_name=agent_resp.agent_name or "coordinator",
            session_id=session_id,
            latency_ms=agent_resp.latency_ms,
            metadata=agent_resp.metadata
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing chat request through coordinator: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing your request: {str(e)}"
        )
