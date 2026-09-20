# -*- coding: utf-8 -*-
"""
实体链接服务（Entity Linking）

将抽取出的实体链接到公开知识图谱（Wikidata / DBpedia），并完成：
1. 实体消歧：在同名/形近候选实体中选择与领域上下文最匹配的一项；
2. 同义词合并：把指向同一规范实体的不同写法（别名、别称、中英文名）归并到同一
   规范节点（canonical id），返回别名集合。

依赖策略（可插拔、可降级）：
- 需要网络访问 Wikidata / DBpedia 公共 API；
- 未启用 / 网络失败 / 无候选时，自动降级为「本地字符串相似度 + 内置领域同义词表」，
  `link_entity` 仍返回规范结果，接口不变；
- 相似度计算为纯函数（可独立测试），不依赖网络。
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

import httpx
from loguru import logger

from app.core.config import settings

# ── 内置材料科学领域同义词表（本地降级 + 领域本体对齐）────────────────
# canonical 为规范名，aliases 为常见同义/别称写法。
# 注意：key 均为 normalize_text() 归一化后的形式（小写、连字符→空格）。
_DOMAIN_SYNONYMS: dict[str, str] = {
    "钙钛矿": "perovskite",
    "钙钛矿结构": "perovskite",
    "perovskite": "perovskite",
    "methylammonium lead iodide": "perovskite",
    "甲基铵铅碘": "perovskite",
    "mapbi3": "perovskite",
    "氧化钛": "titanium dioxide",
    "二氧化钛": "titanium dioxide",
    "titanium dioxide": "titanium dioxide",
    "tio2": "titanium dioxide",
    "spiro ometad": "spiro-ometad",
    "spiro": "spiro-ometad",
}

# 实体类型（内部 label）→ Wikidata 允许的实例/类别关键词（用于消歧打分）
_TYPE_HINTS: dict[str, list[str]] = {
    "Material": ["material", "compound", "chemical", "材料", "化合物"],
    "Property": ["property", "physical property", "性能", "性质"],
    "Method": ["method", "technique", "process", "方法", "技术"],
    "Parameter": ["parameter", "quantity", "参数"],
}

WIKIDATA_SEARCH_URL = "https://www.wikidata.org/w/api.php"
DBPEDIA_LOOKUP_URL = "https://lookup.dbpedia.org/api/search"


def normalize_text(s: str) -> str:
    """统一小写、去首尾空白、压缩内部空白，便于相似度与去重比较。"""
    if not s:
        return ""
    s = s.strip().lower()
    s = re.sub(r"[\s_\-]+", " ", s)
    return s


def levenshtein_ratio(a: str, b: str) -> float:
    """编辑距离相似度（基于 SequenceMatcher，纯 Python，无第三方依赖）。"""
    a, b = normalize_text(a), normalize_text(b)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def jaccard_similarity(a: str, b: str, n: int = 2) -> float:
    """字符 n-gram Jaccard 相似度。"""
    a, b = normalize_text(a), normalize_text(b)
    if not a and not b:
        return 1.0

    def _grams(s: str) -> set[str]:
        return {s[i : i + n] for i in range(max(1, len(s) - n + 1))} or {s}

    ga, gb = _grams(a), _grams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


def string_similarity(name: str, candidate: str) -> float:
    """综合相似度 = 编辑距离 + Jaccard 的加权和。"""
    return 0.6 * levenshtein_ratio(name, candidate) + 0.4 * jaccard_similarity(name, candidate)


class EntityLinkingService:
    """实体链接服务：Wikidata/DBpedia 查询 + 消歧 + 同义词合并，可插拔降级。"""

    def __init__(self):
        self.backend = "none"

    @property
    def available(self) -> bool:
        return settings.ENTITY_LINKING_ENABLED and settings.ENTITY_LINKING_BACKEND != "none"

    def _http(self) -> httpx.Client:
        return httpx.Client(timeout=settings.ENTITY_LINKING_TIMEOUT, follow_redirects=True)

    # ── 外部知识库查询 ─────────────────────────────────────────

    def _query_wikidata(self, text: str, limit: int = 8) -> list[dict[str, Any]]:
        params = {
            "action": "wbsearchentities",
            "search": text,
            "language": settings.ENTITY_LINKING_LANGUAGE,
            "format": "json",
            "limit": limit,
        }
        with self._http() as client:
            resp = client.get(WIKIDATA_SEARCH_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        results = []
        for hit in data.get("search", []):
            results.append(
                {
                    "source": "wikidata",
                    "id": hit.get("id"),
                    "label": hit.get("label"),
                    "description": hit.get("description", ""),
                    "aliases": hit.get("aliases", []) or [],
                }
            )
        return results

    def _query_dbpedia(self, text: str, limit: int = 8) -> list[dict[str, Any]]:
        params = {"query": text, "format": "json", "maxResults": limit}
        headers = {"Accept": "application/json"}
        with self._http() as client:
            resp = client.get(DBPEDIA_LOOKUP_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        results = []
        for hit in data.get("docs", []):
            results.append(
                {
                    "source": "dbpedia",
                    "id": (
                        hit.get("resource", [None])[0]
                        if isinstance(hit.get("resource"), list)
                        else hit.get("resource")
                    ),
                    "label": (
                        hit.get("label", [None])[0]
                        if isinstance(hit.get("label"), list)
                        else hit.get("label")
                    ),
                    "description": (
                        hit.get("comment", "") if isinstance(hit.get("comment"), str) else ""
                    ),
                    "aliases": [],
                }
            )
        return results

    def _query_candidates(self, text: str) -> list[dict[str, Any]]:
        """按 backend 配置查询候选实体；任何异常返回空列表。"""
        candidates: list[dict[str, Any]] = []
        for backend in settings.ENTITY_LINKING_BACKEND.split(","):
            backend = backend.strip()
            try:
                if backend == "wikidata":
                    candidates += self._query_wikidata(text)
                elif backend == "dbpedia":
                    candidates += self._query_dbpedia(text)
            except Exception as e:  # pragma: no cover - 网络/服务不可用
                logger.warning("实体链接后端 %s 查询失败（降级）：%s", backend, e)
        return candidates

    # ── 消歧 ─────────────────────────────────────────────────

    def disambiguate(
        self, name: str, candidates: list[dict[str, Any]], entity_type: str | None = None
    ) -> dict[str, Any] | None:
        """
        从候选实体中选出最佳匹配。

        打分规则：
        - 基础分 = string_similarity(name, label)；
        - 类型提示（entity_type）命中候选 description 时加分；
        - 精确别名命中直接置为高分。
        """
        if not candidates:
            return None

        hints = _TYPE_HINTS.get(entity_type or "", [])
        best, best_score = None, 0.0

        for c in candidates:
            label = c.get("label") or ""
            score = string_similarity(name, label)
            # 别名精确命中
            aliases = c.get("aliases") or []
            if name.lower() in {a.lower() for a in aliases}:
                score = max(score, 0.99)
            # 类型提示命中
            desc = (c.get("description") or "").lower()
            if hints and any(h.lower() in desc for h in hints):
                score += 0.05
            if score > best_score:
                best, best_score = c, score

        if best is None:
            return None
        return {**best, "score": round(best_score, 4)}

    # ── 主入口 ────────────────────────────────────────────────

    def link_entity(self, text: str, entity_type: str | None = None) -> dict[str, Any] | None:
        """
        链接单个实体。返回规范结果或 None。

        返回结构：
        {
            "text": 原实体文本,
            "canonical_id": 规范 id（Wikidata QID / DBpedia URI / 本地 canonical）,
            "canonical_name": 规范名,
            "aliases": [别名...],
            "source": "wikidata" | "dbpedia" | "local",
            "score": 相似度,
            "description": 描述,
        }
        """
        if not text or not text.strip():
            return None

        # 1) 本地领域同义词合并（无需网络，永远可用）
        local_canonical = _DOMAIN_SYNONYMS.get(normalize_text(text))
        if local_canonical:
            return {
                "text": text,
                "canonical_id": f"local:{local_canonical}",
                "canonical_name": local_canonical,
                "aliases": [k for k, v in _DOMAIN_SYNONYMS.items() if v == local_canonical],
                "source": "local",
                "score": 1.0,
                "description": "本地领域本体对齐",
            }

        # 2) 外部知识库查询 + 消歧（可降级）
        if self.available:
            try:
                candidates = self._query_candidates(text)
                best = self.disambiguate(text, candidates, entity_type)
                if best:
                    return {
                        "text": text,
                        "canonical_id": best.get("id"),
                        "canonical_name": best.get("label"),
                        "aliases": best.get("aliases", []),
                        "source": best.get("source"),
                        "score": best.get("score", 0.0),
                        "description": best.get("description", ""),
                    }
            except Exception as e:  # pragma: no cover
                logger.warning("实体链接失败，回退本地：%s", e)

        # 3) 未链接成功：返回未链接标记
        return {
            "text": text,
            "canonical_id": None,
            "canonical_name": normalize_text(text),
            "aliases": [],
            "source": "none",
            "score": 0.0,
            "description": "",
        }

    def link_entities(self, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """批量链接实体，并做同义词合并（同一 canonical_id 归并）。"""
        linked = [
            self.link_entity(e.get("text", ""), e.get("entity_type") or e.get("type"))
            for e in entities
        ]
        linked = [item for item in linked if item is not None]

        # 同义词合并：按 canonical_id 归并，别名单例去重
        merged: dict[str, dict[str, Any]] = {}
        for item in linked:
            key = item["canonical_id"] or f"__none__:{item['text']}"
            if key not in merged:
                merged[key] = item
            else:
                merged[key]["aliases"] = sorted(
                    set(merged[key]["aliases"]) | set(item["aliases"]) | {item["text"]}
                )

        return list(merged.values())


# 全局单例（懒加载，构造时不触发网络）
entity_linking_service = EntityLinkingService()
