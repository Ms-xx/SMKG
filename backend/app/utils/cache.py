"""
性能优化：Redis 异步缓存工具（对应 XiangMu 10.2）。

用法：
    data = await async_cache(
        "stats:team",
        ttl=60,
        producer=lambda: statistics_service.get_team_dashboard(db),
    )

行为：
- Redis 可用：命中返回缓存 JSON；未命中调用 producer 并回填缓存；
- Redis 不可用/序列化失败：静默降级为直接调用 producer，不抛异常、不影响业务。
"""
import asyncio
import json
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis = None
_ready: bool | None = None
_lock = asyncio.Lock()


def _get_redis():
    global _redis, _ready
    if _ready is False:
        return None
    if _redis is None:
        try:
            import redis.asyncio as redis_async

            _redis = redis_async.from_url(
                settings.REDIS_URL, decode_responses=True, encoding="utf-8"
            )
            _ready = True
        except Exception as e:  # noqa: BLE001
            logger.warning(f"缓存 Redis 不可用，将直连数据库: {e}")
            _ready = False
            _redis = None
            return None
    return _redis


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


async def async_cache(key: str, ttl: int, producer):
    """带降级的数据缓存。key 为空或 ttl<=0 时直接调用 producer。"""
    if not key or not ttl or ttl <= 0:
        return await producer()
    r = _get_redis()
    if r is None:
        return await producer()
    try:
        raw = await r.get(key)
        if raw is not None:
            return json.loads(raw)
        async with _lock:
            value = await producer()
            try:
                await r.set(key, _dump(value), ex=ttl)
            except Exception:  # noqa: BLE001
                pass
            return value
    except Exception as e:  # noqa: BLE001
        logger.warning(f"缓存读失败 {key}，直连: {e}")
        return await producer()


async def invalidate_cache(prefix: str, keys: list[str] | None = None) -> None:
    """删除缓存。传 keys 精确删；传 prefix 则扫描前缀删除（依赖 KEYS，仅用于低量）。"""
    r = _get_redis()
    if r is None:
        return
    try:
        if keys:
            await r.delete(*keys)
        elif prefix:
            for k in await r.keys(f"{prefix}*"):
                await r.delete(k)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"缓存失效失败: {e}")