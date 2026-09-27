import os
import json
import logging
import urllib.request
import urllib.parse
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Query, HTTPException, status
from pydantic import BaseModel, Field

from app.agents.coordinate_registry import coordinate_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/maps", tags=["Maps & Places"])


class MapsConfigResponse(BaseModel):
    enabled: bool = Field(..., description="Whether Google Maps integration is enabled")
    api_key: str = Field(..., description="Google Maps JavaScript API key for client-side loading")


class TempleCoordinateItem(BaseModel):
    canonical_name: str
    display_name: str
    latitude: float
    longitude: float
    district: str
    state: str
    source: str
    verification_status: str


class PlaceResultItem(BaseModel):
    name: str
    address: Optional[str] = None
    rating: Optional[float] = None
    user_ratings_total: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    place_id: Optional[str] = None
    types: List[str] = Field(default_factory=list)
    open_now: Optional[bool] = None


class PlacesSearchResponse(BaseModel):
    status: str
    source: str = "Live Google Places Results"
    results: List[PlaceResultItem] = Field(default_factory=list)
    message: Optional[str] = None


@router.get("/config", response_model=MapsConfigResponse)
async def get_maps_config():
    """
    Returns runtime Google Maps JavaScript API configuration for the frontend.
    Credential is read from the local environment (GOOGLE_MAPS_API_KEY).
    """
    raw_key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    return MapsConfigResponse(
        enabled=bool(raw_key),
        api_key=raw_key
    )


@router.get("/temples", response_model=List[TempleCoordinateItem])
async def get_temples():
    """
    Returns all 20 canonical pilgrimage temple coordinates and metadata
    from the verified, read-only TempleCoordinateRegistry.
    """
    all_coords = coordinate_registry.get_all_coordinates()
    items = []
    for canonical, coord in sorted(all_coords.items()):
        items.append(
            TempleCoordinateItem(
                canonical_name=coord.canonical_name,
                display_name=coord.display_name or coord.canonical_name,
                latitude=coord.latitude,
                longitude=coord.longitude,
                district=coord.district,
                state=coord.state,
                source=coord.source,
                verification_status=coord.verification_status
            )
        )
    return items


@router.get("/places", response_model=PlacesSearchResponse)
async def search_nearby_places(
    query: str = Query(..., description="Search query e.g. 'restaurants near Yadadri' or 'lodging'"),
    latitude: Optional[float] = Query(None, description="Optional center latitude"),
    longitude: Optional[float] = Query(None, description="Optional center longitude"),
    radius: int = Query(5000, ge=100, le=50000, description="Search radius in meters"),
    place_type: Optional[str] = Query(None, description="Optional place type filter")
):
    """
    Safe backend query for Google Places API. Clearly segregates results
    as 'Live Google Places Results' without mutating verified pilgrimage data.
    """
    # Check dedicated server-side Places credential
    server_key = os.environ.get("GOOGLE_PLACES_SERVER_API_KEY", "").strip()
    if not server_key:
        # Do NOT attempt to use browser-restricted GOOGLE_MAPS_API_KEY for server-side HTTP calls.
        return PlacesSearchResponse(
            status="BROWSER_SEARCH_REQUIRED",
            source="Live Google Places Results",
            results=[],
            message="Server-side Places API credential is not configured. Browser-side PlacesService should be used with the restricted Maps credential."
        )

    # Build Google Places API query with server-side key
    try:
        base_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            "query": query.strip(),
            "key": server_key
        }
        if latitude is not None and longitude is not None:
            params["location"] = f"{latitude},{longitude}"
            params["radius"] = str(radius)
        if place_type:
            params["type"] = place_type.strip()

        req_url = f"{base_url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(req_url, headers={"User-Agent": "PilgrimAI-Backend/1.0"})
        
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        api_status = data.get("status", "UNKNOWN")
        if api_status in ("OK", "ZERO_RESULTS"):
            raw_results = data.get("results", [])
            parsed_items: List[PlaceResultItem] = []
            for r in raw_results[:10]:
                geom = r.get("geometry", {}).get("location", {})
                opening = r.get("opening_hours", {})
                parsed_items.append(
                    PlaceResultItem(
                        name=r.get("name", "Unknown Place"),
                        address=r.get("formatted_address") or r.get("vicinity"),
                        rating=r.get("rating"),
                        user_ratings_total=r.get("user_ratings_total"),
                        latitude=geom.get("lat"),
                        longitude=geom.get("lng"),
                        place_id=r.get("place_id"),
                        types=r.get("types", []),
                        open_now=opening.get("open_now")
                    )
                )
            return PlacesSearchResponse(
                status=api_status,
                source="Live Google Places Results",
                results=parsed_items,
                message=None
            )
        else:
            err_msg = data.get("error_message") or f"Google Places API returned status: {api_status}"
            logger.warning(f"Google Places API query non-OK: {api_status}")
            return PlacesSearchResponse(
                status=api_status,
                source="Live Google Places Results",
                results=[],
                message=err_msg
            )
    except Exception as e:
        logger.error(f"Error querying Google Places API: {e}")
        return PlacesSearchResponse(
            status="ERROR",
            source="Live Google Places Results",
            results=[],
            message="Places search request failed or timed out. Offline mode active."
        )
