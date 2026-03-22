import re
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, HTMLResponse
from models.schemas import (
    PlaceSearchRequest,
    DirectionsRequest,
    GeocodeRequest,
    ExploreRequest,
)
from services.google_maps import GoogleMapsService
from services.cache import CacheService
from middleware.security import verify_api_key, sanitize_query
from middleware.rate_limiter import limiter
from config import get_settings

settings = get_settings()
router = APIRouter(prefix="/maps", tags=["Google Maps"])


def get_maps_service(request: Request) -> GoogleMapsService:
    return request.app.state.maps_service


@router.post("/search", dependencies=[Depends(verify_api_key)])
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def search_places(
    request: Request,
    body: PlaceSearchRequest,
    maps: GoogleMapsService = Depends(get_maps_service),
):
    """
    Search for places using Google Places API (New).
    The API key never leaves the server — it's used only here in the backend proxy.
    """
    body.query = sanitize_query(body.query)
    if body.location:
        body.location = sanitize_query(body.location)

    result = await maps.search_places(
        query=body.query,
        location=body.location,
        radius_meters=body.radius_meters,
        max_results=body.max_results,
    )
    return result


@router.post("/directions", dependencies=[Depends(verify_api_key)])
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def get_directions(
    request: Request,
    body: DirectionsRequest,
    maps: GoogleMapsService = Depends(get_maps_service),
):
    """
    Get turn-by-turn directions between two locations.
    Returns embedded map URL + step-by-step instructions.
    """
    body.origin = sanitize_query(body.origin)
    body.destination = sanitize_query(body.destination)

    result = await maps.get_directions(
        origin=body.origin,
        destination=body.destination,
        travel_mode=body.travel_mode,
        language=body.language,
    )
    return result


@router.post("/geocode", dependencies=[Depends(verify_api_key)])
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def geocode_address(
    request: Request,
    body: GeocodeRequest,
    maps: GoogleMapsService = Depends(get_maps_service),
):
    """Convert a human-readable address to latitude/longitude coordinates."""
    body.address = sanitize_query(body.address)
    result = await maps.geocode(body.address)
    if not result:
        return JSONResponse(status_code=404, content={"error": "Address not found"})
    return result


@router.post("/explore", dependencies=[Depends(verify_api_key)])
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def explore_area(
    request: Request,
    body: ExploreRequest,
    maps: GoogleMapsService = Depends(get_maps_service),
):
    """
    Explore an area and find top places by category.
    Returns a rich set of recommendations.
    """
    category_queries = {
        "food": "restaurant food",
        "entertainment": "entertainment nightlife",
        "shopping": "shopping mall",
        "coffee": "cafe coffee shop",
        "attractions": "tourist attraction landmark",
        "all": "popular places things to do",
    }
    query = category_queries.get(body.category, "popular places")
    body.area = sanitize_query(body.area)

    result = await maps.search_places(
        query=query,
        location=body.area,
        radius_meters=3000,
        max_results=body.max_results,
    )
    result["area"] = body.area
    result["category"] = body.category
    return result


@router.get("/open")
async def open_maps_redirect(url: str):
    """
    Redirect page for Google Maps URLs.
    Breaks the Cross-Origin-Opener-Policy chain that blocks Google Maps
    when opened from Open WebUI (which sets COOP: same-origin).
    No API key required — accessed from the user's browser.
    """
    decoded = unquote(url)
    if not re.match(r"^https://(www\.google\.com|maps\.google\.com)/maps", decoded):
        return JSONResponse(status_code=400, content={"error": "Invalid URL"})

    safe_url = decoded.replace('"', "%22").replace("'", "%27")

    return HTMLResponse(
        content=(
            "<!DOCTYPE html><html><head>"
            '<meta charset="UTF-8">'
            f'<meta http-equiv="refresh" content="0;url={safe_url}">'
            f"<title>Opening Google Maps...</title>"
            '</head><body style="font-family:sans-serif;display:flex;'
            "align-items:center;justify-content:center;height:100vh;"
            'margin:0;background:#f8f9fa">'
            "<p>Opening Google Maps...</p>"
            "</body></html>"
        )
    )
