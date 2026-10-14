import logging
import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field

from app.auth.jwt import get_current_user, get_optional_current_user
from app.db.itinerary_storage import (
    save_itinerary,
    get_user_itineraries,
    get_itinerary_by_id,
    delete_user_itinerary
)
from app.api.chat import get_coordinator, UTF8JSONResponse
from app.agents.state import AgentState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/itinerary", tags=["Dedicated Itinerary Planner"], default_response_class=UTF8JSONResponse)


class ItineraryPlanRequest(BaseModel):
    origin: Optional[str] = Field(default=None, description="Starting city or location (e.g. Hyderabad, Warangal)")
    destinations: List[str] = Field(..., min_length=1, description="List of pilgrimage temples to visit")
    duration_days: Optional[int] = Field(default=None, ge=1, le=14, description="Trip duration in days")
    start_date: Optional[str] = Field(default=None, description="Optional start date (YYYY-MM-DD)")
    pax: Optional[int] = Field(default=1, ge=1, le=50, description="Number of pilgrims/travellers")
    travellers: Optional[int] = Field(default=None, ge=1, le=50, description="Alternative alias for pax")
    budget_limit: Optional[float] = Field(default=None, ge=0, description="Total trip budget limit in INR")
    accommodation_preference: Optional[str] = Field(default=None, description="Accommodation tier preference: budget, standard, premium, or none")
    transport_preference: Optional[str] = Field(default=None, description="Transport preference: car, bus, train")
    food_preference: Optional[str] = Field(default=None, description="Food preference: temple prasadam, local dining")
    round_trip: Optional[bool] = Field(default=False, description="Whether to include return leg back to starting city")
    selected_activities: Optional[List[Any]] = Field(default=None, description="List of user-selected nearby attractions/activities")


class ItinerarySaveRequest(BaseModel):
    title: Optional[str] = Field(default=None, description="Custom title for saved itinerary")
    origin: Optional[str] = None
    destinations: List[str] = Field(..., min_length=1)
    duration_days: int = Field(default=1, ge=1)
    pax: int = Field(default=1, ge=1)
    itinerary_text: str = Field(..., min_length=1, description="Full formatted itinerary and budget markdown")
    budget_limit: Optional[float] = None
    preferences: Optional[Dict[str, Any]] = None
    route_legs: Optional[List[Dict[str, Any]]] = None
    budget_breakdown: Optional[Dict[str, Any]] = None
    itinerary_id: Optional[str] = None


@router.post("/plan")
async def plan_itinerary_endpoint(
    request: ItineraryPlanRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user)
):
    """
    Dedicated itinerary planner endpoint that delegates directly to the existing
    MasterAgentCoordinator and ItineraryPlanningAgent/BudgetAgent workflow,
    guaranteeing 100% output consistency between dedicated UI and chat.
    """
    cleaned_destinations = [d.strip() for d in request.destinations if d and d.strip()]
    if not cleaned_destinations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one pilgrimage destination must be specified."
        )

    # Calculate days: use provided or default to number of destinations
    days = request.duration_days or len(cleaned_destinations)
    pax = request.travellers or request.pax or 1

    # Formulate natural query that activates the sequential multi-intent pipeline
    # with the exact constraints specified in the dedicated form
    query_parts = []
    dest_str = " and ".join(cleaned_destinations) if len(cleaned_destinations) <= 2 else (", ".join(cleaned_destinations[:-1]) + f", and {cleaned_destinations[-1]}")
    
    if request.origin and request.origin.strip():
        origin_clean = request.origin.strip()
        query_parts.append(f"Plan a {days} day trip from {origin_clean} to {dest_str}")
        if request.round_trip:
            query_parts.append(f"and return back to {origin_clean}")
    else:
        query_parts.append(f"Plan a {days} day trip to {dest_str}")

    if pax > 1:
        query_parts.append(f"for {pax} people")

    if request.budget_limit is not None and request.budget_limit > 0:
        query_parts.append(f"with budget of {int(request.budget_limit)}")

    if request.accommodation_preference:
        pref = request.accommodation_preference.lower()
        if "none" in pref or "no" in pref:
            query_parts.append("without accommodation")
        else:
            query_parts.append(f"with {pref} accommodation")

    if request.transport_preference:
        t_pref = request.transport_preference.lower()
        if "bus" in t_pref:
            query_parts.append("by bus")
        elif "train" in t_pref:
            query_parts.append("by train")
        elif "car" in t_pref or "driving" in t_pref or "cab" in t_pref:
            query_parts.append("by car")

    constructed_query = " ".join(query_parts)
    logger.info(f"[DEDICATED PLANNER] Executing query: {constructed_query}")

    coordinator = get_coordinator()
    session_id = str(uuid.uuid4())
    state = AgentState(
        user_query=constructed_query,
        session_id=session_id,
        structured_constraints={
            "origin": request.origin,
            "destinations": cleaned_destinations,
            "duration_days": days,
            "pax": pax,
            "budget_limit": request.budget_limit,
            "accommodation_preference": request.accommodation_preference,
            "transport_preference": request.transport_preference,
            "food_preference": request.food_preference,
            "round_trip": request.round_trip,
            "start_date": request.start_date,
            "selected_activities": request.selected_activities
        }
    )

    try:
        agent_resp = coordinator.process(state)
        return {
            "success": agent_resp.success,
            "answer": agent_resp.answer,
            "itinerary": agent_resp.answer,
            "metadata": agent_resp.metadata,
            "sources": agent_resp.sources,
            "session_id": session_id,
            "latency_ms": agent_resp.latency_ms,
            "query_used": constructed_query,
            "parameters": {
                "origin": request.origin,
                "destinations": cleaned_destinations,
                "duration_days": days,
                "pax": pax,
                "budget_limit": request.budget_limit,
                "round_trip": request.round_trip,
                "preferences": {
                    "accommodation": request.accommodation_preference,
                    "transport": request.transport_preference,
                    "food": request.food_preference,
                    "start_date": request.start_date
                }
            }
        }
    except Exception as e:
        logger.error(f"[DEDICATED PLANNER] Error planning itinerary: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while generating your itinerary: {str(e)}"
        )


@router.post("/save")
async def save_itinerary_endpoint(
    request: ItinerarySaveRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Persists a generated itinerary for the authenticated user.
    Returns honest error if database is unavailable.
    """
    user_id = str(current_user.get("_id"))
    try:
        saved_record = save_itinerary(
            user_id=user_id,
            title=request.title or f"Pilgrimage to {', '.join(request.destinations)}",
            origin=request.origin,
            destinations=request.destinations,
            duration_days=request.duration_days,
            pax=request.pax,
            itinerary_text=request.itinerary_text,
            budget_limit=request.budget_limit,
            preferences=request.preferences,
            route_legs=request.route_legs,
            budget_breakdown=request.budget_breakdown,
            itinerary_id=request.itinerary_id
        )
        return {
            "success": True,
            "message": "Itinerary saved successfully.",
            "itinerary": saved_record,
            "itinerary_id": saved_record.get("itinerary_id")
        }
    except Exception as e:
        logger.error(f"[SAVE ITINERARY FAILED] Could not persist itinerary: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save itinerary to database: {str(e)}"
        )


@router.get("/saved")
async def get_saved_itineraries_endpoint(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Returns all saved itineraries for the authenticated user.
    """
    user_id = str(current_user.get("_id"))
    try:
        records = get_user_itineraries(user_id=user_id)
        return {
            "success": True,
            "itineraries": records,
            "count": len(records)
        }
    except Exception as e:
        logger.error(f"[FETCH SAVED ITINERARIES FAILED]: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve saved itineraries: {str(e)}"
        )


@router.delete("/saved/{itinerary_id}")
async def delete_saved_itinerary_endpoint(
    itinerary_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Deletes a specific saved itinerary by ID.
    """
    user_id = str(current_user.get("_id"))
    try:
        deleted = delete_user_itinerary(user_id=user_id, itinerary_id=itinerary_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Itinerary not found or not owned by user."
            )
        return {
            "success": True,
            "message": "Itinerary deleted successfully."
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[DELETE SAVED ITINERARY FAILED]: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete itinerary: {str(e)}"
        )
