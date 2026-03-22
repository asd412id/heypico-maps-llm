from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse
from config import get_settings

settings = get_settings()

# Limiter instance — uses client IP as key
limiter = Limiter(key_func=get_remote_address)


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
