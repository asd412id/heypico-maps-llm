"""
title: Google Maps Directions
description: Get turn-by-turn directions between two locations with an embedded interactive map in chat.
author: HeyPico AI Test
version: 2.0.0
license: MIT
requirements: httpx
"""

import httpx
import os
import urllib.parse
from pydantic import BaseModel, Field
from typing import Literal


def _redirect_url(frontend_url: str, target_url: str) -> str:
    """Route Google Maps URL through /api/maps/open to bypass COOP."""
    base = frontend_url.rstrip("/")
    return f"{base}/api/maps/open?url={urllib.parse.quote(target_url, safe='')}"


def _embed_url(
    frontend_url: str, maps_embed_url: str, height: int = 450, open_url: str = ""
) -> str:
    """Wrap a Google Maps embed URL via /api/maps/embed wrapper.
    open_url (optional): pre-proxied URL to intercept the 'Open in Maps' button."""
    base = frontend_url.rstrip("/")
    result = f"{base}/api/maps/embed?url={urllib.parse.quote(maps_embed_url, safe='')}&height={height}"
    if open_url:
        result += f"&open_url={urllib.parse.quote(open_url, safe='')}"
    return result


class Tools:
    class Valves(BaseModel):
        backend_url: str = Field(
            default="http://backend:8000",
            description="Internal URL of the HeyPico Maps Backend API (docker network)",
        )
        frontend_url: str = Field(
            default="http://localhost:3000",
            description="Public-facing URL of the web UI (used for embed/redirect links in chat)",
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
            frontend_url=os.getenv("FRONTEND_URL", "http://localhost:3000"),
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

        redirect = lambda url: _redirect_url(self.valves.frontend_url, url)

        mode_icons = {
            "driving": "🚗",
            "walking": "🚶",
            "transit": "🚌",
            "bicycling": "🚲",
        }
        mode_icon = mode_icons.get(travel_mode, "🗺️")

        maps_url = redirect(data.get("maps_url", ""))
        embed_url = data.get("embed_url", "")
        origin_addr = data.get("origin_address", origin)
        dest_addr = data.get("destination_address", destination)

        # Wrap in backend proxy — pass maps_url as overlay so 'Open in Maps' routes via proxy
        wrapper_url = (
            _embed_url(self.valves.frontend_url, embed_url, open_url=maps_url)
            if embed_url
            else ""
        )

        # Emit the interactive map as an embed (rendered as sandboxed iframe by Open WebUI)
        if __event_emitter__ and wrapper_url:
            await __event_emitter__(
                {
                    "type": "embeds",
                    "data": {"embeds": [wrapper_url]},
                }
            )

        import re

        lines = []
        lines.append(f"{mode_icon} Directions: {origin_addr} → {dest_addr}")
        lines.append(
            f"Distance: {data['total_distance']} · Duration: {data['total_duration']}"
        )
        lines.append(f"[🗺️ Open in Google Maps]({maps_url})")
        lines.append("")

        steps = data.get("steps", [])
        if steps:
            lines.append(f"Route ({len(steps)} steps):")
            for i, step in enumerate(steps):
                instruction = re.sub(r"<[^>]+>", "", step.get("html_instructions", ""))
                dist = step.get("distance", "")
                dur = step.get("duration", "")
                lines.append(f"  {i + 1}. {instruction} ({dist}, {dur})")
            lines.append("")

        lines.append(
            "Present the directions above with the clickable Google Maps link."
        )

        return "\n".join(lines)
