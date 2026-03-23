"""
title: Google Maps Area Explorer
description: Explore an area and discover top places by category (food, entertainment, coffee, shopping, attractions) with a rich info card overview.
author: HeyPico AI Test
version: 4.0.0
license: MIT
requirements: httpx
"""

import httpx
import os
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

    async def explore_area(
        self,
        area: str,
        category: Literal[
            "food", "entertainment", "shopping", "coffee", "attractions", "all"
        ] = "all",
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        __event_emitter__=None,
    ) -> str:
        """
        Explore an area and discover the top places in a chosen category. Shows a rich info card with recommendations.

        :param area: The area to explore, e.g. "SCBD Jakarta", "Bandung Old Town", "Seminyak Bali"
        :param category: Type of places to find: food, entertainment, shopping, coffee, attractions, or all
        :param latitude: Latitude coordinate from detect_my_location (e.g. -6.2). Use this for "near me" queries.
        :param longitude: Longitude coordinate from detect_my_location (e.g. 106.8). Use this for "near me" queries.
        :return: Info card with top place recommendations
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
                    json={
                        "area": area,
                        "category": category,
                        "latitude": latitude,
                        "longitude": longitude,
                        "max_results": 8,
                    },
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

        # Build info card data
        card_places = [
            {
                "name": p["name"],
                "address": p["address"],
                "rating": p.get("rating"),
                "user_ratings_total": p.get("user_ratings_total"),
                "types": p.get("types", [])[:2],
                "price_level": p.get("price_level"),
                "open_now": p.get("open_now"),
                "lat": p.get("lat"),
                "lng": p.get("lng"),
                "maps_url": p.get("maps_url", ""),
            }
            for p in places
        ]

        card_data = {
            "card_type": "places",
            "title": f"{label} in {area}",
            "subtitle": f"Found {len(places)} places",
            "places": card_places,
        }

        # Build map card data (Static Maps with numbered markers)
        # Build coordinate-based Google Maps URL so clicking the map shows the same area
        places_with_coords = [
            p for p in places if p.get("lat") is not None and p.get("lng") is not None
        ]
        if places_with_coords:
            avg_lat = sum(p["lat"] for p in places_with_coords) / len(
                places_with_coords
            )
            avg_lng = sum(p["lng"] for p in places_with_coords) / len(
                places_with_coords
            )
            search_query = urllib.parse.quote(
                f"{category} in {area}" if category != "all" else f"places in {area}"
            )
            gmaps_search_url = f"https://www.google.com/maps/search/{search_query}/@{avg_lat},{avg_lng},14z"
        else:
            search_query = urllib.parse.quote(
                f"{category} in {area}" if category != "all" else f"places in {area}"
            )
            gmaps_search_url = f"https://www.google.com/maps/search/{search_query}"
        map_card_data = {
            "card_type": "places_map",
            "title": f"{label} in {area}",
            "maps_url": gmaps_search_url,
            "places": [
                {"lat": p.get("lat"), "lng": p.get("lng")}
                for p in places
                if p.get("lat") is not None
            ],
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
        place_names = ", ".join(p["name"] for p in places)
        return (
            f"{label} in {area} — Found {len(places)} places: {place_names}. "
            f"The map and detailed info card are shown above. "
            f"Give a brief, friendly summary of the results. Do NOT re-list all the places — the card already shows them. "
            f"You may highlight 1-2 interesting picks if relevant."
        )
