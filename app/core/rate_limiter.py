import time
import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, status, Request
from app.core.config import settings
from app.core.auth import get_tenant_from_api_key


redis_client = aioredis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=0,
    decode_responses=True
)


async def sliding_window_rate_limit(
    tenant_id: str,
    action: str,
    max_requests: int,
    window_seconds: int,
):
    """
    Sliding window rate limiting algorithm using Redis sorted sets (ZSET).
    Tracks timestamps of each request in a window.
    """

    key = f"rate_limit:{tenant_id}:{action}"
    current_time = int(time.time())
    window_start = current_time - window_seconds

    pipe = redis_client.pipeline()
    pipe.zremrangebyscore(key, 0, window_start)  # Remove outdated requests
    pipe.zadd(key, {str(current_time): current_time})  # Add current request
    pipe.zcard(key)  # Count requests in window
    pipe.expire(key, window_seconds + 10)  # Set key expiry
    _, _, current_count, _ = await pipe.execute()

    if current_count > max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded for {action}. Try again later."
        )


def rate_limit_dependency(
    action: str,
    max_requests: int,
    window_seconds: int
):
    async def dependency(
        request: Request,
        tenant=Depends(get_tenant_from_api_key)
    ):
        tenant_id = tenant.id if hasattr(tenant, "id") else str(tenant)
        await sliding_window_rate_limit(tenant_id, action, max_requests, window_seconds)

    return dependency