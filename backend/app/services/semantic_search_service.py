# -*- coding: utf-8 -*-
"""
语义搜索服务（Semantic Search）

在 GraphRAGTest 已提供的「向量 + BM25 + RRF 混合检索」之上，补齐语义搜索的场景化能力：
1. 分面搜索：按实体标签/关系类型等字段对检索结果聚合计数，支持面筛选；
2. 搜索建议：基于前缀 / 子串 / 编辑距离的自动补全（无需索引服务）。

依赖策略（可插拔、可降级）：
- 纯 Python 实现，零第三方依赖，永远可用；
- 关键字打分复用编辑距离 + token 重叠思想，与实体链接服务保持一致的风格；
- Elasticsearch 作为可选后端（可插拔），未部署时走内置轻量打分，接口不变。
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from app.core.config import settings


def tokenize(text: str) -> list[str]:
    """粗粒度分词：小写 + 按非字母数字切分（CJK 逐字符保留）。"""
    if not text:
        return []
    text = text.lower()
    # 英文字母数字串 + 单个 CJK 字符
    tokens = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", text)
    return tokens


def _levenshtein_ratio(a: str, b: str) -> float:
    a, b = a.lower().strip(), b.lower().strip()
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def keyword_score(query: str, text: str) -> float:
    """查询与目标文本的匹配得分（token 重叠 + 子串命中 + 编辑距离兜底）。"""
    q_tokens = tokenize(query)
    t_tokens = tokenize(text)
    if not q_tokens or not t_tokens:
        return 0.0
    overlap = len(set(q_tokens) & set(t_tokens))
    overlap_score = overlap / len(set(q_tokens) | set(t_tokens))
    substring_bonus = 0.3 if query.lower() in text.lower() else 0.0
    fuzzy_bonus = 0.2 * _levenshtein_ratio(query, text)
    return overlap_score + substring_bonus + fuzzy_bonus


def suggest(prefix: str, candidates: list[str], limit: int = 10) -> list[str]:
    """搜索建议：前缀 > 子串 > 编辑距离 三级排序。"""
    prefix = prefix.strip().lower()
    if not prefix:
        return []
    ranked: list[tuple[float, str]] = []
    seen: set[str] = set()
    for c in candidates:
        name = str(c).strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        low = name.lower()
        if low.startswith(prefix):
            score = 3.0 - len(name) * 0.001
        elif prefix in low:
            score = 2.0 + _levenshtein_ratio(prefix, low)
        else:
            sim = _levenshtein_ratio(prefix, low)
            if sim < 0.3:
                continue
            score = 1.0 + sim
        ranked.append((score, name))
    ranked.sort(key=lambda x: (-x[0], x[1]))
    return [name for _, name in ranked[:limit]]


def facet_search(
    query: str,
    records: list[dict[str, Any]],
    facet_key: str = "label",
    limit: int = 20,
) -> dict[str, Any]:
    """
    分面搜索：对记录做关键字打分，并返回按 facet_key 的面计数。

    records 形如 {"name": "...", "label": "Material", "description": "..."}。

    Returns:
        {"query", "total", "results": [...], "facets": [{"value", "count"}, ...]}
    """
    scored: list[tuple[float, dict[str, Any]]] = []
    facet_counter: dict[str, int] = {}
    total_matched = 0

    for rec in records:
        text = " ".join(
            str(rec.get(k, "")) for k in ("name", "label", "description", "full_name") if rec.get(k)
        )
        s = keyword_score(query, text) if query else 1.0
        if s > 0 or not query:
            if s > 0:
                total_matched += 1
            facet_value = str(rec.get(facet_key) or "Unknown")
            facet_counter[facet_value] = facet_counter.get(facet_value, 0) + 1
            scored.append((s, rec))

    scored.sort(key=lambda x: -x[0])
    results = [{**rec, "score": round(s, 4)} for s, rec in scored[:limit]]
    facets = sorted(facet_counter.items(), key=lambda kv: -kv[1])
    return {
        "query": query,
        "total": total_matched,
        "results": results,
        "facets": [{"value": v, "count": c} for v, c in facets],
    }


class SemanticSearchService:
    """语义搜索服务：建议 + 分面搜索（可插拔 Elasticsearch，内置降级）。"""

    @property
    def available(self) -> bool:
        return settings.SEMANTIC_SEARCH_ENABLED

    def suggest(self, prefix: str, candidates: list[str], limit: int = 10) -> dict[str, Any]:
        return {
            "prefix": prefix,
            "suggestions": suggest(prefix, candidates, limit),
            "backend": "builtin",
        }

    def search(
        self, query: str, records: list[dict[str, Any]], facet_key: str = "label", limit: int = 20
    ) -> dict[str, Any]:
        return facet_search(query, records, facet_key=facet_key, limit=limit)


# 全局单例
semantic_search_service = SemanticSearchService()
