import logging
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from app.db.mongodb import get_saved_itineraries_collection

logger = logging.getLogger(__name__)


def save_itinerary(
    user_id: str,
    title: str,
    origin: Optional[str],
    destinations: List[str],
    duration_days: int,
    pax: int,
    itinerary_text: str,
    budget_limit: Optional[float] = None,
    preferences: Optional[Dict[str, Any]] = None,
    route_legs: Optional[List[Dict[str, Any]]] = None,
    budget_breakdown: Optional[Dict[str, Any]] = None,
    itinerary_id: Optional[str] = None,
    db_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Persists a generated itinerary and its associated parameters, route legs,
    and budget breakdown to the MongoDB saved_itineraries collection.
    """
    if not user_id:
        raise ValueError("user_id is required to save an itinerary")

    itin_id = itinerary_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    col = get_saved_itineraries_collection(db_name)

    doc = {
        "user_id": str(user_id),
        "itinerary_id": itin_id,
        "title": title or f"Itinerary to {', '.join(destinations)}",
        "origin": origin,
        "destinations": destinations,
        "duration_days": int(duration_days),
        "pax": int(pax),
        "budget_limit": float(budget_limit) if budget_limit is not None else None,
        "preferences": preferences or {},
        "itinerary_text": itinerary_text,
        "route_legs": route_legs or [],
        "budget_breakdown": budget_breakdown or {},
        "created_at": now,
        "updated_at": now
    }

    col.update_one(
        {"user_id": str(user_id), "itinerary_id": itin_id},
        {"$set": doc},
        upsert=True
    )

    return {
        "itinerary_id": itin_id,
        "title": doc["title"],
        "origin": origin,
        "destinations": destinations,
        "duration_days": duration_days,
        "pax": pax,
        "created_at": now.isoformat()
    }


def get_user_itineraries(
    user_id: str,
    limit: int = 50,
    db_name: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieves all saved itineraries for the given authenticated user,
    ordered by creation date descending.
    """
    if not user_id:
        return []

    col = get_saved_itineraries_collection(db_name)
    cursor = col.find(
        {"user_id": str(user_id)},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit)

    results = []
    for item in cursor:
        if isinstance(item.get("created_at"), datetime):
            item["created_at"] = item["created_at"].isoformat()
        if isinstance(item.get("updated_at"), datetime):
            item["updated_at"] = item["updated_at"].isoformat()
        results.append(item)
    return results


def get_itinerary_by_id(
    user_id: str,
    itinerary_id: str,
    db_name: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Retrieves a single saved itinerary document by ID for the user.
    """
    if not user_id or not itinerary_id:
        return None

    col = get_saved_itineraries_collection(db_name)
    item = col.find_one(
        {"user_id": str(user_id), "itinerary_id": str(itinerary_id)},
        {"_id": 0}
    )
    if item:
        if isinstance(item.get("created_at"), datetime):
            item["created_at"] = item["created_at"].isoformat()
        if isinstance(item.get("updated_at"), datetime):
            item["updated_at"] = item["updated_at"].isoformat()
    return item


def delete_user_itinerary(
    user_id: str,
    itinerary_id: str,
    db_name: Optional[str] = None
) -> bool:
    """
    Deletes a saved itinerary owned by the authenticated user.
    """
    if not user_id or not itinerary_id:
        return False

    col = get_saved_itineraries_collection(db_name)
    res = col.delete_one({"user_id": str(user_id), "itinerary_id": str(itinerary_id)})
    return res.deleted_count > 0
