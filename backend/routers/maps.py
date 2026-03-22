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


@router.get("/embed")
async def embed_map(url: str, height: int = 450, open_url: str = ""):
    """
    Serve Google Maps embed URL inside a properly-sized HTML wrapper.
    Sends postMessage({type:'iframe:height', height}) so Open WebUI's
    sandbox iframe auto-resizes to the correct height.
    If open_url is provided, an invisible overlay is placed over the
    Google Maps 'Open in Maps' button so clicks route through our proxy.
    No API key required — accessed from the user's browser.
    """
    decoded = unquote(url)
    if not re.match(
        r"^https://(www\.|maps\.)?(google\.(com|co\.[a-z]+)|googleapis\.com)/",
        decoded,
    ):
        return JSONResponse(status_code=400, content={"error": "Invalid URL"})

    safe_url = decoded.replace("&", "&amp;").replace('"', "&quot;")
    h = max(200, min(height, 800))

    # Overlay anchor that intercepts the "Open in Maps" button (top-left of embed)
    overlay_html = ""
    if open_url:
        safe_open = unquote(open_url).replace('"', "&quot;").replace("'", "&#39;")
        overlay_html = (
            f'<a href="{safe_open}" target="_blank" rel="noopener noreferrer" '
            f'style="position:absolute;top:0;left:0;width:175px;height:54px;'
            f'z-index:9999;display:block;cursor:pointer;"></a>'
        )

    html = (
        "<!DOCTYPE html><html><head>"
        '<meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<style>"
        "*{margin:0;padding:0;box-sizing:border-box}"
        f"html,body{{height:{h}px;overflow:hidden}}"
        f".wrap{{position:relative;width:100%;height:{h}px}}"
        f"iframe{{width:100%;height:{h}px;border:0;display:block}}"
        "</style></head><body>"
        "<div class='wrap'>"
        f'<iframe src="{safe_url}" allowfullscreen loading="lazy" '
        f'referrerpolicy="no-referrer-when-downgrade"></iframe>'
        f"{overlay_html}"
        "</div>"
        "<script>"
        f"window.parent.postMessage({{type:'iframe:height',height:{h}}},'*');"
        f"window.addEventListener('load',()=>window.parent.postMessage({{type:'iframe:height',height:{h}}},'*'));"
        "</script>"
        "</body></html>"
    )

    return HTMLResponse(content=html)


@router.get("/open")
async def open_maps_redirect(url: str):
    """
    Redirect page for Google Maps URLs.
    Breaks the Cross-Origin-Opener-Policy chain that blocks Google Maps
    when opened from Open WebUI (which sets COOP: same-origin).
    Uses window.location.replace + COOP: unsafe-none to fully break the chain.
    No API key required — accessed from the user's browser.
    """
    decoded = unquote(url)
    # Accept any google.com / google.co.* / googleapis.com maps URL
    if not re.match(
        r"^https://(www\.|maps\.)?(google\.(com|co\.[a-z]+)|googleapis\.com)/",
        decoded,
    ):
        return JSONResponse(status_code=400, content={"error": "Invalid URL"})

    # Escape for safe embedding in JS string
    safe_url = (
        decoded.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("'", "\\'")
        .replace("<", "\\x3c")
    )

    html = (
        "<!DOCTYPE html><html><head>"
        '<meta charset="UTF-8">'
        "<title>Opening Google Maps...</title>"
        "</head><body>"
        '<p style="font-family:sans-serif;text-align:center;margin-top:40vh">'
        "Opening Google Maps...</p>"
        "<script>"
        f'window.location.replace("{safe_url}");'
        "</script>"
        "</body></html>"
    )

    return HTMLResponse(
        content=html,
        headers={
            "Cross-Origin-Opener-Policy": "unsafe-none",
            "Cross-Origin-Embedder-Policy": "unsafe-none",
        },
    )
