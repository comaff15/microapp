import json

import redis.asyncio as redis

from app.core.config import settings

redis_client = redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)


async def cache_set(key: str, value: dict, ttl_seconds: int = 30) -> None:
    try:
        await redis_client.set(key, json.dumps(value), ex=ttl_seconds)
    except Exception:
        return


async def cache_get(key: str) -> dict | None:
    try:
        raw = await redis_client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        return None


async def cache_delete(key: str) -> None:
    try:
        await redis_client.delete(key)
    except Exception:
        return
