# -*- coding: utf-8 -*-
"""
知识图谱高级能力 - 趋势分析服务（P2）

按时间桶（year / created_at 前 4 位 / unknown）聚合实体与关系计数，
输出时间线、热点实体/关系及覆盖率统计，供前端折线图展示。

依赖策略（可插拔、可降级）：纯 Python 零第三方依赖，永远可用。
"""
from __future__ import annotations

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


def _empty_period() -> dict[str, Any]:
    return {"entity_counts": {}, "relation_counts": {}}


class TrendAnalysisService:
    @property
    def available(self) -> bool:
        return settings.TREND_ANALYSIS_ENABLED

    def analyze(
        self,
        nodes: list[dict[str, Any]],
        relations: list[dict[str, Any]],
        by: str = "year",
    ) -> dict[str, Any]:
        """按时间桶聚合实体/关系计数并输出热点与覆盖率。"""
        by_id = {n.get("id"): n for n in nodes or []}

        periods: dict[str, dict[str, Any]] = {}
        for nd in nodes or []:
            bucket = _bucket_key(nd)
            if bucket not in periods:
                periods[bucket] = _empty_period()
            label = nd.get("label") or "unknown"
            counts = periods[bucket]["entity_counts"]
            counts[label] = counts.get(label, 0) + 1

        for rel in relations or []:
            src = by_id.get(rel.get("source"))
            bucket = _bucket_key(src) if src else "unknown"
            if bucket not in periods:
                periods[bucket] = _empty_period()
            rtype = rel.get("type") or "unknown"
            counts = periods[bucket]["relation_counts"]
            counts[rtype] = counts.get(rtype, 0) + 1

        timeline = [{"period": p, **periods[p]} for p in sorted(periods)]

        # 热点实体：跨期总计数 + 出现期数（total_periods），按 total 降序
        entity_total: dict[str, int] = {}
        entity_periods: dict[str, int] = {}
        for data in periods.values():
            for label, cnt in data["entity_counts"].items():
                entity_total[label] = entity_total.get(label, 0) + cnt
                entity_periods[label] = entity_periods.get(label, 0) + (1 if cnt > 0 else 0)
        top_entities = [
            {"label": label, "count": cnt, "total_periods": entity_periods.get(label, 0)}
            for label, cnt in entity_total.items()
        ]
        top_entities.sort(key=lambda x: x["count"], reverse=True)

        # 热点关系：同结构
        rel_total: dict[str, int] = {}
        rel_periods: dict[str, int] = {}
        for data in periods.values():
            for rtype, cnt in data["relation_counts"].items():
                rel_total[rtype] = rel_total.get(rtype, 0) + cnt
                rel_periods[rtype] = rel_periods.get(rtype, 0) + (1 if cnt > 0 else 0)
        top_relations = [
            {"label": rtype, "count": cnt, "total_periods": rel_periods.get(rtype, 0)}
            for rtype, cnt in rel_total.items()
        ]
        top_relations.sort(key=lambda x: x["count"], reverse=True)

        total_nodes = len(nodes or [])
        labeled = sum(1 for nd in nodes or [] if _bucket_key(nd) != "unknown")
        coverage = {
            "total_nodes": total_nodes,
            "labeled": labeled,
            "unlabeled": total_nodes - labeled,
        }

        return {
            "backend": "trend",
            "time_field": by,
            "timeline": timeline,
            "top_entities": top_entities,
            "top_relations": top_relations,
            "coverage": coverage,
        }


# 全局单例
trend_analysis_service = TrendAnalysisService()
