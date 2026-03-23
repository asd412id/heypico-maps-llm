"""
title: Google Maps Directions
description: Get turn-by-turn directions between two locations with a rich info card in chat.
author: HeyPico AI Test
version: 4.0.0
license: MIT
requirements: httpx
"""

import httpx
import os
import re
import urllib.parse
from pydantic import BaseModel, Field
from typing import Literal, Optional


def _card_url(frontend_url: str, card_id: str) -> str:
    """Build the public URL for a rendered card embed."""
    base = frontend_url.rstrip("/")
    return f"{base}/api/maps/card/{card_id}"


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

    def __init__(self):
        self.valves = self.Valves(
            backend_url=os.getenv("BACKEND_URL", "http://backend:8000"),
            frontend_url=os.getenv("FRONTEND_URL", "http://localhost:3000"),
            backend_api_key=os.getenv("BACKEND_API_KEY", ""),
        )

    async def get_directions(
        self,
        origin: str,
        destination: str,
        travel_mode: Literal["driving", "walking", "transit", "bicycling"] = "driving",
        __event_emitter__=None,
        __user__: dict = None,
    ) -> str:
        """
        Get turn-by-turn directions between two locations. Shows a rich info card with route and step-by-step instructions.

        :param origin: Starting point — use a real place name or address (e.g. "Monas Jakarta", "Jl. Sudirman No.1") or coordinates like "-6.2,106.8". NEVER use "My current location" or "my location".
        :param destination: End point, e.g. "Sarinah Jakarta" or "Bandung, West Java"
        :param travel_mode: Transportation mode: driving, walking, transit, or bicycling
        :return: Info card with directions and route steps
        """
        # Auto-fix: if origin looks like "my location"/"current location", resolve to actual coordinates
        origin_lower = (origin or "").lower().strip()
        location_phrases = [
            "my current location",
            "my location",
            "current location",
            "lokasi saya",
            "lokasi saya sekarang",
            "lokasiku",
            "lokasiku sekarang",
            "posisi saya",
            "tempat saya",
            "di sini",
            "dari sini",
            "sini",
        ]
        if any(phrase in origin_lower for phrase in location_phrases):
            stored = await self._get_stored_location(__user__)
            if stored:
                origin = f"{stored['latitude']},{stored['longitude']}"

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
                        "description": f"\u2705 Route found: {data.get('total_distance', '')} \u00b7 {data.get('total_duration', '')}",
                        "done": True,
                    },
                }
            )

        mode_icons = {
            "driving": "🚗",
            "walking": "🚶",
            "transit": "🚌",
            "bicycling": "🚲",
        }
        mode_icon = mode_icons.get(travel_mode, "🗺️")
        origin_addr = data.get("origin_address", origin)
        dest_addr = data.get("destination_address", destination)

        # Build direction steps for info card
        card_steps = [
            {
                "instruction": re.sub(r"<[^>]+>", "", s.get("html_instructions", "")),
                "distance": s.get("distance", ""),
                "duration": s.get("duration", ""),
            }
            for s in data.get("steps", [])
        ]

        card_data = {
            "card_type": "directions",
            "title": f"{origin_addr} → {dest_addr}",
            "origin": origin_addr,
            "destination": dest_addr,
            "distance": data.get("total_distance", ""),
            "duration": data.get("total_duration", ""),
            "travel_mode": travel_mode,
            "steps": card_steps,
        }

        # Build map card data (Static Maps with route polyline)
        gmaps_dir_url = (
            f"https://www.google.com/maps/dir/?api=1"
            f"&origin={urllib.parse.quote(origin)}"
            f"&destination={urllib.parse.quote(destination)}"
            f"&travelmode={travel_mode}"
        )
        map_card_data = {
            "card_type": "directions_map",
            "title": f"{origin_addr} → {dest_addr}",
            "maps_url": gmaps_dir_url,
            "overview_polyline": data.get("overview_polyline", ""),
            "origin_lat": data.get("origin_lat"),
            "origin_lng": data.get("origin_lng"),
            "dest_lat": data.get("dest_lat"),
            "dest_lng": data.get("dest_lng"),
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Create map card
                map_resp = await client.post(
                    f"{self.valves.backend_url}/maps/card",
                    json=map_card_data,
                    headers={"X-API-Key": self.valves.backend_api_key},
                )
                map_resp.raise_for_status()
                map_card_id = map_resp.json()["card_id"]

                # Create info card
                card_resp = await client.post(
                    f"{self.valves.backend_url}/maps/card",
                    json=card_data,
                    headers={"X-API-Key": self.valves.backend_api_key},
                )
                card_resp.raise_for_status()
                card_id = card_resp.json()["card_id"]

            map_embed = _card_url(self.valves.frontend_url, map_card_id)
            card_embed = _card_url(self.valves.frontend_url, card_id)
            if __event_emitter__:
                await __event_emitter__(
                    {"type": "embeds", "data": {"embeds": [map_embed, card_embed]}}
                )
        except Exception:
            pass

        # Build concise result — card embed already shows full details
        return (
            f"{mode_icon} Directions: {origin_addr} \u2192 {dest_addr}. "
            f"Distance: {data.get('total_distance', '')}, Duration: {data.get('total_duration', '')}. "
            f"The route map and step-by-step directions card are shown above. "
            f"Give a brief, friendly summary (distance, duration, travel mode). "
            f"Do NOT re-list all the route steps \u2014 the card already shows them."
        )

    async def _get_stored_location(self, user: dict = None) -> Optional[dict]:
        """Fetch cached user GPS location from backend."""
        user_id = (user or {}).get("id", "default")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self.valves.backend_url}/maps/user-location",
                    params={"user_id": user_id},
                    headers={"X-API-Key": self.valves.backend_api_key},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("found"):
                        return data
        except Exception:
            pass
        return None
