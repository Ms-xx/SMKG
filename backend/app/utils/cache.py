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
from typing import Any, Awaitable, Callable

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis = None
_ready: bool | None = None
_lock = asyncio.Lock()

# 单飞注册表：缓存键 → 在飞 Future；并发请求共享同一结果
_inflight: dict[str, asyncio.Future] = {}


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


async def async_single_flight_cache(
    key: str,
    ttl: int,
    producer: Callable[[], Awaitable[Any]],
    empty_ttl: int | None = None,
    is_empty: Callable[[Any], bool] | None = None,
) -> Any:
    """单飞 + Redis 命中回填 + 空结果短 TTL / 不缓存 + 静默降级。

    与既有 async_cache 的差异：
    - 并发未命中同 key 请求共享同一 Future（单飞合并），不重复生产；
    - 空结果按 empty_ttl 写入或跳过写入；
    - 不引入全局串行锁（不同 key 互不阻塞）；
    - Redis 读写/序列化异常 → 捕获 warning 并直连 producer，不抛出。
    """
    if not key or not ttl or ttl <= 0:
        return await producer()

    # 单飞：若同 key 已有在飞 Future，复用
    fut = _inflight.get(key)
    if fut is not None:
        return await fut

    loop = asyncio.get_event_loop()
    fut = loop.create_future()
    _inflight[key] = fut
    try:
        value = await _single_flight_produce(key, ttl, producer, empty_ttl, is_empty)
        if not fut.done():
            fut.set_result(value)
        return value
    except Exception as e:  # noqa: BLE001
        if not fut.done():
            fut.set_exception(e)
        raise
    finally:
        _inflight.pop(key, None)


async def _single_flight_produce(
    key: str,
    ttl: int,
    producer: Callable[[], Awaitable[Any]],
    empty_ttl: int | None,
    is_empty: Callable[[Any], bool] | None,
) -> Any:
    """单飞内部：先读 Redis 命中则返回；未命中则调 producer、回填、返回。"""
    r = _get_redis()
    if r is None:
        return await producer()
    try:
        raw = await r.get(key)
        if raw is not None:
            return json.loads(raw)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"单飞缓存读失败 {key}，直连: {e}")

    value = await producer()

    # 决定回填 TTL：空结果按 empty_ttl（None 则不缓存）
    write_ttl = ttl
    if is_empty is not None and is_empty(value):
        if empty_ttl is None or empty_ttl <= 0:
            return value
        write_ttl = empty_ttl

    try:
        await r.set(key, _dump(value), ex=write_ttl)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"单飞缓存写失败 {key}: {e}")

    return value
