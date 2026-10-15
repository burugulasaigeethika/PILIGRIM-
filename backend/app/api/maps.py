import os
import re
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


import math
from pathlib import Path


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)


def categorize_place(name: str, desc: str = "", types: Optional[List[str]] = None) -> str:
    text = (name + " " + (desc or "") + " " + " ".join(types or [])).lower()
    if any(k in text for k in ["fort", "monument", "chalukya", "heritage", "palace", "ruins", "historical", "archaeological"]):
        return "Historic Forts & Heritage Sites"
    if any(k in text for k in ["lake", "dam", "waterfall", "park", "garden", "nature", "viewpoint", "forest", "valley", "ghat", "river"]):
        return "Lakes, Viewpoints & Nature"
    if any(k in text for k in ["museum", "planetarium", "science", "gallery", "exhibition"]):
        return "Museums & Science Attractions"
    if any(k in text for k in ["temple", "shrine", "gutta", "mandir", "devalayam", "gaddelu", "ashram"]):
        return "Cultural Sites & Shrines"
    if any(k in text for k in ["recreation", "amusement", "boating", "sports", "zoo", "resort", "activity"]):
        return "Family-Friendly Activities"
    return "Local Experiences & Sightseeing"


def load_static_nearby_attractions(temple_name: str) -> List[Dict[str, Any]]:
    root_dir = Path(__file__).resolve().parents[3]
    target_folder = None

    # 1. First check if coordinate_registry resolves canonical name
    coord = coordinate_registry.get_coordinate(temple_name)
    if coord and coord.canonical_name:
        cand = root_dir / coord.canonical_name.lower()
        if cand.is_dir() and (cand / "nearby_attractions.json").exists():
            target_folder = cand

    if not target_folder:
        # Check alias seeds / common aliases
        aliases_map = {
            "bhadrachalam": "badrachalam",
            "badrachalam": "badrachalam",
            "vemulawada": "vemulavada",
            "vemulavada": "vemulavada",
            "srisailam": "srisaila",
            "srisaila": "srisaila",
            "yadagirigutta": "yadadri",
            "yadadri": "yadadri"
        }
        for k, v in aliases_map.items():
            if k in temple_name.lower():
                cand = root_dir / v
                if cand.is_dir() and (cand / "nearby_attractions.json").exists():
                    target_folder = cand
                    break

    if not target_folder:
        clean_t = temple_name.lower().replace("temple", "").replace("sri", "").replace("swamy", "").replace("devasthanam", "").strip()
        for folder in root_dir.iterdir():
            if folder.is_dir():
                f_low = folder.name.lower()
                if clean_t and (clean_t in f_low or f_low in clean_t):
                    target_folder = folder
                    break

    if not target_folder:
        target_folder = root_dir / temple_name.lower()

    attr_file = target_folder / "nearby_attractions.json"
    if attr_file.exists():
        try:
            with open(attr_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and "attractions" in data:
                    return data["attractions"]
        except Exception as e:
            logger.warning(f"Failed to read static attractions for {temple_name}: {e}")
    return []


class PlaceResultItem(BaseModel):
    name: str
    category: Optional[str] = None
    distance: Optional[str] = None
    distance_km: Optional[float] = None
    address: Optional[str] = None
    rating: Optional[float] = None
    user_ratings_total: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    place_id: Optional[str] = None
    types: List[str] = Field(default_factory=list)
    open_now: Optional[bool] = None
    source: str = "Live Google Places Results"
    description: Optional[str] = None
    map_url: Optional[str] = None
    directions_url: Optional[str] = None


class PlacesSearchResponse(BaseModel):
    status: str
    source: str = "Live Google Places Results"
    results: List[PlaceResultItem] = Field(default_factory=list)
    places: List[PlaceResultItem] = Field(default_factory=list)
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
    query: Optional[str] = None,
    temple: Optional[str] = None,
    temple_name: Optional[str] = None,
    category: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    radius: int = 15000,
    place_type: Optional[str] = None
):
    """
    Discovers nearby attractions, historic monuments, nature spots, and cultural sites.
    Reuses verified temple coordinates rather than city names.
    If server-side Places API is not configured or offline, falls back to the verified temple knowledge base.
    """
    target_temple = temple or temple_name
    temple_ref_name = target_temple or ""
    # 1. Resolve temple coordinates if temple provided
    if target_temple:
        coord = coordinate_registry.get_coordinate(target_temple)
        if not coord:
            # Fuzzy match canonical map
            for c_name, c_obj in coordinate_registry.get_all_coordinates().items():
                if target_temple.lower() in c_name.lower() or target_temple.lower() in c_obj.display_name.lower():
                    coord = c_obj
                    temple_ref_name = c_obj.display_name
                    break
        if coord:
            temple_ref_name = coord.display_name
            if latitude is None:
                latitude = coord.latitude
            if longitude is None:
                longitude = coord.longitude

    # 2. Check server-side Places API key
    parsed_items: List[PlaceResultItem] = []
    server_key = os.environ.get("GOOGLE_PLACES_SERVER_API_KEY", "").strip()
    if not server_key and not temple_ref_name:
        return PlacesSearchResponse(
            status="BROWSER_SEARCH_REQUIRED",
            source="Live Google Places Results",
            results=[],
            message="Server-side Places API credential is not configured. Browser-side PlacesService should be used with the restricted Maps credential."
        )

    if server_key:
        try:
            base_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
            q_term = query
            if not q_term:
                if category == "heritage":
                    q_term = f"historic forts, monuments and heritage sites near {temple_ref_name or 'temple'}"
                elif category == "nature":
                    q_term = f"lakes, viewpoints and nature parks near {temple_ref_name or 'temple'}"
                elif category == "museums":
                    q_term = f"museums and planetariums near {temple_ref_name or 'temple'}"
                elif category == "cultural":
                    q_term = f"cultural sites and temples near {temple_ref_name or 'temple'}"
                elif category == "recreation":
                    q_term = f"family friendly recreation near {temple_ref_name or 'temple'}"
                else:
                    q_term = f"attractions and sightseeing near {temple_ref_name or 'temple'}"

            params = {
                "query": q_term.strip(),
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
                seen_names = set()
                for r in raw_results:
                    p_name = r.get("name", "Unknown Place")
                    if p_name.lower() in seen_names:
                        continue
                    seen_names.add(p_name.lower())

                    geom = r.get("geometry", {}).get("location", {})
                    p_lat = geom.get("lat")
                    p_lng = geom.get("lng")
                    p_dist_km = None
                    p_dist_str = None
                    if latitude is not None and longitude is not None and p_lat is not None and p_lng is not None:
                        p_dist_km = haversine_distance_km(latitude, longitude, p_lat, p_lng)
                        p_dist_str = f"{p_dist_km} km"

                    p_cat = categorize_place(p_name, types=r.get("types", []))
                    if category and category.lower() not in p_cat.lower():
                        continue

                    opening = r.get("opening_hours", {})
                    gmap_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(p_name + ' ' + (r.get('formatted_address') or ''))}"

                    parsed_items.append(
                        PlaceResultItem(
                            name=p_name,
                            category=p_cat,
                            distance=p_dist_str,
                            distance_km=p_dist_km,
                            address=r.get("formatted_address") or r.get("vicinity"),
                            rating=r.get("rating"),
                            user_ratings_total=r.get("user_ratings_total"),
                            latitude=p_lat,
                            longitude=p_lng,
                            place_id=r.get("place_id"),
                            types=r.get("types", []),
                            open_now=opening.get("open_now"),
                            source="Live Google Places Results",
                            map_url=gmap_url,
                            directions_url=f"https://www.google.com/maps/dir/?api=1&origin={urllib.parse.quote(temple_ref_name or 'Current Location')}&destination={urllib.parse.quote(p_name)}&travelmode=driving"
                        )
                    )
        except Exception as e:
            logger.warning(f"Google Places API query encountered exception: {e}")

    # Merge static verified temple attractions with live Google Places (deduplicated by normalized name)
    merged_items: List[PlaceResultItem] = []
    seen_names = set()

    # 1. Add static verified attractions
    if temple_ref_name:
        static_attractions = load_static_nearby_attractions(temple_ref_name)
        for it in static_attractions:
            name = it.get("name", "Attraction")
            norm_name = re.sub(r"[^\w\s]", "", name.lower()).strip()
            if norm_name in seen_names:
                continue
            desc = it.get("description", "")
            dist_raw = it.get("distance", f"Near {temple_ref_name}")
            cat = categorize_place(name, desc)
            if category and category.lower() not in cat.lower() and category.lower() != "all":
                continue
            seen_names.add(norm_name)

            dist_km = None
            m = re.search(r"(\d+(?:\.\d+)?)\s*km", dist_raw, re.IGNORECASE)
            if m:
                try:
                    dist_km = float(m.group(1))
                except ValueError:
                    dist_km = None

            gmap_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(name + ' near ' + temple_ref_name)}"
            dir_url = f"https://www.google.com/maps/dir/?api=1&origin={urllib.parse.quote(temple_ref_name)}&destination={urllib.parse.quote(name)}&travelmode=driving"
            merged_items.append(
                PlaceResultItem(
                    name=name,
                    category=cat,
                    distance=dist_raw,
                    distance_km=dist_km,
                    description=desc,
                    source="Verified Temple Knowledge Base",
                    map_url=gmap_url,
                    directions_url=dir_url
                )
            )

    # 2. Add live Google Places (if any) that are not already present
    for p in parsed_items:
        norm_name = re.sub(r"[^\w\s]", "", p.name.lower()).strip()
        if norm_name not in seen_names:
            seen_names.add(norm_name)
            merged_items.append(p)

    if merged_items:
        # Sort by distance if available
        merged_items.sort(key=lambda x: (x.distance_km if x.distance_km is not None else 999.0))
        source_label = "Live Google Places & Verified Knowledge Base" if parsed_items and temple_ref_name else (
            "Live Google Places Results" if parsed_items else "Verified Temple Knowledge Base"
        )
        return PlacesSearchResponse(
            status="OK",
            source=source_label,
            results=merged_items[:15],
            places=merged_items[:15],
            message=None
        )

    # If neither live API nor static records exist
    return PlacesSearchResponse(
        status="ZERO_RESULTS",
        source="Verified Temple Knowledge Base" if temple_ref_name else "Live Google Places Results",
        results=[],
        places=[],
        message=f"No nearby attractions or activities recorded for '{temple_ref_name or query or 'location'}'. Try searching with specific category keywords or explore official temple counters."
    )
