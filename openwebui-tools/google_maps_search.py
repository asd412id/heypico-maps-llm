"""
title: Google Maps Place Search
description: Search for places (restaurants, cafes, attractions, etc.) near a location and display interactive embedded maps in chat.
author: HeyPico AI Test
version: 1.0.0
license: MIT
requirements: httpx
"""

import httpx
import json
import os
import urllib.parse
from pydantic import BaseModel, Field
from typing import Optional
from fastapi.responses import HTMLResponse


def _redirect_url(backend_url: str, target_url: str) -> str:
    """Route Google Maps URL through backend redirect to bypass COOP."""
    pub = backend_url.replace("://backend:", "://localhost:")
    return f"{pub}/maps/open?url={urllib.parse.quote(target_url, safe='')}"


class Tools:
    class Valves(BaseModel):
        backend_url: str = Field(
            default="http://backend:8000",
            description="URL of the HeyPico Maps Backend API",
        )
        backend_api_key: str = Field(
            default="",
            description="Internal API key for the backend (set in .env as BACKEND_API_KEY)",
        )
        google_maps_api_key: str = Field(
            default="",
            description="Google Maps API key — used only for embedding the map iframe in the UI",
        )
        default_radius_meters: int = Field(
            default=5000,
            description="Default search radius in meters",
        )

    def __init__(self):
        self.valves = self.Valves(
            backend_url=os.getenv("BACKEND_URL", "http://backend:8000"),
            backend_api_key=os.getenv("BACKEND_API_KEY", ""),
            google_maps_api_key=os.getenv("GOOGLE_MAPS_API_KEY", ""),
        )

    async def search_places(
        self,
        query: str,
        location: Optional[str] = None,
        max_results: int = 5,
        __event_emitter__=None,
    ) -> str:
        """
        Search for places (restaurants, cafes, attractions, etc.) near a location.
        Returns an interactive embedded map and place cards directly in the chat.

        :param query: What to search for, e.g. "pizza restaurant", "coffee shop", "tourist attraction"
        :param location: Location to search near, e.g. "Jakarta, Indonesia" or "SCBD Jakarta". If not provided, returns general results.
        :param max_results: Number of results to show (1-10)
        :return: Interactive map with place results
        """
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"🔍 Searching for '{query}'...",
                        "done": False,
                    },
                }
            )

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    f"{self.valves.backend_url}/maps/search",
                    json={
                        "query": query,
                        "location": location,
                        "radius_meters": self.valves.default_radius_meters,
                        "max_results": min(max_results, 10),
                    },
                    headers={"X-API-Key": self.valves.backend_api_key},
                )
                response.raise_for_status()
                data = response.json()

        except httpx.HTTPStatusError as e:
            error_msg = f"Backend API error: {e.response.status_code}"
            if __event_emitter__:
                await __event_emitter__(
                    {"type": "status", "data": {"description": error_msg, "done": True}}
                )
            return f"Sorry, I couldn't search for places right now. Error: {error_msg}"
        except Exception as e:
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": f"Error: {e}", "done": True},
                    }
                )
            return f"Sorry, an error occurred while searching: {str(e)}"

        places = data.get("places", [])
        count = data.get("count", 0)

        if not places:
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": "No places found", "done": True},
                    }
                )
            return (
                f"No results found for '{query}'"
                + (f" near {location}" if location else "")
                + ". Try a different search."
            )

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": f"✅ Found {count} places", "done": True},
                }
            )

        # Build redirect helper for Google Maps links
        redirect = lambda url: _redirect_url(self.valves.backend_url, url)

        # Emit clickable Google Maps links as markdown in chat (outside iframe)
        if __event_emitter__:
            location_label = f" near {location}" if location else ""
            links_md = "\n".join(
                f"{i + 1}. [{p['name']}]({redirect(p['maps_url'])})"
                for i, p in enumerate(places)
            )
            await __event_emitter__(
                {
                    "type": "message",
                    "data": {
                        "content": f"\n\n**🗺️ {query.title()}{location_label}** — Found {count} places:\n\n{links_md}\n"
                    },
                }
            )

        # Wrap Google Maps URLs through redirect for HTML
        for p in places:
            p["maps_url"] = redirect(p["maps_url"])

        # Build Rich UI HTML
        html = _build_search_results_html(
            places=places,
            query=query,
            location=location,
            api_key=self.valves.google_maps_api_key,
            redirect_fn=redirect,
        )

        return HTMLResponse(
            content=html,
            headers={"Content-Disposition": "inline"},
        )


def _build_search_results_html(
    places: list,
    query: str,
    location: Optional[str],
    api_key: str,
    redirect_fn=None,
) -> str:
    """Build a rich HTML page with embedded map and place cards."""

    # Build markers for the map
    center_lat = places[0]["lat"] if places else 0
    center_lng = places[0]["lng"] if places else 0

    # Create markers param for the embed URL
    markers_param = "&".join(
        f"markers=color:red%7Clabel:{i + 1}%7C{p['lat']},{p['lng']}"
        for i, p in enumerate(places)
    )

    # Map embed URL (using Static Maps for multi-marker view)
    map_embed_url = (
        f"https://maps.googleapis.com/maps/api/staticmap"
        f"?center={center_lat},{center_lng}&zoom=14&size=800x400"
        f"&maptype=roadmap&{markers_param}&key={api_key}"
    )

    # Interactive map link (routed through backend redirect to bypass COOP)
    location_str = location or f"{center_lat},{center_lng}"
    raw_maps_url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}/@{center_lat},{center_lng},14z"
    maps_search_url = redirect_fn(raw_maps_url) if redirect_fn else raw_maps_url

    # Place cards HTML
    place_cards_html = ""
    for i, place in enumerate(places):
        rating_html = ""
        if place.get("rating"):
            stars = "★" * int(place["rating"]) + "☆" * (5 - int(place["rating"]))
            rating_html = f"""
            <div class="rating">
                <span class="stars">{stars}</span>
                <span class="rating-value">{place["rating"]}</span>
                <span class="rating-count">({place.get("user_ratings_total", 0):,})</span>
            </div>"""

        price_html = ""
        if place.get("price_level") is not None:
            price_html = (
                "<span class='price'>" + "$" * (place["price_level"] + 1) + "</span>"
            )

        open_html = ""
        if place.get("open_now") is not None:
            open_label = "Open now" if place["open_now"] else "Closed"
            open_color = "#22c55e" if place["open_now"] else "#ef4444"
            open_html = f"<span class='open-status' style='color:{open_color}'>● {open_label}</span>"

        img_html = ""
        if place.get("photo_url"):
            img_html = f'<img class="place-photo" src="{place["photo_url"]}" alt="{place["name"]}" loading="lazy"/>'

        types_str = " · ".join(
            t.replace("_", " ").title() for t in place.get("types", [])[:2]
        )

        place_cards_html += f"""
        <div class="place-card">
            <div class="place-number">{i + 1}</div>
            {img_html}
            <div class="place-info">
                <div class="place-name">{place["name"]}</div>
                <div class="place-type">{types_str}</div>
                {rating_html}
                <div class="place-meta">{price_html} {open_html}</div>
                <div class="place-address">📍 {place["address"]}</div>
                <a class="maps-link" href="{place["maps_url"]}" target="_blank" rel="noopener">
                    View on Google Maps →
                </a>
            </div>
        </div>"""

    location_label = f" near {location}" if location else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8f9fa; color: #1a1a2e; padding: 12px; }}
  .header {{ background: linear-gradient(135deg, #1a73e8, #0d47a1); color: white; padding: 16px 20px; border-radius: 12px; margin-bottom: 16px; }}
  .header h2 {{ font-size: 18px; font-weight: 600; }}
  .header p {{ font-size: 13px; opacity: 0.85; margin-top: 4px; }}
  .map-container {{ border-radius: 12px; overflow: hidden; margin-bottom: 16px; box-shadow: 0 2px 12px rgba(0,0,0,0.15); position: relative; }}
  .map-img {{ width: 100%; display: block; cursor: pointer; transition: opacity 0.2s; }}
  .map-img:hover {{ opacity: 0.9; }}
  .map-overlay {{ position: absolute; bottom: 12px; right: 12px; }}
  .open-maps-btn {{ background: #1a73e8; color: white; padding: 8px 14px; border-radius: 20px; font-size: 13px; font-weight: 500; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 2px 8px rgba(26,115,232,0.4); }}
  .open-maps-btn:hover {{ background: #1557b0; }}
  .results-count {{ font-size: 13px; color: #666; margin-bottom: 12px; padding: 0 4px; }}
  .place-card {{ background: white; border-radius: 10px; padding: 14px; margin-bottom: 10px; box-shadow: 0 1px 6px rgba(0,0,0,0.08); display: flex; gap: 12px; align-items: flex-start; position: relative; }}
  .place-number {{ background: #1a73e8; color: white; width: 26px; height: 26px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; flex-shrink: 0; }}
  .place-photo {{ width: 80px; height: 80px; border-radius: 8px; object-fit: cover; flex-shrink: 0; }}
  .place-info {{ flex: 1; min-width: 0; }}
  .place-name {{ font-size: 15px; font-weight: 600; color: #1a1a2e; margin-bottom: 3px; }}
  .place-type {{ font-size: 12px; color: #888; margin-bottom: 5px; }}
  .rating {{ display: flex; align-items: center; gap: 5px; margin-bottom: 4px; }}
  .stars {{ color: #fbbc04; font-size: 13px; letter-spacing: 1px; }}
  .rating-value {{ font-size: 13px; font-weight: 600; color: #1a1a2e; }}
  .rating-count {{ font-size: 12px; color: #888; }}
  .place-meta {{ display: flex; gap: 10px; align-items: center; margin-bottom: 4px; }}
  .price {{ color: #34a853; font-size: 13px; font-weight: 600; }}
  .open-status {{ font-size: 12px; font-weight: 500; }}
  .place-address {{ font-size: 12px; color: #666; margin-bottom: 6px; }}
  .maps-link {{ font-size: 12px; color: #1a73e8; text-decoration: none; font-weight: 500; }}
  .maps-link:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
<div class="header">
  <h2>🗺️ {query.title()}{location_label}</h2>
  <p>Found {len(places)} places matching your search</p>
</div>

<div class="map-container">
  <a href="{maps_search_url}" target="_blank" rel="noopener">
    <img class="map-img" src="{map_embed_url}" alt="Map showing search results"/>
  </a>
  <div class="map-overlay">
    <a class="open-maps-btn" href="{maps_search_url}" target="_blank" rel="noopener">
      🗺️ Open in Google Maps
    </a>
  </div>
</div>

<div class="results-count">Showing {len(places)} results</div>

{place_cards_html}

<script>
  // Auto-report height to Open WebUI for iframe sizing
  function reportHeight() {{
    const h = document.documentElement.scrollHeight;
    window.parent.postMessage({{ type: 'iframe:height', height: h }}, '*');
  }}
  window.addEventListener('load', reportHeight);
  window.addEventListener('resize', reportHeight);
  setTimeout(reportHeight, 500);
  // Also report after images load
  document.querySelectorAll('img').forEach(img => {{
    img.addEventListener('load', reportHeight);
  }});

</script>
</body>
</html>"""
