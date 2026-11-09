"""The only place that creates Redis clients. Use get_cache() as a FastAPI dependency.

Not used by any route yet: the rate-limiting (L3) and idempotency (L4) demos build on it.
Production runs 3 replicas, so any state shared between requests must live in Redis.
"""

from functools import lru_cache

import redis
from fastapi import Depends

from app.settings import Settings, get_settings


@lru_cache(maxsize=4)
def _client(redis_url: str) -> redis.Redis:
    return redis.Redis.from_url(redis_url, decode_responses=True)


def get_cache(settings: Settings = Depends(get_settings)) -> redis.Redis:
    """FastAPI dependency. Tests override it with fakeredis."""
    return _client(settings.redis_url)
