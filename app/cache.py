from __future__ import annotations

import asyncio
import functools
import json
from typing import Any, Callable, Awaitable

import redis.asyncio as redis

from .config import settings


_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis | None:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def cache_get(key: str) -> Any | None:
    client = get_redis()
    if client is None:
        return None
    value = await client.get(key)
    if value is None:
        return None
    return json.loads(value)


async def cache_set(key: str, value: Any, ttl: int = 60) -> None:
    client = get_redis()
    if client is None:
        return
    await client.setex(key, ttl, json.dumps(value))


def cached(ttl: int = 60, key_builder: Callable[..., str] | None = None):
    """Decorator to cache async function results in Redis."""

    def decorator(func: Callable[..., Awaitable[Any]]):
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if key_builder:
                key = key_builder(*args, **kwargs)
            else:
                key = f"{func.__module__}:{func.__name__}:{args}:{kwargs}"
            cached_value = await cache_get(key)
            if cached_value is not None:
                return cached_value
            result = await func(*args, **kwargs)
            await cache_set(key, result, ttl=ttl)
            return result

        return wrapper

    return decorator
