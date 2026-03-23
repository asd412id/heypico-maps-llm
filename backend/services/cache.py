import json
import time
import redis.asyncio as aioredis
from typing import Optional, Any
from config import get_settings

settings = get_settings()

MEMORY_CACHE_MAX_SIZE = 10000


class CacheService:
    """
    Redis-based cache with in-memory fallback.
    Reduces Google Maps API calls and improves response time.
    """

    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None
        self._memory: dict = {}
        self._memory_ttl: dict = {}
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
                exp = self._memory_ttl.get(key, 0)
                if exp and time.time() > exp:
                    self._memory.pop(key, None)
                    self._memory_ttl.pop(key, None)
                    return None
                return self._memory.get(key)
        except Exception as e:
            print(f"[Cache] Get error for {key}: {e}")
            return self._memory.get(key)
        return None

    async def set(self, key: str, value: Any, ttl: int = 3600):
        try:
            serialized = json.dumps(value)
            if self._connected and self._redis:
                await self._redis.setex(key, ttl, serialized)
            else:
                if len(self._memory) >= MEMORY_CACHE_MAX_SIZE:
                    oldest = next(iter(self._memory))
                    self._memory.pop(oldest, None)
                    self._memory_ttl.pop(oldest, None)
                self._memory[key] = value
                self._memory_ttl[key] = time.time() + ttl
        except Exception as e:
            print(f"[Cache] Set error: {e}")
            self._memory[key] = value
            self._memory_ttl[key] = time.time() + ttl

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
