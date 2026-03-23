import re
import uuid
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, HTMLResponse
from models.schemas import (
    PlaceSearchRequest,
    DirectionsRequest,
    GeocodeRequest,
    ExploreRequest,
    CardRequest,
    UserLocationRequest,
    GeoResultRequest,
)
from services.google_maps import GoogleMapsService
from services.cache import CacheService
from services.card_renderer import (
    render_places_card,
    render_directions_card,
    render_places_map,
    render_directions_map,
)
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
        latitude=body.latitude,
        longitude=body.longitude,
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


@router.get("/reverse-geocode", dependencies=[Depends(verify_api_key)])
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def reverse_geocode(
    request: Request,
    lat: float = 0,
    lng: float = 0,
    maps: GoogleMapsService = Depends(get_maps_service),
):
    """Convert latitude/longitude to a human-readable address."""
    result = await maps.reverse_geocode(lat, lng)
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
        latitude=body.latitude,
        longitude=body.longitude,
        radius_meters=3000,
        max_results=body.max_results,
    )
    result["area"] = body.area
    result["category"] = body.category
    return result


@router.get("/embed")
async def embed_map(url: str, height: int = 450):
    """
    Serve Google Maps embed URL inside a properly-sized HTML wrapper.
    Sends postMessage({type:'iframe:height', height}) so Open WebUI's
    sandbox iframe auto-resizes to the correct height.
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

    html = (
        "<!DOCTYPE html><html><head>"
        '<meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<style>"
        "*{margin:0;padding:0;box-sizing:border-box}"
        f"html,body{{height:{h}px;overflow:hidden}}"
        f"iframe{{width:100%;height:{h}px;border:0;display:block}}"
        ".cover{position:absolute;bottom:0;left:0;right:0;height:26px;background:#1a1a2e;z-index:9999}"
        "</style></head><body>"
        f'<iframe src="{safe_url}" allowfullscreen loading="lazy" '
        f'referrerpolicy="no-referrer-when-downgrade"></iframe>'
        '<div class="cover"></div>'
        "<script>"
        f"window.parent.postMessage({{type:'iframe:height',height:{h}}},'*');"
        f"window.addEventListener('load',()=>window.parent.postMessage({{type:'iframe:height',height:{h}}},'*'));"
        "</script>"
        "</body></html>"
    )

    return HTMLResponse(content=html)


@router.post("/card", dependencies=[Depends(verify_api_key)])
async def create_card(request: Request, body: CardRequest):
    """
    Store card data in cache and return a card ID.
    The tool POSTs place/direction data here, gets back a URL to emit as embed.
    """
    card_id = str(uuid.uuid4())
    cache: CacheService = request.app.state.cache
    await cache.set(f"card:{card_id}", body.model_dump(), ttl=86400)
    return {"card_id": card_id}


@router.get("/card/{card_id}")
async def render_card(card_id: str, request: Request):
    """
    Render a rich HTML info card from stored data.
    No clickable links — pure informational display.
    """
    cache: CacheService = request.app.state.cache
    data = await cache.get(f"card:{card_id}")
    if not data:
        return HTMLResponse(
            content="<html><body><p>Card expired or not found.</p></body></html>",
            status_code=404,
        )

    card_type = data.get("card_type", "places")
    if card_type == "directions":
        html = render_directions_card(data)
    elif card_type == "places_map":
        html = render_places_map(data)
    elif card_type == "directions_map":
        html = render_directions_map(data)
    else:
        html = render_places_card(data)

    return HTMLResponse(content=html)


@router.post("/user-location", dependencies=[Depends(verify_api_key)])
async def store_user_location(request: Request, body: UserLocationRequest):
    """
    Store the user's browser-detected geolocation coordinates.
    Called from the geolocation card via JavaScript fetch().
    """
    cache: CacheService = request.app.state.cache
    await cache.set(
        f"user_location:{body.user_id}",
        {
            "latitude": body.latitude,
            "longitude": body.longitude,
            "accuracy": body.accuracy,
            "source": "browser",
        },
        ttl=3600,
    )
    return {"status": "ok", "latitude": body.latitude, "longitude": body.longitude}


@router.get("/user-location", dependencies=[Depends(verify_api_key)])
async def get_user_location(request: Request, user_id: str = "default"):
    """
    Retrieve the user's stored browser geolocation.
    Returns null fields if no location stored.
    """
    cache: CacheService = request.app.state.cache
    data = await cache.get(f"user_location:{user_id}")
    if not data:
        return {"found": False, "latitude": None, "longitude": None}
    return {"found": True, **data}


@router.post("/geo-result")
async def store_geo_result(request: Request, body: GeoResultRequest):
    """
    Store browser geolocation result for a specific request.
    Called from the GPS popup after detection completes (success or failure).
    No API key required — accessed from user's browser.
    """
    cache: CacheService = request.app.state.cache
    result = {
        "status": body.status,
        "latitude": body.latitude,
        "longitude": body.longitude,
        "accuracy": body.accuracy,
    }
    await cache.set(f"geo_result:{body.request_id}", result, ttl=120)

    # Also persist to user location if success
    if body.status == "ok" and body.latitude is not None and body.longitude is not None:
        await cache.set(
            f"user_location:{body.user_id}",
            {
                "latitude": body.latitude,
                "longitude": body.longitude,
                "accuracy": body.accuracy,
                "source": "browser",
            },
            ttl=3600,
        )

    return {"status": "stored"}


@router.get("/geo-result/{request_id}")
async def get_geo_result(request_id: str, request: Request):
    """
    Poll for browser geolocation result by request_id.
    Returns {found: false} if no result yet.
    """
    cache: CacheService = request.app.state.cache
    data = await cache.get(f"geo_result:{request_id}")
    if not data:
        return {"found": False}
    return {"found": True, **data}


@router.get("/user-location/card/{user_id}")
async def geolocation_card(user_id: str, request: Request):
    """
    Render a geolocation card inside the embed iframe.
    Since embed iframes lack allow="geolocation", this card opens a popup
    window to /api/maps/user-location/gps/{user_id} where GPS works at top level.
    Then polls for the result to update the UI.
    No API key required — accessed from user's browser.
    """
    html = f"""<!DOCTYPE html><html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#1a1a2e;color:#e0e0e0}}
.c{{padding:16px 20px;text-align:center}}
.ic{{font-size:36px;margin-bottom:8px}}
.tt{{font-size:15px;font-weight:600;color:#fff;margin-bottom:4px}}
.st{{font-size:12px;color:#8888aa}}
.ld{{margin-top:12px;font-size:13px;color:#7c7cff}}
.ok{{color:#66bb6a}}
.er{{color:#ef5350}}
.bt{{display:inline-block;margin-top:12px;padding:10px 24px;background:#7c7cff;color:#fff;border:none;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;text-decoration:none}}
.bt:hover{{background:#6b6bef}}
.sp{{display:inline-block;width:16px;height:16px;border:2px solid #7c7cff;border-top:2px solid transparent;border-radius:50%;animation:spin 0.8s linear infinite;vertical-align:middle;margin-right:6px}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
</style></head><body>
<div class="c" id="content">
    <div class="ic">\U0001f4cd</div>
    <div class="tt">Detect Your Location</div>
    <div class="st">Tap the button to allow GPS access</div>
    <div id="action"><button class="bt" onclick="openGPS()">📍 Allow Location Access</button></div>
    <div class="ld" id="status"></div>
</div>
<script>
const uid="{user_id}";
const rid=new URLSearchParams(window.location.search).get('rid')||'';
const el=document.getElementById('status');
const act=document.getElementById('action');
let pollTimer=null;

function postHeight(){{window.parent.postMessage({{type:'iframe:height',height:document.body.scrollHeight}},'*');}}

function openGPS(){{
  const url='/api/maps/user-location/gps/'+uid+'?rid='+rid;
  const w=window.open(url,'heypico_gps','width=420,height=350,left=100,top=100');
  if(!w||w.closed){{
    el.innerHTML='<span class="er">\\u274c Popup blocked. Please allow popups for this site.</span>';
    postHeight();
    return;
  }}
  act.innerHTML='';
  el.innerHTML='<span class="sp"></span>Waiting for GPS permission...';
  postHeight();
  startPoll();
}}

function startPoll(){{
  let elapsed=0;
  pollTimer=setInterval(function(){{
    elapsed++;
    if(elapsed>25){{clearInterval(pollTimer);el.innerHTML='<span class="er">\\u274c GPS timed out</span>';postHeight();return;}}
    fetch('/api/maps/geo-result/'+rid)
    .then(function(r){{return r.json();}})
    .then(function(d){{
      if(d.found){{
        clearInterval(pollTimer);
        if(d.status==='ok'){{
          el.innerHTML='<span class="ok">\\u2705 Location detected (\\u00b1'+d.accuracy+'m)</span>';
        }}else{{
          el.innerHTML='<span class="er">\\u274c '+(d.error||'GPS denied')+'</span><br><span style="font-size:11px;color:#8888aa">Using approximate location instead</span>';
        }}
        postHeight();
      }}
    }}).catch(function(){{}});
  }},1000);
}}

window.addEventListener('load',postHeight);
</script>
</body></html>"""

    return HTMLResponse(content=html)


@router.get("/user-location/gps/{user_id}")
async def geolocation_popup(user_id: str, request: Request):
    """
    Popup page for GPS geolocation detection.
    Opens at top level (not in iframe) so navigator.geolocation works.
    Detects GPS, posts result to /maps/geo-result, then auto-closes.
    No API key required — accessed from user's browser.
    """
    html = f"""<!DOCTYPE html><html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HeyPico - GPS Location</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{min-height:100vh;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#1a1a2e;color:#e0e0e0;display:flex;align-items:center;justify-content:center}}
.c{{padding:32px;text-align:center;max-width:380px}}
.ic{{font-size:48px;margin-bottom:12px}}
.tt{{font-size:18px;font-weight:600;color:#fff;margin-bottom:6px}}
.st{{font-size:13px;color:#8888aa;margin-bottom:16px}}
.ld{{font-size:14px;color:#7c7cff}}
.ok{{color:#66bb6a}}
.er{{color:#ef5350}}
.sp{{display:inline-block;width:20px;height:20px;border:2px solid #7c7cff;border-top:2px solid transparent;border-radius:50%;animation:spin 0.8s linear infinite;vertical-align:middle;margin-right:8px}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
.cls{{display:none;margin-top:16px;font-size:12px;color:#8888aa}}
</style></head><body>
<div class="c">
    <div class="ic">\U0001f4cd</div>
    <div class="tt">GPS Location</div>
    <div class="st">Please allow location access when prompted</div>
    <div class="ld" id="status"><span class="sp"></span>Requesting GPS permission...</div>
    <div class="cls" id="close-msg">This window will close automatically...</div>
</div>
<script>
const uid="{user_id}";
const rid=new URLSearchParams(window.location.search).get('rid')||'';
const el=document.getElementById('status');
const cm=document.getElementById('close-msg');

function send(data){{
  return fetch('/api/maps/geo-result',{{
    method:'POST',
    headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify(Object.assign({{request_id:rid,user_id:uid}},data))
  }});
}}

function done(){{
  cm.style.display='block';
  setTimeout(function(){{try{{window.close();}}catch(e){{}}}},2000);
}}

if(!navigator.geolocation){{
  el.innerHTML='<span class="er">\\u274c Geolocation not supported in this browser</span>';
  send({{status:'error',error:'not_supported'}}).finally(done);
}}else{{
  navigator.geolocation.getCurrentPosition(
    function(pos){{
      const lat=pos.coords.latitude,lng=pos.coords.longitude,acc=Math.round(pos.coords.accuracy);
      el.innerHTML='<span class="ok">\\u2705 Location detected (\\u00b1'+acc+'m)</span>';
      send({{status:'ok',latitude:lat,longitude:lng,accuracy:acc}}).finally(done);
    }},
    function(err){{
      let msg='Permission denied';
      if(err.code===2)msg='Position unavailable';
      if(err.code===3)msg='Timed out';
      el.innerHTML='<span class="er">\\u274c '+msg+'</span>';
      send({{status:'denied',error:msg}}).finally(done);
    }},
    {{enableHighAccuracy:true,timeout:15000,maximumAge:300000}}
  );
}}
</script>
</body></html>"""

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
