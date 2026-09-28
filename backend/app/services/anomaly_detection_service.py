# -*- coding: utf-8 -*-
"""
知识图谱高级能力 - 异常检测服务（P2）

基于无向度分布检测图谱异常：
- isolated：孤立节点（degree == 0）
- high_connectivity：超连通节点（z 值 > 阈值）
- low_connectivity：低连通节点（degree > 0 且 z 值 < -阈值）

并计算整体/分年密度及最大密度突变。纯 Python 零第三方依赖，永远可用。
"""
from __future__ import annotations

from math import sqrt
from typing import Any

from app.core.config import settings


def _bucket_key(node: dict[str, Any]) -> str:
    """时间桶 key：properties.year → properties.created_at 前 4 位 → "unknown"。"""
    props = node.get("properties") or {}
    year = props.get("year")
    if year not in (None, ""):
        return str(year)
    created = props.get("created_at")
    if created not in (None, ""):
        return str(created)[:4]
    return "unknown"


def _density(num_edges: int, num_nodes: int) -> float:
    """无向图密度 = 边数 / (n*(n-1)/2)；节点过少时返回 0 防除零。"""
    if num_nodes >= 2:
        possible = num_nodes * (num_nodes - 1) / 2
        if possible > 0:
            return num_edges / possible
    return 0.0


def _zscore(d: int, mean: float, std: float) -> float:
    """计算 z 值；标准差为 0 时返回 0。"""
    if std == 0:
        return 0.0
    return (d - mean) / std


def _compute_degree_distribution(
    nodes: list[dict[str, Any]], relations: list[dict[str, Any]]
) -> dict[str, int]:
    """计算无向度分布。"""
    deg: dict[str, int] = {nd.get("id"): 0 for nd in nodes}
    for rel in relations:
        src, tgt = rel.get("source"), rel.get("target")
        if src in deg:
            deg[src] += 1
        if tgt in deg:
            deg[tgt] += 1
    return deg


def _classify_anomalies(
    deg: dict[str, int],
    by_id: dict[Any, dict[str, Any]],
    mean: float,
    std: float,
    z_threshold: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """三类异常分类，返回 (isolated, high, low, anomalies)。"""
    isolated: list[dict[str, Any]] = []
    high: list[dict[str, Any]] = []
    low: list[dict[str, Any]] = []
    anomalies: list[dict[str, Any]] = []
    for node_id, d in deg.items():
        label = by_id.get(node_id, {}).get("label")
        if d == 0:
            isolated.append({"id": node_id, "label": label, "degree": d})
            anomalies.append(
                {
                    "kind": "isolated",
                    "severity": "medium",
                    "node_id": node_id,
                    "node_label": label,
                    "message": f"节点 {label or node_id} 为孤立节点（度为 0）",
                }
            )
            continue
        zi = _zscore(d, mean, std)
        if zi > z_threshold:
            high.append({"id": node_id, "label": label, "degree": d, "z": round(zi, 3)})
            anomalies.append(
                {
                    "kind": "high_connectivity",
                    "severity": "high",
                    "node_id": node_id,
                    "node_label": label,
                    "message": (f"节点 {label or node_id} 超连通（度 {d}，z={zi:.2f}）"),
                }
            )
        elif zi < -z_threshold:
            low.append({"id": node_id, "label": label, "degree": d, "z": round(zi, 3)})
            anomalies.append(
                {
                    "kind": "low_connectivity",
                    "severity": "low",
                    "node_id": node_id,
                    "node_label": label,
                    "message": (f"节点 {label or node_id} 低连通（度 {d}，z={zi:.2f}）"),
                }
            )
    return isolated, high, low, anomalies


def _compute_period_density(
    nodes: list[dict[str, Any]], relations: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int]]:
    """计算分年密度，返回 (per_period, bucket_nodes, bucket_edges)。"""
    bucket_nodes: dict[str, int] = {}
    bucket_edges: dict[str, int] = {}
    by_id_index = {nd.get("id"): nd for nd in nodes}
    for nd in nodes:
        b = _bucket_key(nd)
        bucket_nodes[b] = bucket_nodes.get(b, 0) + 1
    for rel in relations:
        src = by_id_index.get(rel.get("source"))
        b = _bucket_key(src) if src else "unknown"
        bucket_edges[b] = bucket_edges.get(b, 0) + 1

    per_period: list[dict[str, Any]] = []
    for b in sorted(bucket_nodes):
        per_period.append(
            {
                "period": b,
                "density": round(_density(bucket_edges.get(b, 0), bucket_nodes[b]), 4),
                "nodes": bucket_nodes[b],
                "edges": bucket_edges.get(b, 0),
            }
        )
    return per_period, bucket_nodes, bucket_edges


def _detect_mutation(bucket_nodes: dict[str, int], bucket_edges: dict[str, int]) -> dict[str, Any]:
    """检测最大密度突变，返回 mutation dict。"""
    gene = sorted(bucket_nodes)
    mutation: dict[str, Any] = {"periods": [], "delta": 0.0}
    if len(gene) > 1:
        best: tuple[float, str, str] | None = None
        for i in range(len(gene) - 1):
            d1 = _density(bucket_edges.get(gene[i], 0), bucket_nodes[gene[i]])
            d2 = _density(bucket_edges.get(gene[i + 1], 0), bucket_nodes[gene[i + 1]])
            delta = abs(d2 - d1)
            if best is None or delta > best[0]:
                best = (delta, gene[i], gene[i + 1])
        if best:
            mutation = {"periods": [best[1], best[2]], "delta": round(best[0], 4)}
    return mutation


class AnomalyDetectionService:
    @property
    def available(self) -> bool:
        return settings.ANOMALY_DETECTION_ENABLED

    def detect(
        self,
        nodes: list[dict[str, Any]],
        relations: list[dict[str, Any]],
        z_threshold: float = 2.0,
    ) -> dict[str, Any]:
        """计算无向度分布并输出异常列表与密度像。"""
        nodes = nodes or []
        relations = relations or []
        n = len(nodes)

        deg = _compute_degree_distribution(nodes, relations)

        mean = sum(deg.values()) / n if n else 0
        std = sqrt(sum((d - mean) ** 2 for d in deg.values()) / n) if n > 1 else 0.0

        by_id = {nd.get("id"): nd for nd in nodes}
        isolated, high, low, anomalies = _classify_anomalies(deg, by_id, mean, std, z_threshold)

        edges = len(relations)
        density = _density(edges, n)

        per_period, bucket_nodes, bucket_edges = _compute_period_density(nodes, relations)
        mutation = _detect_mutation(bucket_nodes, bucket_edges)

        return {
            "backend": "anomaly",
            "z_threshold": z_threshold,
            "isolated": {"count": len(isolated), "nodes": isolated},
            "high_connectivity": {"count": len(high), "nodes": high},
            "low_connectivity": {"count": len(low), "nodes": low},
            "density": {
                "overall": round(density, 4),
                "per_period": per_period,
                "mutation": mutation,
            },
            "anomalies": anomalies,
        }


# 全局单例
anomaly_detection_service = AnomalyDetectionService()
