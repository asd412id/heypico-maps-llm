from pydantic import BaseModel, Field
from typing import Optional, Literal


class PlaceSearchRequest(BaseModel):
    query: str = Field(
        ...,
        description="Search query, e.g. 'pizza near me' or 'coffee shops in Jakarta'",
    )
    location: Optional[str] = Field(
        None, description="Location to search near, e.g. 'Jakarta, Indonesia'"
    )
    latitude: Optional[float] = Field(
        None,
        description="Latitude for coordinate-based search (overrides location text geocoding)",
    )
    longitude: Optional[float] = Field(
        None,
        description="Longitude for coordinate-based search (overrides location text geocoding)",
    )
    radius_meters: int = Field(
        5000, ge=100, le=50000, description="Search radius in meters"
    )
    max_results: int = Field(
        5, ge=1, le=20, description="Maximum number of results to return"
    )


class DirectionsRequest(BaseModel):
    origin: str = Field(..., description="Starting location, e.g. 'Monas, Jakarta'")
    destination: str = Field(..., description="Destination, e.g. 'Sarinah, Jakarta'")
    travel_mode: Literal["driving", "walking", "transit", "bicycling"] = Field(
        "driving", description="Travel mode"
    )
    language: str = Field("en", description="Language for directions steps")


class GeocodeRequest(BaseModel):
    address: str = Field(..., description="Address to geocode")


class ExploreRequest(BaseModel):
    area: str = Field(..., description="Area to explore, e.g. 'SCBD Jakarta'")
    category: Literal[
        "food", "entertainment", "shopping", "coffee", "attractions", "all"
    ] = Field("all", description="Category of places to explore")
    latitude: Optional[float] = Field(
        None,
        description="Latitude for coordinate-based search (overrides area geocoding)",
    )
    longitude: Optional[float] = Field(
        None,
        description="Longitude for coordinate-based search (overrides area geocoding)",
    )
    max_results: int = Field(8, ge=1, le=20)


class PlaceResult(BaseModel):
    name: str
    address: str
    rating: Optional[float]
    user_ratings_total: Optional[int]
    place_id: str
    types: list[str]
    photo_url: Optional[str]
    price_level: Optional[int]
    open_now: Optional[bool]
    lat: float
    lng: float
    maps_url: str


class DirectionStep(BaseModel):
    html_instructions: str
    distance: str
    duration: str
    travel_mode: str


class DirectionsResult(BaseModel):
    origin_address: str
    destination_address: str
    total_distance: str
    total_duration: str
    steps: list[DirectionStep]
    overview_polyline: str
    maps_url: str
    embed_url: str


class CardPlace(BaseModel):
    name: str = ""
    address: str = ""
    rating: Optional[float] = None
    user_ratings_total: Optional[int] = None
    types: list[str] = []
    price_level: Optional[int] = None
    open_now: Optional[bool] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    maps_url: Optional[str] = None


class CardDirectionStep(BaseModel):
    instruction: str
    distance: str
    duration: str


class CardRequest(BaseModel):
    card_type: Literal["places", "directions", "places_map", "directions_map"] = Field(
        ..., description="Type of card"
    )
    title: str = Field("", description="Card title")
    subtitle: Optional[str] = Field(None, description="Card subtitle")
    places: Optional[list[CardPlace]] = Field(None, description="Places data")
    origin: Optional[str] = Field(None, description="Directions origin")
    destination: Optional[str] = Field(None, description="Directions destination")
    distance: Optional[str] = Field(None, description="Total distance")
    duration: Optional[str] = Field(None, description="Total duration")
    travel_mode: Optional[str] = Field(None, description="Travel mode")
    steps: Optional[list[CardDirectionStep]] = Field(
        None, description="Direction steps"
    )
    overview_polyline: Optional[str] = Field(
        None, description="Encoded polyline for directions map"
    )
    origin_lat: Optional[float] = Field(None, description="Origin latitude")
    origin_lng: Optional[float] = Field(None, description="Origin longitude")
    dest_lat: Optional[float] = Field(None, description="Destination latitude")
    dest_lng: Optional[float] = Field(None, description="Destination longitude")
    maps_url: Optional[str] = Field(
        None, description="Google Maps URL for 'Open in Google Maps' button"
    )


class UserLocationRequest(BaseModel):
    user_id: str = Field(default="default", description="User identifier")
    latitude: float = Field(..., description="Latitude coordinate")
    longitude: float = Field(..., description="Longitude coordinate")
    accuracy: Optional[float] = Field(None, description="GPS accuracy in meters")


class GeoResultRequest(BaseModel):
    request_id: str = Field(..., description="Request ID for polling")
    user_id: str = Field(default="default", description="User identifier")
    status: str = Field(
        default="error", description="GPS result status: ok, denied, error"
    )
    latitude: Optional[float] = Field(None, description="Latitude coordinate")
    longitude: Optional[float] = Field(None, description="Longitude coordinate")
    accuracy: Optional[float] = Field(None, description="GPS accuracy in meters")
    error: Optional[str] = Field(None, description="Error message if GPS failed")


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
