import logging

import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client = None


async def get_redis_client():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            encoding="utf-8",
        )
    return _redis_client


# 向后兼容：保留 redis_client 名称，但延迟创建
class _LazyRedis:
    """延迟初始化的 Redis 代理"""

    def __getattr__(self, name):
        # 不实际连接，仅在真正使用时抛出友好错误
        raise RuntimeError(
            "Redis client not initialized. Use 'await get_redis_client()' "
            "or check Redis is running on " + settings.REDIS_URL
        )


redis_client = _LazyRedis()
