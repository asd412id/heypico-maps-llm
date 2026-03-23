from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse
from config import get_settings

settings = get_settings()


def _get_real_ip(request: Request) -> str:
    """Extract real client IP from proxy headers (X-Forwarded-For / X-Real-IP)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    return request.client.host if request.client else "127.0.0.1"


# Limiter instance — uses real client IP behind reverse proxy
limiter = Limiter(key_func=_get_real_ip)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "detail": f"Too many requests. Limit: {exc.detail}",
            "retry_after": "Please wait before making another request.",
        },
        headers={"Retry-After": "60"},
    )
