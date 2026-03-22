"""
title: Google Maps Area Explorer
description: Explore an area and discover top places by category (food, entertainment, coffee, shopping, attractions) with an interactive map overview.
author: HeyPico AI Test
version: 1.0.0
license: MIT
requirements: httpx
"""

import httpx
import os
from pydantic import BaseModel, Field
from typing import Literal


class Tools:
    class Valves(BaseModel):
        backend_url: str = Field(
            default="http://backend:8000",
            description="URL of the HeyPico Maps Backend API",
        )
        backend_api_key: str = Field(
            default="",
            description="Internal API key for the backend",
        )
        google_maps_api_key: str = Field(
            default="",
            description="Google Maps API key for embed iframe and static maps",
        )

    def __init__(self):
        self.valves = self.Valves(
            backend_url=os.getenv("BACKEND_URL", "http://backend:8000"),
            backend_api_key=os.getenv("BACKEND_API_KEY", ""),
            google_maps_api_key=os.getenv("GOOGLE_MAPS_API_KEY", ""),
        )

    async def explore_area(
        self,
        area: str,
        category: Literal[
            "food", "entertainment", "shopping", "coffee", "attractions", "all"
        ] = "all",
        __event_emitter__=None,
    ) -> str:
        """
        Explore an area and discover the top places in a chosen category. Shows an interactive overview map with recommendations.

        :param area: The area to explore, e.g. "SCBD Jakarta", "Bandung Old Town", "Seminyak Bali"
        :param category: Type of places to find: food, entertainment, shopping, coffee, attractions, or all
        :return: Interactive area map with top place recommendations
        """
        category_labels = {
            "food": "🍽️ Food & Restaurants",
            "entertainment": "🎭 Entertainment",
            "shopping": "🛍️ Shopping",
            "coffee": "☕ Cafes & Coffee",
            "attractions": "🏛️ Attractions & Landmarks",
            "all": "✨ Top Places",
        }
        label = category_labels.get(category, "Places")

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"🔍 Exploring {area} for {label}...",
                        "done": False,
                    },
                }
            )

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    f"{self.valves.backend_url}/maps/explore",
                    json={"area": area, "category": category, "max_results": 8},
                    headers={"X-API-Key": self.valves.backend_api_key},
                )
                response.raise_for_status()
                data = response.json()

        except httpx.HTTPStatusError as e:
            err = f"Backend error: {e.response.status_code}"
            if __event_emitter__:
                await __event_emitter__(
                    {"type": "status", "data": {"description": err, "done": True}}
                )
            return f"Sorry, I couldn't explore {area} right now. Error: {err}"
        except Exception as e:
            if __event_emitter__:
                await __event_emitter__(
                    {"type": "status", "data": {"description": str(e), "done": True}}
                )
            return f"Sorry, an error occurred: {str(e)}"

        places = data.get("places", [])

        if not places:
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": "No places found", "done": True},
                    }
                )
            return (
                f"I couldn't find {label} in {area}. Try a different area or category."
            )

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"✅ Found {len(places)} places in {area}",
                        "done": True,
                    },
                }
            )

        html = _build_explore_html(
            places, area, category, label, self.valves.google_maps_api_key
        )
        return html


def _build_explore_html(
    places: list, area: str, category: str, label: str, api_key: str
) -> str:
    """Build a rich HTML page with embedded area overview map and place grid."""

    center_lat = places[0]["lat"] if places else 0
    center_lng = places[0]["lng"] if places else 0

    # Build multi-marker static map
    markers_param = "&".join(
        f"markers=color:red%7Clabel:{i + 1}%7C{p['lat']},{p['lng']}"
        for i, p in enumerate(places)
    )
    static_map_url = (
        f"https://maps.googleapis.com/maps/api/staticmap"
        f"?center={center_lat},{center_lng}&zoom=14&size=800x350"
        f"&maptype=roadmap&{markers_param}&key={api_key}"
    )

    # Interactive Google Maps link for the area
    maps_area_url = f"https://www.google.com/maps/search/{label.replace('✨', '').strip().replace(' ', '+')}/@{center_lat},{center_lng},14z"

    # Category color themes
    category_colors = {
        "food": ("#ea4335", "#fce8e6"),
        "entertainment": ("#9334e6", "#f3e8fd"),
        "shopping": ("#e37400", "#fef3e2"),
        "coffee": ("#795548", "#efebe9"),
        "attractions": ("#1a73e8", "#e8f0fe"),
        "all": ("#34a853", "#e6f4ea"),
    }
    primary_color, bg_color = category_colors.get(category, ("#1a73e8", "#e8f0fe"))

    # Build place grid cards
    place_cards_html = ""
    for i, place in enumerate(places):
        rating_html = ""
        if place.get("rating"):
            rating_html = f"""
            <div class="place-rating">
              ⭐ {place["rating"]}
              <span class="rc">({place.get("user_ratings_total", 0):,})</span>
            </div>"""

        price_html = ""
        if place.get("price_level") is not None:
            price_html = (
                f"<span class='price'>{'$' * (place['price_level'] + 1)}</span>"
            )

        open_html = ""
        if place.get("open_now") is not None:
            open_label = "Open" if place["open_now"] else "Closed"
            open_color = "#22c55e" if place["open_now"] else "#ef4444"
            open_html = f"<span class='open-badge' style='background:{open_color}15;color:{open_color}'>{open_label}</span>"

        img_html = ""
        if place.get("photo_url"):
            img_html = f'<img class="card-img" src="{place["photo_url"]}" alt="{place["name"]}" loading="lazy"/>'
        else:
            img_html = f'<div class="card-img-placeholder" style="background:{bg_color}"><span style="font-size:28px">{label[0]}</span></div>'

        types_str = " · ".join(
            t.replace("_", " ").title() for t in place.get("types", [])[:2]
        )

        place_cards_html += f"""
        <a class="place-card" href="{place["maps_url"]}" target="_blank" rel="noopener">
          <div class="card-img-wrapper">
            {img_html}
            <span class="card-num" style="background:{primary_color}">{i + 1}</span>
          </div>
          <div class="card-body">
            <div class="card-name">{place["name"]}</div>
            <div class="card-type">{types_str}</div>
            {rating_html}
            <div class="card-meta">{price_html}{open_html}</div>
            <div class="card-addr">📍 {place["address"][:50]}{"..." if len(place["address"]) > 50 else ""}</div>
          </div>
        </a>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8f9fa; color: #1a1a2e; padding: 12px; }}
  .header {{ background: linear-gradient(135deg, {primary_color}, {primary_color}cc); color: white; padding: 16px 20px; border-radius: 12px; margin-bottom: 14px; }}
  .header h2 {{ font-size: 18px; font-weight: 700; }}
  .header p {{ font-size: 13px; opacity: 0.85; margin-top: 4px; }}
  .map-wrap {{ border-radius: 12px; overflow: hidden; margin-bottom: 14px; box-shadow: 0 2px 12px rgba(0,0,0,0.15); position: relative; }}
  .map-img {{ width: 100%; display: block; cursor: pointer; }}
  .map-cta {{ position: absolute; bottom: 12px; right: 12px; }}
  .cta-btn {{ background: {primary_color}; color: white; padding: 8px 14px; border-radius: 20px; font-size: 13px; font-weight: 500; text-decoration: none; display: inline-flex; align-items: center; gap: 5px; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }}
  .section-title {{ font-size: 14px; font-weight: 600; margin-bottom: 10px; color: #333; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; }}
  .place-card {{ background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 6px rgba(0,0,0,0.08); text-decoration: none; color: inherit; display: block; transition: transform 0.15s, box-shadow 0.15s; }}
  .place-card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0,0,0,0.12); }}
  .card-img-wrapper {{ position: relative; height: 110px; }}
  .card-img {{ width: 100%; height: 110px; object-fit: cover; display: block; }}
  .card-img-placeholder {{ width: 100%; height: 110px; display: flex; align-items: center; justify-content: center; }}
  .card-num {{ position: absolute; top: 8px; left: 8px; color: white; width: 22px; height: 22px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; }}
  .card-body {{ padding: 10px; }}
  .card-name {{ font-size: 13px; font-weight: 600; margin-bottom: 2px; color: #1a1a2e; }}
  .card-type {{ font-size: 11px; color: #888; margin-bottom: 4px; }}
  .place-rating {{ font-size: 12px; color: #444; margin-bottom: 3px; }}
  .rc {{ color: #888; font-size: 11px; }}
  .card-meta {{ display: flex; gap: 6px; align-items: center; margin-bottom: 3px; }}
  .price {{ color: #34a853; font-size: 12px; font-weight: 600; }}
  .open-badge {{ font-size: 11px; padding: 2px 7px; border-radius: 10px; font-weight: 500; }}
  .card-addr {{ font-size: 11px; color: #888; }}
</style>
</head>
<body>
<div class="header">
  <h2>{label} in {area}</h2>
  <p>Discover the best spots in the area</p>
</div>

<div class="map-wrap">
  <a href="{maps_area_url}" target="_blank" rel="noopener">
    <img class="map-img" src="{static_map_url}" alt="Area map of {area}"/>
  </a>
  <div class="map-cta">
    <a class="cta-btn" href="{maps_area_url}" target="_blank" rel="noopener">
      🗺️ Explore in Maps
    </a>
  </div>
</div>

<div class="section-title">Top {len(places)} picks in {area}</div>
<div class="grid">
  {place_cards_html}
</div>

<script>
  function reportHeight() {{
    window.parent.postMessage({{ type: 'iframe:height', height: document.documentElement.scrollHeight }}, '*');
  }}
  window.addEventListener('load', reportHeight);
  window.addEventListener('resize', reportHeight);
  setTimeout(reportHeight, 300);
  setTimeout(reportHeight, 1000);
  document.querySelectorAll('img').forEach(img => img.addEventListener('load', reportHeight));
</script>
</body>
</html>"""
