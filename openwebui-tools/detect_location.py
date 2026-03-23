"""
title: Detect My Location
description: Detect the user's current GPS location. ONLY use this when the user explicitly wants results near their CURRENT location ("near me", "nearby", "dekat saya", "terdekat", "sekitar sini", "di sekitar saya", "lokasi saya"). DO NOT use this when the user specifies any location name, city, address, or landmark in their query — in that case, pass the location directly to search_places or explore_area instead.
author: HeyPico AI Test
version: 3.0.0
license: MIT
requirements: httpx
"""

import asyncio
import httpx
import ipaddress
import os
import uuid
from pydantic import BaseModel, Field
from typing import Optional


def _card_url(frontend_url: str, path: str) -> str:
    base = frontend_url.rstrip("/")
    return f"{base}{path}"


class Tools:
    class Valves(BaseModel):
        backend_url: str = Field(
            default="http://backend:8000",
            description="Internal URL of the HeyPico Maps Backend API (docker network)",
        )
        frontend_url: str = Field(
            default="http://localhost:3000",
            description="Public-facing URL of the web UI",
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

    async def detect_my_location(
        self,
        __event_emitter__=None,
        __request__=None,
        __user__: dict = None,
    ) -> str:
        """
        Detect the user's current location using browser GPS geolocation (precise) with IP geolocation fallback.

        ONLY call this tool when the user explicitly wants results near their CURRENT physical location, using
        phrases such as: "near me", "nearby", "closest to me", "terdekat", "dekat saya", "sekitar sini",
        "di sekitar saya", "sekitar aku", "lokasi saya sekarang", "di dekat saya".

        DO NOT call this tool when:
        - The user specifies any location by name (city, neighborhood, landmark, address, region, country).
          Examples: "SCBD Jakarta", "Bandung", "Jl. Sudirman", "Bali", "Sinjai", "Makassar".
        - The query contains an explicit location keyword like "in [place]", "at [place]", "near [place name]",
          "di [kota]", "sekitar [nama tempat]", "di daerah [X]".
        - The user asks about a specific named area, district, or address.

        CORRECT usage:
          "Find coffee shops near me" → call detect_my_location first
          "Restaurants nearby" → call detect_my_location first
          "Tempat makan terdekat" → call detect_my_location first

        WRONG usage (DO NOT call detect_my_location for these):
          "Coffee shops in SCBD Jakarta" → pass location="SCBD Jakarta" directly to search_places
          "Restaurants in Bandung" → pass location="Bandung" directly to search_places
          "Find places near Monas" → pass location="Monas Jakarta" directly to search_places
          "Kopi di Makassar" → pass location="Makassar" directly to search_places

        :return: Detected location with city, region, country, and coordinates (latitude/longitude)
        """
        user_id = (__user__ or {}).get("id", "default")
        request_id = str(uuid.uuid4())

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": "📍 Detecting your location...",
                        "done": False,
                    },
                }
            )

        # Step 1: Check if we already have stored browser GPS coordinates
        stored_gps = await self._get_stored_location(user_id)
        if stored_gps:
            lat = stored_gps["latitude"]
            lng = stored_gps["longitude"]
            accuracy = stored_gps.get("accuracy", "unknown")

            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": f"📍 GPS location detected (±{accuracy}m)",
                            "done": True,
                        },
                    }
                )

            city_name = await self._reverse_geocode(lat, lng)
            return (
                f"User's GPS location detected (precise, ±{accuracy}m): {city_name}\n"
                f"Coordinates: latitude={lat}, longitude={lng}\n"
                f"Use these coordinates when calling search_places or explore_area. "
                f"Pass latitude={lat} and longitude={lng} as parameters to get nearby results."
            )

        # Step 2: No stored GPS — emit geolocation card and wait for browser GPS
        try:
            geo_card_url = _card_url(
                self.valves.frontend_url,
                f"/api/maps/user-location/card/{user_id}?rid={request_id}",
            )
            if __event_emitter__:
                await __event_emitter__(
                    {"type": "embeds", "data": {"embeds": [geo_card_url]}}
                )
        except Exception:
            pass

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": "📍 Waiting for GPS permission...",
                        "done": False,
                    },
                }
            )

        # Step 3: Poll for browser GPS result (max 20 seconds, check every 1 second)
        gps_result = await self._poll_geo_result(request_id, max_wait=20, interval=1.0)

        if gps_result and gps_result.get("status") == "ok":
            lat = gps_result["latitude"]
            lng = gps_result["longitude"]
            accuracy = gps_result.get("accuracy", "unknown")

            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": f"📍 GPS location detected (±{accuracy}m)",
                            "done": True,
                        },
                    }
                )

            city_name = await self._reverse_geocode(lat, lng)
            return (
                f"User's GPS location detected (precise, ±{accuracy}m): {city_name}\n"
                f"Coordinates: latitude={lat}, longitude={lng}\n"
                f"Use these coordinates when calling search_places or explore_area. "
                f"Pass latitude={lat} and longitude={lng} as parameters to get nearby results."
            )

        if gps_result and gps_result.get("status") == "denied":
            # User denied GPS — fall back to IP
            pass

        # Step 4: GPS not available or denied — fall back to IP geolocation
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": "📍 Using IP-based location...",
                        "done": False,
                    },
                }
            )

        return await self._ip_geolocation(__request__, __event_emitter__)

    async def _get_stored_location(self, user_id: str) -> Optional[dict]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self.valves.backend_url}/maps/user-location",
                    params={"user_id": user_id},
                    headers={"X-API-Key": self.valves.backend_api_key},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("found") and data.get("source") == "browser":
                        return data
        except Exception:
            pass
        return None

    async def _poll_geo_result(
        self, request_id: str, max_wait: int = 20, interval: float = 1.0
    ) -> Optional[dict]:
        elapsed = 0.0
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                while elapsed < max_wait:
                    await asyncio.sleep(interval)
                    elapsed += interval
                    try:
                        resp = await client.get(
                            f"{self.valves.backend_url}/maps/geo-result/{request_id}",
                            headers={"X-API-Key": self.valves.backend_api_key},
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            if data.get("found"):
                                return data
                    except Exception:
                        pass
        except Exception:
            pass
        return None

    async def _ip_geolocation(self, request, event_emitter) -> str:
        user_ip = self._extract_ip(request)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = "http://ip-api.com/json/"
                is_private = False
                if user_ip:
                    try:
                        is_private = ipaddress.ip_address(user_ip).is_private
                    except ValueError:
                        is_private = True
                if user_ip and not is_private:
                    url += user_ip

                response = await client.get(
                    url,
                    params={
                        "fields": "status,message,country,regionName,city,lat,lon,timezone,query"
                    },
                )
                response.raise_for_status()
                data = response.json()

            if data.get("status") != "success":
                if event_emitter:
                    await event_emitter(
                        {
                            "type": "status",
                            "data": {
                                "description": "❌ Could not detect location",
                                "done": True,
                            },
                        }
                    )
                return (
                    "Could not detect the user's location automatically. "
                    "Please ask the user to provide their location (city or area name)."
                )

            city = data.get("city", "Unknown")
            region = data.get("regionName", "")
            country = data.get("country", "")
            lat = data.get("lat")
            lon = data.get("lon")
            location_name = ", ".join(filter(None, [city, region, country]))

            if event_emitter:
                await event_emitter(
                    {
                        "type": "status",
                        "data": {
                            "description": f"📍 Location: {city}, {region} (approximate)",
                            "done": True,
                        },
                    }
                )

            return (
                f"User's approximate location (IP-based): {location_name}\n"
                f"Coordinates: latitude={lat}, longitude={lon}\n"
                f"Use these coordinates when calling search_places or explore_area. "
                f"Pass latitude={lat} and longitude={lon} as parameters to get nearby results."
            )

        except Exception as e:
            if event_emitter:
                await event_emitter(
                    {
                        "type": "status",
                        "data": {"description": f"Error: {e}", "done": True},
                    }
                )
            return (
                f"Could not detect location: {str(e)}. "
                "Please ask the user to provide their location (city or area name)."
            )

    def _extract_ip(self, request) -> Optional[str]:
        if not request:
            return None
        try:
            if hasattr(request, "headers"):
                forwarded = request.headers.get("x-forwarded-for")
                if forwarded:
                    return forwarded.split(",")[0].strip()
                real_ip = request.headers.get("x-real-ip")
                if real_ip:
                    return real_ip
            if hasattr(request, "client") and request.client:
                return request.client.host
        except Exception:
            pass
        return None

    async def _reverse_geocode(self, lat: float, lng: float) -> str:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self.valves.backend_url}/maps/reverse-geocode",
                    params={"lat": lat, "lng": lng},
                    headers={"X-API-Key": self.valves.backend_api_key},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("formatted_address"):
                        return data["formatted_address"]
        except Exception:
            pass
        return f"{lat}, {lng}"
