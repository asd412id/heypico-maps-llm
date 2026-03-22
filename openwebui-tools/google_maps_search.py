"""
title: Google Maps Place Search
description: Search for places (restaurants, cafes, attractions, etc.) near a location and display interactive embedded maps in chat.
author: HeyPico AI Test
version: 2.0.0
license: MIT
requirements: httpx
"""

import httpx
import os
import urllib.parse
from pydantic import BaseModel, Field
from typing import Optional


def _redirect_url(frontend_url: str, target_url: str) -> str:
    """Route Google Maps URL through /api/maps/open to bypass COOP."""
    base = frontend_url.rstrip("/")
    return f"{base}/api/maps/open?url={urllib.parse.quote(target_url, safe='')}"


def _embed_url(frontend_url: str, maps_embed_url: str, height: int = 450) -> str:
    """Wrap a Google Maps embed URL via /api/maps/embed wrapper.
    The wrapper page sends postMessage to Open WebUI so the iframe auto-resizes."""
    base = frontend_url.rstrip("/")
    return f"{base}/api/maps/embed?url={urllib.parse.quote(maps_embed_url, safe='')}&height={height}"


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
        google_maps_api_key: str = Field(
            default="",
            description="Google Maps API key — used for embedding the map in the UI",
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
        Returns a map and place results with clickable Google Maps links.

        :param query: What to search for, e.g. "pizza restaurant", "coffee shop", "tourist attraction"
        :param location: Location to search near, e.g. "Jakarta, Indonesia" or "SCBD Jakarta". If not provided, returns general results.
        :param max_results: Number of results to show (1-10)
        :return: Map and place results with clickable links
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

        redirect = lambda url: _redirect_url(self.valves.frontend_url, url)

        # Build Google Maps Embed URL for interactive map
        search_q = f"{query} near {location}" if location else query
        embed_url = (
            f"https://www.google.com/maps/embed/v1/search"
            f"?key={self.valves.google_maps_api_key}"
            f"&q={urllib.parse.quote(search_q)}"
        )

        # Wrap in backend proxy so the iframe auto-resizes via postMessage
        wrapper_url = _embed_url(self.valves.frontend_url, embed_url)

        # Emit the interactive map as an embed (rendered as sandboxed iframe by Open WebUI)
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "embeds",
                    "data": {"embeds": [wrapper_url]},
                }
            )

        # Build markdown result for LLM to present
        location_label = f" near {location}" if location else ""
        lines = []
        lines.append(f"Found {count} places for '{query}'{location_label}.\n")

        for i, p in enumerate(places):
            link = redirect(p["maps_url"])
            rating = f"⭐ {p['rating']}" if p.get("rating") else ""
            reviews = (
                f"({p.get('user_ratings_total', 0):,} reviews)"
                if p.get("user_ratings_total")
                else ""
            )
            price = (
                "$" * (p.get("price_level", 0) + 1)
                if p.get("price_level") is not None
                else ""
            )
            status = ""
            if p.get("open_now") is not None:
                status = "🟢 Open now" if p["open_now"] else "🔴 Closed"
            types = ", ".join(
                t.replace("_", " ").title() for t in p.get("types", [])[:2]
            )

            lines.append(f"{i + 1}. **{p['name']}** — {types}")
            details = " · ".join(filter(None, [rating, reviews, price, status]))
            if details:
                lines.append(f"   {details}")
            lines.append(f"   📍 {p['address']}")
            lines.append(f"   🔗 [View on Google Maps]({link})")
            lines.append("")

        lines.append(
            "\nPresent each place above with its details and clickable Google Maps link."
        )

        return "\n".join(lines)
