"""
title: Google Maps Area Explorer
description: Explore an area and discover top places by category (food, entertainment, coffee, shopping, attractions) with an interactive map overview.
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


def _embed_url(frontend_url: str, maps_embed_url: str, height: int = 450) -> str:
    """Wrap a Google Maps embed URL via /api/maps/embed wrapper."""
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
            description="Internal API key for the backend",
        )
        google_maps_api_key: str = Field(
            default="",
            description="Google Maps API key for embed iframe and static maps",
        )

    def __init__(self):
        self.valves = self.Valves(
            backend_url=os.getenv("BACKEND_URL", "http://backend:8000"),
            frontend_url=os.getenv("FRONTEND_URL", "http://localhost:3000"),
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

        redirect = lambda url: _redirect_url(self.valves.frontend_url, url)

        # Build category query for embed
        category_queries = {
            "food": "restaurants",
            "entertainment": "entertainment",
            "shopping": "shopping",
            "coffee": "cafes",
            "attractions": "tourist attractions",
            "all": "popular places",
        }
        cat_q = category_queries.get(category, "places")
        embed_url = (
            f"https://www.google.com/maps/embed/v1/search"
            f"?key={self.valves.google_maps_api_key}"
            f"&q={urllib.parse.quote(f'{cat_q} in {area}')}"
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

        lines = []
        lines.append(f"{label} in {area} — Found {len(places)} places.\n")

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
