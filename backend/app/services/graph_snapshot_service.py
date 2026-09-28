"""全图快照服务：编排缓存读取 → 单飞 → 参数化抓取 → 归一化 → 回填 → 降级。

知识图谱洞察类接口（/trends、/anomalies）的唯一全图入口。
"""

import asyncio
import time
from typing import Any

from loguru import logger

from app.core.config import settings
from app.services.graph_snapshot import (
    GraphSnapshot,
    is_empty_snapshot,
    normalize_export_payload,
    snapshot_cache_key,
)
from app.services.graphrag_integration import graphrag_integration
from app.utils.cache import async_single_flight_cache, invalidate_cache

# 与既有 _load_full_graph 上限对齐（design.md D-10：不新增截断）
_NODE_LIMIT = 5000
_RELATION_LIMIT = 5000


async def _fetch_and_normalize() -> GraphSnapshot:
    """抓取全图并归一化：aexport_graph 优先，404 时降级 asyncio.gather 并发按类别抓取。"""
    started = time.monotonic()
    try:
        payload = await graphrag_integration.aexport_graph(
            node_limit=_NODE_LIMIT, relation_limit=_RELATION_LIMIT
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"aexport_graph 异常，尝试降级按类别抓取: {e}")
        payload = {"error": "export endpoint unavailable"}

    if isinstance(payload, dict) and payload.get("error") == "export endpoint unavailable":
        snapshot = await _fetch_and_normalize_fallback()
    else:
        snapshot = normalize_export_payload(payload)

    elapsed = time.monotonic() - started
    logger.info(
        f"全图快照抓取完成: nodes={len(snapshot.nodes)} relations={len(snapshot.relations)} "
        f"elapsed={elapsed:.3f}s"
    )
    return snapshot


async def _fetch_and_normalize_fallback() -> GraphSnapshot:
    """兜底：asyncio.gather 并发按类别抓取（兼容未升级 /graph/export 的 :8001）。"""
    stats = await graphrag_integration.agraph_stats()
    if not isinstance(stats, dict) or "error" in stats:
        return GraphSnapshot(nodes=[], relations=[])

    labels = list((stats.get("node_labels") or {}).keys())
    rel_types = list((stats.get("relation_types") or {}).keys())

    all_results = await asyncio.gather(
        *[graphrag_integration.aget_nodes_by_label(lab, _NODE_LIMIT) for lab in labels],
        *[graphrag_integration.aget_relations_by_type(rt, _RELATION_LIMIT) for rt in rel_types],
        return_exceptions=True,
    )
    node_results = all_results[: len(labels)]
    rel_results = all_results[len(labels) :]

    nodes: list[dict[str, Any]] = []
    for lab, resp in zip(labels, node_results, strict=False):
        if isinstance(resp, dict) and "error" not in resp:
            for nd in resp.get("nodes") or []:
                props = nd.get("properties") or {}
                node_id = props.get("id") or nd.get("id")
                nodes.append(
                    {
                        "id": node_id,
                        "label": nd.get("label") or lab,
                        "properties": props,
                    }
                )

    relations: list[dict[str, Any]] = []
    for rt, resp in zip(rel_types, rel_results, strict=False):
        if isinstance(resp, dict) and "error" not in resp:
            for rel in resp.get("relations") or []:
                source = rel.get("source") or {}
                target = rel.get("target") or {}
                relations.append(
                    {
                        "source": (source.get("id") if isinstance(source, dict) else source),
                        "target": (target.get("id") if isinstance(target, dict) else target),
                        "type": rel.get("relation") or rel.get("type") or rt,
                    }
                )

    return GraphSnapshot(nodes=nodes, relations=relations)


async def get_full_graph_snapshot() -> GraphSnapshot:
    """获取全图快照：缓存优先 → 单飞合并 → 抓取 → 归一化 → 回填。"""
    key = snapshot_cache_key()
    snapshot = await async_single_flight_cache(
        key,
        ttl=settings.GRAPH_SNAPSHOT_CACHE_TTL,
        producer=_fetch_and_normalize,
        empty_ttl=settings.GRAPH_SNAPSHOT_EMPTY_TTL,
        is_empty=is_empty_snapshot,
    )
    if isinstance(snapshot, GraphSnapshot):
        return snapshot
    if isinstance(snapshot, dict):
        return GraphSnapshot(
            nodes=snapshot.get("nodes") or [], relations=snapshot.get("relations") or []
        )
    if isinstance(snapshot, list) and len(snapshot) == 2:
        return GraphSnapshot(nodes=snapshot[0] or [], relations=snapshot[1] or [])
    return GraphSnapshot(nodes=[], relations=[])


async def invalidate_graph_snapshot() -> None:
    """失效全图快照缓存（图谱写入后调用）。"""
    await invalidate_cache(prefix="", keys=[snapshot_cache_key()])
