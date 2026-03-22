import json
import redis.asyncio as aioredis
from typing import Optional, Any
from config import get_settings

settings = get_settings()


class CacheService:
    """
    Redis-based cache with in-memory fallback.
    Reduces Google Maps API calls and improves response time.
    """

    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None
        self._memory: dict = {}  # fallback in-memory cache
        self._connected = False

    async def connect(self):
        try:
            self._redis = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self._redis.ping()
            self._connected = True
            print("[Cache] Connected to Redis")
        except Exception as e:
            print(f"[Cache] Redis unavailable, using in-memory fallback: {e}")
            self._connected = False

    async def get(self, key: str) -> Optional[Any]:
        try:
            if self._connected and self._redis:
                value = await self._redis.get(key)
                if value:
                    return json.loads(value)
            else:
                return self._memory.get(key)
        except Exception:
            return self._memory.get(key)
        return None

    async def set(self, key: str, value: Any, ttl: int = 3600):
        try:
            serialized = json.dumps(value)
            if self._connected and self._redis:
                await self._redis.setex(key, ttl, serialized)
            else:
                self._memory[key] = value  # no TTL for fallback, acceptable for demo
        except Exception as e:
            print(f"[Cache] Set error: {e}")
            self._memory[key] = value

    async def delete(self, key: str):
        try:
            if self._connected and self._redis:
                await self._redis.delete(key)
            else:
                self._memory.pop(key, None)
        except Exception:
            self._memory.pop(key, None)

    async def close(self):
        if self._redis:
            await self._redis.aclose()
