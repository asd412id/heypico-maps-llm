import httpx
import hashlib
import json
import urllib.parse
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
        h = hashlib.sha256(payload.encode()).hexdigest()[:16]
        return f"{prefix}:{h}"

    async def search_places(
        self,
        query: str,
        location: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        radius_meters: int = 5000,
        max_results: int = 5,
    ) -> dict:
        cache_key = self._cache_key(
            "places",
            query=query,
            location=location,
            lat=latitude,
            lng=longitude,
            radius=radius_meters,
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

        # Use pre-resolved coordinates if provided, otherwise geocode location text
        if latitude is not None and longitude is not None:
            body["locationBias"] = {
                "circle": {
                    "center": {
                        "latitude": latitude,
                        "longitude": longitude,
                    },
                    "radius": float(radius_meters),
                }
            }
        elif location:
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
            photo_resource = None
            if place.get("photos"):
                photo_resource = place["photos"][0]["name"]
                photo_url = f"/api/maps/photo/{place.get('id', '')}/0"
                # Cache photo resource name for the proxy endpoint
                await self.cache.set(
                    f"photo_resource:{place.get('id', '')}:0",
                    photo_resource,
                    ttl=settings.cache_ttl_places_seconds,
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
                    "photo_resource": photo_resource,
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

        if not data.get("routes"):
            raise ValueError("No routes found for the given origin and destination")

        route = data["routes"][0]
        if not route.get("legs"):
            raise ValueError("No route legs found")
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
            f"&origin={urllib.parse.quote(origin)}&destination={urllib.parse.quote(destination)}&travelmode={travel_mode}"
        )

        # Build embed URL via server proxy (keeps API key server-side)
        embed_url = (
            f"/api/maps/embed-map?type=directions"
            f"&origin={urllib.parse.quote(origin)}&destination={urllib.parse.quote(destination)}&mode={travel_mode}"
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
            "origin_lat": leg.get("start_location", {}).get("lat"),
            "origin_lng": leg.get("start_location", {}).get("lng"),
            "dest_lat": leg.get("end_location", {}).get("lat"),
            "dest_lng": leg.get("end_location", {}).get("lng"),
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

    async def reverse_geocode(self, lat: float, lng: float) -> Optional[dict]:
        cache_key = self._cache_key(
            "reverse_geocode", lat=round(lat, 4), lng=round(lng, 4)
        )
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        response = await self.client.get(
            f"{GOOGLE_MAPS_BASE_URL}/geocode/json",
            params={"latlng": f"{lat},{lng}", "key": self.api_key},
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "OK" or not data.get("results"):
            return None

        result = {
            "formatted_address": data["results"][0]["formatted_address"],
        }

        await self.cache.set(cache_key, result, ttl=settings.cache_ttl_geocode_seconds)
        return result

    async def close(self):
        await self.client.aclose()
