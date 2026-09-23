# -*- coding: utf-8 -*-
"""
系统性能探测服务（步骤 11）：对 MySQL / Redis / Neo4j 做轻量延迟基线探测。

依赖策略（可插拔、可降级）：
- 每个后端独立 `wait_for` 短超时探测，任一服务不可达时优雅返回 `available=False`；
- DB 用 `SELECT 1` 探测；Redis 用 `PING`；Neo4j 用 `verify_connectivity`；
- 真实压测（并发/吞吐/慢查询分析）不在本服务范围内，属于需真实运行环境的运维项。
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

_TIMEOUT = 1.5  # 单个后端探测超时（秒）


def _latency_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)


async def _check_db(db: AsyncSession) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=_TIMEOUT)
        return {"available": True, "latency_ms": _latency_ms(start)}
    except Exception as exc:  # pragma: no cover - 依赖服务不可达
        return {"available": False, "latency_ms": None, "error": str(exc)[:120]}


async def _check_redis() -> dict[str, Any]:
    start = time.perf_counter()
    try:
        from app.utils.redis_client import get_redis_client

        client = await get_redis_client()
        await asyncio.wait_for(client.ping(), timeout=_TIMEOUT)
        return {"available": True, "latency_ms": _latency_ms(start)}
    except Exception as exc:  # pragma: no cover - Redis 不可达
        return {"available": False, "latency_ms": None, "error": str(exc)[:120]}


async def _check_neo4j() -> dict[str, Any]:
    start = time.perf_counter()
    try:
        from app.utils.neo4j_client import Neo4jClient

        client = Neo4jClient()
        await asyncio.wait_for(client.verify_connectivity(), timeout=_TIMEOUT)
        return {"available": True, "latency_ms": _latency_ms(start)}
    except Exception as exc:  # pragma: no cover - Neo4j 不可达
        return {"available": False, "latency_ms": None, "error": str(exc)[:120]}


class PerformanceService:
    """系统性能基线探测门面。"""

    @property
    def available(self) -> bool:
        return settings.PERFORMANCE_CHECK_ENABLED

    async def check(self, db: AsyncSession) -> dict[str, Any]:
        """探测各后端延迟，返回 {db, redis, neo4j, summary}。"""
        db_result = await _check_db(db)
        redis_result = await _check_redis()
        neo4j_result = await _check_neo4j()

        available = [
            r["latency_ms"]
            for r in (db_result, redis_result, neo4j_result)
            if r.get("available") and r.get("latency_ms") is not None
        ]
        summary = {
            "checked": 3,
            "available": len(
                [r for r in (db_result, redis_result, neo4j_result) if r.get("available")]
            ),
            "max_latency_ms": max(available) if available else None,
        }
        logger.info("性能探测完成：%s", summary)
        return {
            "db": db_result,
            "redis": redis_result,
            "neo4j": neo4j_result,
            "summary": summary,
        }


# 全局单例（懒加载，构造时不探测）
performance_service = PerformanceService()
