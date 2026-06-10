import logging
from fastapi import Request
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


def get_redis_client(request: Request) -> Redis:
    redis_client = getattr(request.app.state, "redis_client", None)
    if redis_client is not None:
        return request.app.state.redis_client
    logger.error("Redis client is not initialized in app state")
    raise ValueError("Redis client is not initialized in app state")
