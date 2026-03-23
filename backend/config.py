from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # Google Maps
    google_maps_api_key: str

    # Security
    backend_api_key: str

    # Rate Limiting
    rate_limit_per_minute: int = 60
    rate_limit_per_day: int = 1000

    # Redis / Cache
    redis_url: str = "redis://localhost:6379"
    cache_ttl_places_seconds: int = 3600
    cache_ttl_directions_seconds: int = 1800
    cache_ttl_geocode_seconds: int = 86400
    cache_ttl_user_location_seconds: int = 300  # User GPS location cache (5 minutes)

    # App
    debug: bool = False
    backend_url: str = "http://localhost:8000"

    # CORS
    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,http://open-webui:8080"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
