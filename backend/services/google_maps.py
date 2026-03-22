import httpx
import hashlib
import json
from typing import Optional
from config import get_settings
from services.cache import CacheService

settings = get_settings()

GOOGLE_MAPS_BASE_URL = "https://maps.googleapis.com/maps/api"
GOOGLE_PLACES_NEW_BASE_URL = "https://places.googleapis.com/v1"


class GoogleMapsService:
    """
    Proxy service for Google Maps APIs.
    Handles caching, error handling, and keeps the API key server-side only.
    """

    def __init__(self, cache: CacheService):
        self.cache = cache
        self.api_key = settings.google_maps_api_key
        self.client = httpx.AsyncClient(timeout=15.0)

    def _cache_key(self, prefix: str, **kwargs) -> str:
        payload = json.dumps(kwargs, sort_keys=True)
        h = hashlib.md5(payload.encode()).hexdigest()
        return f"{prefix}:{h}"

    async def search_places(
        self,
        query: str,
        location: Optional[str] = None,
        radius_meters: int = 5000,
        max_results: int = 5,
    ) -> dict:
        cache_key = self._cache_key(
            "places", query=query, location=location, radius=radius_meters
        )
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        # Build request for Places API (New) — Text Search
        body = {
            "textQuery": query if not location else f"{query} near {location}",
            "maxResultCount": min(max_results, 20),
            "languageCode": "en",
        }
        if location:
            # Geocode the location first to get lat/lng for locationBias
            coords = await self.geocode(location)
            if coords:
                body["locationBias"] = {
                    "circle": {
                        "center": {
                            "latitude": coords["lat"],
                            "longitude": coords["lng"],
                        },
                        "radius": float(radius_meters),
                    }
                }

        headers = {
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": (
                "places.id,places.displayName,places.formattedAddress,"
                "places.rating,places.userRatingCount,places.types,"
                "places.priceLevel,places.currentOpeningHours.openNow,"
                "places.photos,places.location,places.googleMapsUri"
            ),
        }

        response = await self.client.post(
            f"{GOOGLE_PLACES_NEW_BASE_URL}/places:searchText",
            json=body,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

        places = []
        for place in data.get("places", []):
            lat = place.get("location", {}).get("latitude", 0)
            lng = place.get("location", {}).get("longitude", 0)

            # Build photo URL if available
            photo_url = None
            if place.get("photos"):
                photo_name = place["photos"][0]["name"]
                photo_url = (
                    f"{GOOGLE_PLACES_NEW_BASE_URL}/{photo_name}/media"
                    f"?maxHeightPx=400&maxWidthPx=400&key={self.api_key}"
                )

            # Convert priceLevel enum to integer
            price_map = {
                "PRICE_LEVEL_FREE": 0,
                "PRICE_LEVEL_INEXPENSIVE": 1,
                "PRICE_LEVEL_MODERATE": 2,
                "PRICE_LEVEL_EXPENSIVE": 3,
                "PRICE_LEVEL_VERY_EXPENSIVE": 4,
            }
            raw_price = place.get("priceLevel", "")
            price_level = price_map.get(raw_price)

            places.append(
                {
                    "name": place.get("displayName", {}).get("text", "Unknown"),
                    "address": place.get("formattedAddress", ""),
                    "rating": place.get("rating"),
                    "user_ratings_total": place.get("userRatingCount"),
                    "place_id": place.get("id", ""),
                    "types": place.get("types", []),
                    "photo_url": photo_url,
                    "price_level": price_level,
                    "open_now": place.get("currentOpeningHours", {}).get("openNow"),
                    "lat": lat,
                    "lng": lng,
                    "maps_url": place.get(
                        "googleMapsUri",
                        f"https://www.google.com/maps/place/?q=place_id:{place.get('id', '')}",
                    ),
                }
            )

        result = {"places": places, "count": len(places)}
        await self.cache.set(cache_key, result, ttl=settings.cache_ttl_places_seconds)
        return result

    async def get_directions(
        self,
        origin: str,
        destination: str,
        travel_mode: str = "driving",
        language: str = "en",
    ) -> dict:
        cache_key = self._cache_key(
            "directions", origin=origin, destination=destination, mode=travel_mode
        )
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        response = await self.client.get(
            f"{GOOGLE_MAPS_BASE_URL}/directions/json",
            params={
                "origin": origin,
                "destination": destination,
                "mode": travel_mode,
                "language": language,
                "key": self.api_key,
            },
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "OK":
            raise ValueError(
                f"Directions API error: {data.get('status')} — {data.get('error_message', '')}"
            )

        route = data["routes"][0]
        leg = route["legs"][0]

        steps = []
        for step in leg.get("steps", []):
            steps.append(
                {
                    "html_instructions": step.get("html_instructions", ""),
                    "distance": step.get("distance", {}).get("text", ""),
                    "duration": step.get("duration", {}).get("text", ""),
                    "travel_mode": step.get("travel_mode", travel_mode).lower(),
                }
            )

        # Build Google Maps URL for the route
        maps_url = (
            f"https://www.google.com/maps/dir/?api=1"
            f"&origin={origin}&destination={destination}&travelmode={travel_mode}"
        )

        # Build embed URL for iframe
        embed_url = (
            f"https://www.google.com/maps/embed/v1/directions"
            f"?key={self.api_key}&origin={origin}&destination={destination}&mode={travel_mode}"
        )

        result = {
            "origin_address": leg.get("start_address", origin),
            "destination_address": leg.get("end_address", destination),
            "total_distance": leg.get("distance", {}).get("text", ""),
            "total_duration": leg.get("duration", {}).get("text", ""),
            "steps": steps,
            "overview_polyline": route.get("overview_polyline", {}).get("points", ""),
            "maps_url": maps_url,
            "embed_url": embed_url,
        }

        await self.cache.set(
            cache_key, result, ttl=settings.cache_ttl_directions_seconds
        )
        return result

    async def geocode(self, address: str) -> Optional[dict]:
        cache_key = self._cache_key("geocode", address=address)
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        response = await self.client.get(
            f"{GOOGLE_MAPS_BASE_URL}/geocode/json",
            params={"address": address, "key": self.api_key},
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "OK" or not data.get("results"):
            return None

        location = data["results"][0]["geometry"]["location"]
        result = {
            "lat": location["lat"],
            "lng": location["lng"],
            "formatted_address": data["results"][0]["formatted_address"],
        }

        await self.cache.set(cache_key, result, ttl=settings.cache_ttl_geocode_seconds)
        return result

    async def close(self):
        await self.client.aclose()
