from fastapi import APIRouter
from fastapi.responses import JSONResponse
import httpx

router = APIRouter()


@router.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for Docker and monitoring."""
    return {"status": "ok", "service": "heypico-maps-backend"}


@router.get("/health/maps", tags=["Health"])
async def maps_health():
    """Check if Google Maps API is reachable (does not consume quota)."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://maps.googleapis.com/maps/api/geocode/json?address=test&key=invalid"
            )
            # Status 200 even for invalid key — means API is reachable
            return {"status": "reachable", "maps_api": resp.status_code in [200, 400]}
    except Exception as e:
        return JSONResponse(
            status_code=503, content={"status": "unreachable", "error": str(e)}
        )
