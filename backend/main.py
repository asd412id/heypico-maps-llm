from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from slowapi.errors import RateLimitExceeded

from config import get_settings
from services.cache import CacheService
from services.google_maps import GoogleMapsService
from middleware.rate_limiter import limiter, rate_limit_exceeded_handler
from routers import maps as maps_router
from routers import health as health_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    cache = CacheService()
    await cache.connect()
    app.state.cache = cache
    app.state.maps_service = GoogleMapsService(cache)
    print("[Startup] Google Maps service initialized")
    yield
    # Shutdown
    await app.state.maps_service.close()
    await app.state.cache.close()
    print("[Shutdown] Cleanup complete")


app = FastAPI(
    title="HeyPico Maps Backend",
    description=(
        "Secure proxy for Google Maps APIs. "
        "Keeps the API key server-side, provides rate limiting and caching. "
        "Used by Open WebUI LLM Tools to deliver interactive maps in chat."
    ),
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,  # Disable Swagger in production
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# ── Rate Limiter ──────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# ── CORS ───────────────────────────────────────────────────────────────────────
# Restrict origins to only Open WebUI and local dev
# In production: replace "*" with your actual domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)


# ── Global Exception Handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.debug else "An unexpected error occurred",
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"error": str(exc)})


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health_router.router)
app.include_router(maps_router.router)
