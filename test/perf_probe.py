#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
压测配套资源/依赖侧取证（步骤 10.3.3）。

采集：
  - 后端进程 CPU / 内存占用
  - MySQL 连接数与会话概况
  - Redis 命中率（压测缓存效果）
  - MySQL 索引生效性对照（同一查询强制 USE/FORCE INDEX 与忽略索引的 EXPLAIN + 耗时）

用法：python test/perf_probe.py [--out PATH]
输出：outputs/perf/perf_probe.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "backend"))

_THREAD_LOCK = 0.0


def _load_env() -> None:
    from dotenv import load_dotenv

    load_dotenv(_REPO_ROOT / "backend" / ".env", override=False)


def probe_backend_process() -> dict[str, Any]:
    """找到监听 8000 的后端进程并采集 CPU / 内存。"""
    import psutil  # 可选依赖

    for conn in psutil.net_connections(kind="tcp"):
        if (
            conn.laddr
            and conn.laddr.port == 8000
            and conn.status == "LISTEN"
            and conn.pid
        ):
            proc = psutil.Process(conn.pid)
            with proc.oneshot():
                return {
                    "pid": conn.pid,
                    "rss_mb": round(proc.memory_info().rss / 1024 / 1024, 1),
                    "cpu_percent": round(proc.cpu_percent(interval=1.0), 2),
                    "threads": proc.num_threads(),
                    "create_time": datetime.fromtimestamp(
                        proc.create_time()
                    ).isoformat(),
                }
    return {"error": "backend process not found"}


def probe_backend_process_safe() -> dict[str, Any]:
    try:
        return probe_backend_process()
    except ImportError:
        return {"error": "psutil 未安装，跳过进程资源采集"}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


async def probe_mysql() -> dict[str, Any]:
    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.core.config import settings

    engine = create_async_engine(settings.DATABASE_URL)
    out: dict[str, Any] = {}
    async with engine.connect() as conn:
        for var in (
            "Threads_connected",
            "Threads_running",
            "Slow_queries",
            "Questions",
        ):
            res = await conn.execute(sa.text(f"SHOW STATUS LIKE '{var}'"))
            row = res.first()
            if row:
                out[var] = int(row[1])
        res = await conn.execute(
            sa.text(
                "SELECT count(*) FROM information_schema.statistics "
                "WHERE table_schema = DATABASE() AND table_name = 'documents'"
            )
        )
        out["documents_index_count"] = int(res.scalar() or 0)
    await engine.dispose()
    return out


async def probe_mysql_index_effect() -> dict[str, Any]:
    """对比「走索引」与「忽略索引」同一查询的执行计划与耗时。"""
    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.core.config import settings

    engine = create_async_engine(settings.DATABASE_URL)
    result: dict[str, Any] = {}
    async with engine.connect() as conn:
        base = "SELECT id, title FROM documents WHERE status = :st ORDER BY created_at DESC LIMIT 50"

        # 1) 优化器自选（预期走 ix_* 索引 / 主键排序）
        async def timed(sql: str) -> float:
            t0 = time.perf_counter()
            for _ in range(5):
                await conn.execute(sa.text(sql), {"st": "parsed"})
            return round((time.perf_counter() - t0) / 5 * 1000, 2)

        result["with_index_ms"] = await timed(base)
        res = await conn.execute(sa.text("EXPLAIN " + base), {"st": "parsed"})
        result["with_index_plan"] = [dict(r) for r in res.mappings()]

        # 2) 显式忽略全部二级索引（等价于 10.1 加索引之前的扫描行为）
        forced = (
            "SELECT id, title FROM documents IGNORE INDEX (`ix_documents_status`) "
            "WHERE status = :st ORDER BY created_at DESC LIMIT 50"
        )
        res = await conn.execute(sa.text("SHOW INDEX FROM documents"))
        names = sorted({r[2] for r in res})
        result["available_indexes"] = names
        secondary = next(
            (n for n in names if "ix_" in n or n.lower() != "primary"), None
        )
        if secondary:
            result["ignore_index_used"] = secondary
            ignored = f"SELECT id, title FROM documents IGNORE INDEX (`{secondary}`) WHERE status = :st ORDER BY created_at DESC LIMIT 50"
            result["without_index_ms"] = await timed(ignored)
            res = await conn.execute(sa.text("EXPLAIN " + ignored), {"st": "parsed"})
            result["without_index_plan"] = [dict(r) for r in res.mappings()]
        else:
            result["without_index_ms"] = None
    await engine.dispose()
    return result


def probe_redis() -> dict[str, Any]:
    import redis

    from app.core.config import settings

    client = redis.Redis.from_url(settings.REDIS_URL)
    info = client.info("stats")
    hits = int(info.get("keyspace_hits", 0))
    misses = int(info.get("keyspace_misses", 0))
    total = hits + misses
    return {
        "keyspace_hits": hits,
        "keyspace_misses": misses,
        "hit_rate": round(hits / total, 4) if total else None,
        "db_keys": int(client.dbsize()),
    }


async def main_async() -> dict[str, Any]:
    return {
        "mysql": await probe_mysql(),
        "mysql_index_effect": await probe_mysql_index_effect(),
    }


def main(args: argparse.Namespace) -> int:
    _load_env()
    data: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(),
        "backend_process": probe_backend_process_safe(),
        "redis": probe_redis(),
    }
    data.update(asyncio.run(main_async()))

    out_path = (
        Path(args.out)
        if args.out
        else _REPO_ROOT / "outputs" / "perf" / "perf_probe.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="压测配套资源与依赖侧取证")
    p.add_argument("--out", type=str, default=None)
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(main(parse_args()))
