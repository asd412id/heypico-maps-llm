"""
title: Google Maps Place Search
description: Search for places (restaurants, cafes, attractions, etc.) near a location and display a rich info card in chat.
author: HeyPico AI Test
version: 4.0.0
license: MIT
requirements: httpx
"""

import httpx
import os
import urllib.parse
from pydantic import BaseModel, Field
from typing import Optional


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
            description="Internal API key for the backend (set in .env as BACKEND_API_KEY)",
        )
        default_radius_meters: int = Field(
            default=5000,
            description="Default search radius in meters",
        )

    def __init__(self):
        self.valves = self.Valves(
            backend_url=os.getenv("BACKEND_URL", "http://backend:8000"),
            frontend_url=os.getenv("FRONTEND_URL", "http://localhost:3000"),
            backend_api_key=os.getenv("BACKEND_API_KEY", ""),
        )

    async def search_places(
        self,
        query: str,
        location: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        max_results: int = 5,
        __event_emitter__=None,
    ) -> str:
        # Defensive cast — LLMs (esp. smaller models) sometimes pass args as strings
        try:
            max_results = int(max_results)
        except (TypeError, ValueError):
            max_results = 5
        if latitude is not None:
            try:
                latitude = float(latitude)
            except (TypeError, ValueError):
                latitude = None
        if longitude is not None:
            try:
                longitude = float(longitude)
            except (TypeError, ValueError):
                longitude = None
        """
        Search for places (restaurants, cafes, attractions, etc.) near a location.
        Returns a rich info card and place results with Google Maps links.

        :param query: What to search for, e.g. "pizza restaurant", "coffee shop", "tourist attraction"
        :param location: Location to search near, e.g. "Jakarta, Indonesia" or "SCBD Jakarta". If not provided, returns general results.
        :param latitude: Latitude coordinate from detect_my_location (e.g. -6.2). Use this for "near me" queries.
        :param longitude: Longitude coordinate from detect_my_location (e.g. 106.8). Use this for "near me" queries.
        :param max_results: Number of results to show (1-10)
        :return: Info card and place results with details
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
                        "latitude": latitude,
                        "longitude": longitude,
                        "radius_meters": self.valves.default_radius_meters,
                        "max_results": min(
                            max_results, 10
                        ),  # already cast to int above
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

        location_label = f" near {location}" if location else ""
        card_data = {
            "card_type": "places",
            "title": f"Search: {query}",
            "subtitle": f"Found {count} places{location_label}",
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
                f"{query} near {location}" if location else query
            )
            gmaps_search_url = f"https://www.google.com/maps/search/{search_query}/@{avg_lat},{avg_lng},14z"
        else:
            search_query = urllib.parse.quote(
                f"{query} near {location}" if location else query
            )
            gmaps_search_url = f"https://www.google.com/maps/search/{search_query}"
        map_card_data = {
            "card_type": "places_map",
            "title": f"Search: {query}",
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
            pass  # Card embed is optional — text result still works

        # Build concise result — card embed already shows full details
        place_names = ", ".join(p["name"] for p in places)
        return (
            f"Found {count} places for '{query}'{location_label}: {place_names}. "
            f"The map and detailed info card are shown above. "
            f"Give a brief, friendly summary of the results. Do NOT re-list all the places — the card already shows them. "
            f"You may highlight 1-2 interesting picks if relevant."
        )
