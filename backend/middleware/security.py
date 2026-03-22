from fastapi import Request, HTTPException, status
from fastapi.security import APIKeyHeader
from config import get_settings
import re

settings = get_settings()

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(request: Request) -> str:
    """
    Verify the internal API key sent by Open WebUI Tools.
    This prevents unauthorized access to the backend proxy.
    """
    api_key = request.headers.get("X-API-Key")
    if not api_key or api_key != settings.backend_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "API key"},
        )
    return api_key


def sanitize_query(query: str) -> str:
    """
    Sanitize user input before passing to Google Maps API.
    Remove potentially harmful characters.
    """
    # Allow letters, numbers, spaces, common punctuation
    sanitized = re.sub(r"[^\w\s\-,.'()&/+@]", "", query, flags=re.UNICODE)
    return sanitized.strip()[:500]  # cap at 500 chars
