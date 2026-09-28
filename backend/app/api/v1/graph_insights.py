"""
知识图谱高级能力 — 端到端洞察接口（P2）

API 层负责当前全图数据的抓取（GraphRAGTest 转发），service 保持纯 Python 便于单测。
- GET /trends     → 趋势分析（按时间桶聚合）
- GET /anomalies  → 异常检测（孤立/超连通/低连通）
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.core.permissions import DOCUMENT_READ, require_permission
from app.services.anomaly_detection_service import anomaly_detection_service
from app.services.graph_snapshot_service import get_full_graph_snapshot
from app.services.graphrag_integration import graphrag_integration
from app.services.trend_analysis_service import trend_analysis_service

router = APIRouter()

# 批量拉取单标签/关系的限定上限（节点规模几百，循环可接受）
_NODE_LIMIT = 2000
_RELATION_LIMIT = 5000


def _load_full_graph() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """[legacy/兜底] 抓取 GraphRAGTest 当前全图：按 stats 的标签/关系类型逐一拉取后归一化。

    保留同步实现以降低回滚成本（design.md D-04）；当前路由已切换到
    `graph_snapshot_service.get_full_graph_snapshot()`（异步、缓存、单飞）。
    """
    nodes: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []

    stats = graphrag_integration.graph_stats()
    if "error" in stats or not isinstance(stats, dict):
        return [], []

    for label in (stats.get("node_labels") or {}).keys():
        resp = graphrag_integration.get_nodes_by_label(label, _NODE_LIMIT)
        for nd in resp.get("nodes") or []:
            node_id = (nd.get("properties") or {}).get("id") or nd.get("id")
            nodes.append(
                {
                    "id": node_id,
                    "label": nd.get("label") or label,
                    "properties": nd.get("properties") or {},
                }
            )

    for rel_type in (stats.get("relation_types") or {}).keys():
        resp = graphrag_integration.get_relations_by_type(rel_type, _RELATION_LIMIT)
        for rel in resp.get("relations") or []:
            source = rel.get("source") or {}
            target = rel.get("target") or {}
            relations.append(
                {
                    "source": source.get("id") if isinstance(source, dict) else source,
                    "target": target.get("id") if isinstance(target, dict) else target,
                    "type": rel.get("relation") or rel.get("type") or rel_type,
                }
            )

    return nodes, relations


@router.get("/trends")
async def get_graph_trends(
    current_user: dict = Depends(require_permission(DOCUMENT_READ)),
):
    """当前全图趋势分析。"""
    if not trend_analysis_service.available:
        raise HTTPException(status_code=503, detail="trend analysis disabled")
    snapshot = await get_full_graph_snapshot()
    return trend_analysis_service.analyze(snapshot.nodes, snapshot.relations)


@router.get("/anomalies")
async def get_graph_anomalies(
    current_user: dict = Depends(require_permission(DOCUMENT_READ)),
):
    """当前全图异常检测。"""
    if not anomaly_detection_service.available:
        raise HTTPException(status_code=503, detail="anomaly detection disabled")
    snapshot = await get_full_graph_snapshot()
    return anomaly_detection_service.detect(snapshot.nodes, snapshot.relations)
