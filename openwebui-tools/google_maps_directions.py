"""
title: Google Maps Directions
description: Get turn-by-turn directions between two locations with an embedded interactive map in chat.
author: HeyPico AI Test
version: 1.0.0
license: MIT
requirements: httpx
"""

import httpx
import os
from pydantic import BaseModel, Field
from typing import Optional, Literal


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
            description="Google Maps API key for embed iframe",
        )

    def __init__(self):
        self.valves = self.Valves(
            backend_url=os.getenv("BACKEND_URL", "http://backend:8000"),
            backend_api_key=os.getenv("BACKEND_API_KEY", ""),
            google_maps_api_key=os.getenv("GOOGLE_MAPS_API_KEY", ""),
        )

    async def get_directions(
        self,
        origin: str,
        destination: str,
        travel_mode: Literal["driving", "walking", "transit", "bicycling"] = "driving",
        __event_emitter__=None,
    ) -> str:
        """
        Get turn-by-turn directions between two locations. Shows an embedded interactive map with the route and step-by-step instructions.

        :param origin: Starting point, e.g. "Monas Jakarta" or "Jl. Sudirman No.1"
        :param destination: End point, e.g. "Sarinah Jakarta" or "Bandung, West Java"
        :param travel_mode: Transportation mode: driving, walking, transit, or bicycling
        :return: Interactive map with directions and route steps
        """
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"🗺️ Getting directions from {origin} to {destination}...",
                        "done": False,
                    },
                }
            )

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    f"{self.valves.backend_url}/maps/directions",
                    json={
                        "origin": origin,
                        "destination": destination,
                        "travel_mode": travel_mode,
                        "language": "en",
                    },
                    headers={"X-API-Key": self.valves.backend_api_key},
                )
                response.raise_for_status()
                data = response.json()

        except httpx.HTTPStatusError as e:
            err = f"Could not get directions: {e.response.status_code}"
            if __event_emitter__:
                await __event_emitter__(
                    {"type": "status", "data": {"description": err, "done": True}}
                )
            return f"Sorry, I couldn't get directions. Error: {err}"
        except Exception as e:
            if __event_emitter__:
                await __event_emitter__(
                    {"type": "status", "data": {"description": str(e), "done": True}}
                )
            return f"Sorry, an error occurred: {str(e)}"

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"✅ Route found: {data['total_distance']} · {data['total_duration']}",
                        "done": True,
                    },
                }
            )

        html = _build_directions_html(
            data, travel_mode, self.valves.google_maps_api_key
        )
        return html


def _build_directions_html(data: dict, travel_mode: str, api_key: str) -> str:
    """Build a rich HTML page with embedded directions map and step-by-step instructions."""

    mode_icons = {
        "driving": "🚗",
        "walking": "🚶",
        "transit": "🚌",
        "bicycling": "🚲",
    }
    mode_icon = mode_icons.get(travel_mode, "🗺️")

    # Build embed URL for the directions iframe
    embed_url = data.get("embed_url", "")
    maps_url = data.get("maps_url", "")

    # Strip API key from embed_url before including in HTML
    # (iframe embed is fine — browsers don't expose it to users, but it's in page source)
    # Best practice: use Maps Embed API key restricted to your domain
    embed_src = embed_url if embed_url else ""

    # Build steps HTML
    steps_html = ""
    for i, step in enumerate(data.get("steps", [])):
        step_icon = mode_icons.get(step.get("travel_mode", travel_mode), "➤")
        # Strip HTML tags from instructions for clean display
        raw_instructions = step.get("html_instructions", "")
        # We'll keep it as HTML since it contains formatting like <b> tags
        steps_html += f"""
        <div class="step">
          <div class="step-num">{i + 1}</div>
          <div class="step-body">
            <div class="step-text">{raw_instructions}</div>
            <div class="step-meta">
              <span>{step.get("distance", "")}</span>
              <span>·</span>
              <span>{step.get("duration", "")}</span>
            </div>
          </div>
        </div>"""

    if not steps_html:
        steps_html = (
            "<p style='color:#666;padding:10px'>No detailed steps available.</p>"
        )

    origin_addr = data.get("origin_address", "")
    dest_addr = data.get("destination_address", "")
    distance = data.get("total_distance", "")
    duration = data.get("total_duration", "")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8f9fa; color: #1a1a2e; padding: 12px; }}
  .header {{ background: linear-gradient(135deg, #34a853, #137333); color: white; padding: 16px 20px; border-radius: 12px; margin-bottom: 14px; }}
  .header h2 {{ font-size: 17px; font-weight: 600; margin-bottom: 6px; }}
  .route-meta {{ display: flex; gap: 16px; margin-top: 8px; flex-wrap: wrap; }}
  .route-badge {{ background: rgba(255,255,255,0.2); padding: 5px 12px; border-radius: 20px; font-size: 13px; font-weight: 500; }}
  .origin-dest {{ margin-bottom: 14px; display: flex; flex-direction: column; gap: 6px; }}
  .point-row {{ display: flex; align-items: center; gap: 10px; background: white; padding: 10px 14px; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }}
  .point-dot {{ width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }}
  .dot-origin {{ background: #34a853; }}
  .dot-dest {{ background: #ea4335; }}
  .point-text {{ font-size: 13px; color: #444; }}
  .map-iframe-container {{ border-radius: 12px; overflow: hidden; margin-bottom: 14px; box-shadow: 0 2px 12px rgba(0,0,0,0.15); }}
  .map-iframe {{ width: 100%; height: 300px; border: none; display: block; }}
  .open-btn {{ display: block; text-align: center; background: #34a853; color: white; text-decoration: none; padding: 10px 16px; border-radius: 8px; font-size: 14px; font-weight: 500; margin-bottom: 14px; }}
  .open-btn:hover {{ background: #2d8f47; }}
  .steps-header {{ font-size: 14px; font-weight: 600; color: #1a1a2e; margin-bottom: 8px; padding: 0 2px; }}
  .steps-list {{ background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 6px rgba(0,0,0,0.06); }}
  .step {{ display: flex; gap: 12px; padding: 12px 14px; border-bottom: 1px solid #f0f0f0; align-items: flex-start; }}
  .step:last-child {{ border-bottom: none; }}
  .step-num {{ background: #1a73e8; color: white; width: 22px; height: 22px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; flex-shrink: 0; margin-top: 2px; }}
  .step-body {{ flex: 1; }}
  .step-text {{ font-size: 13px; color: #333; line-height: 1.4; }}
  .step-text b {{ color: #1a1a2e; }}
  .step-meta {{ font-size: 12px; color: #888; margin-top: 4px; display: flex; gap: 6px; }}
</style>
</head>
<body>
<div class="header">
  <h2>{mode_icon} Directions by {travel_mode.title()}</h2>
  <div class="route-meta">
    <span class="route-badge">📏 {distance}</span>
    <span class="route-badge">⏱️ {duration}</span>
  </div>
</div>

<div class="origin-dest">
  <div class="point-row">
    <div class="point-dot dot-origin"></div>
    <div class="point-text"><strong>From:</strong> {origin_addr}</div>
  </div>
  <div class="point-row">
    <div class="point-dot dot-dest"></div>
    <div class="point-text"><strong>To:</strong> {dest_addr}</div>
  </div>
</div>

<div class="map-iframe-container">
  <iframe class="map-iframe" src="{embed_src}" allowfullscreen loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>
</div>

<a class="open-btn" href="{maps_url}" target="_blank" rel="noopener">
  🗺️ Open Full Route in Google Maps
</a>

<div class="steps-header">📋 Step-by-step directions ({len(data.get("steps", []))} steps)</div>
<div class="steps-list">
  {steps_html}
</div>

<script>
  function reportHeight() {{
    window.parent.postMessage({{ type: 'iframe:height', height: document.documentElement.scrollHeight }}, '*');
  }}
  window.addEventListener('load', reportHeight);
  window.addEventListener('resize', reportHeight);
  setTimeout(reportHeight, 300);
  setTimeout(reportHeight, 1000);
</script>
</body>
</html>"""
