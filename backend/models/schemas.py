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


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
