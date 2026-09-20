# -*- coding: utf-8 -*-
"""
Text-to-Cypher 服务（自然语言 → Cypher 查询，GraphQA）

将自然语言问题翻译为只读的 Cypher 查询，用于知识图谱问答（GraphQA）。

依赖策略（可插拔、可降级）：
- 规则模板匹配（零依赖、确定性、永远可用）：覆盖「统计数量 / 列出某类实体 /
  实体间关系 / 关键词检索」等常见意图；
- LLM 后端（`TEXT_TO_CYPHER_BACKEND=llm`）预留：可用大模型做更灵活的翻译，
  未配置或调用失败时自动降级回规则模板；
- 所有生成结果只读（MATCH ... RETURN），内置危险关键词校验，防止写操作注入。
"""
from __future__ import annotations

import re
from typing import Any

from loguru import logger

from app.core.config import settings

# 标签提示词 → Neo4j 节点标签
_LABEL_HINTS: dict[str, str] = {
    "material": "Material",
    "材料": "Material",
    "property": "Property",
    "性能": "Property",
    "性质": "Property",
    "method": "Method",
    "方法": "Method",
    "工艺": "Method",
    "parameter": "Parameter",
    "参数": "Parameter",
    "result": "Result",
    "结果": "Result",
}

# 危险写操作关键词（只读翻译不应出现）
_DANGEROUS_KEYWORDS = [
    "DELETE",
    "DETACH",
    "REMOVE",
    "DROP",
    "CREATE",
    "MERGE",
    "SET ",
    "FOREACH",
    "CALL ",
    "LOAD CSV",
    "UNWIND",
    "APOC",
]

_COUNT_PATTERNS = ["有多少", "统计", "几个", "多少个", "一共有多少", "数量"]
_LIST_PATTERNS = ["列出", "有哪些", "哪些", "所有", "查询", "查找", "搜一下", "搜", "检索"]


def _detect_label(question: str) -> str | None:
    low = question.lower()
    # 优先匹配较长的中文关键词（如「性能」先于「材料」无关，但保守逐项遍历）
    for kw, label in _LABEL_HINTS.items():
        if kw.lower() in low:
            return label
    return None


def _is_count(question: str) -> bool:
    return any(p in question for p in _COUNT_PATTERNS)


def _is_list(question: str) -> bool:
    return any(p in question for p in _LIST_PATTERNS)


def _extract_relation_pair(question: str) -> tuple[str, str] | None:
    """提取「X 和 Y 的关系」类问题中的两个实体短语。"""
    m = re.search(
        r"(.{1,40}?)\s*(?:和|与|跟|以及)\s*(.{1,40}?)\s*(?:之间)?\s*的?\s*(?:关系|关联|联系|连接)",
        question,
    )
    if m:
        a, b = m.group(1).strip(" 的了有"), m.group(2).strip(" 的了有")
        if a and b:
            return a, b
    return None


def _extract_keyword(question: str) -> str:
    """回退意图：从问题中抽取核心关键词（去掉常见疑问/动词前缀）。"""
    for prefix in [
        "列出",
        "有哪些",
        "哪些",
        "所有",
        "查询",
        "查找",
        "搜一下",
        "搜",
        "检索",
        "什么是",
        "什么叫",
    ]:
        question = question.replace(prefix, " ")
    question = re.sub(r"[?？。，,、：:！!]", " ", question)
    tokens = [t for t in re.split(r"\s+", question) if t]
    return tokens[0] if tokens else question


def _validate_read_only(cypher: str) -> tuple[bool, str]:
    upper = cypher.upper()
    for kw in _DANGEROUS_KEYWORDS:
        if kw in upper:
            return False, f"检测到危险关键词，已拒绝：{kw.strip()}"
    if not upper.strip().startswith("MATCH"):
        return False, "仅允许只读的 MATCH ... RETURN 查询"
    if " RETURN" not in upper:
        return False, "查询缺少 RETURN 子句"
    return True, ""


class TextToCypherService:
    """Text-to-Cypher：规则模板翻译（LLM 后端预留，可降级）。"""

    @property
    def available(self) -> bool:
        return settings.TEXT_TO_CYPHER_ENABLED

    def translate(
        self,
        question: str,
        node_labels: list[str] | None = None,
        relation_types: list[str] | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """
        将自然语言问题翻译为只读 Cypher 查询。

        Returns:
            {"question", "cypher", "params", "intent", "backend", "labels", "llm_used"}
        """
        q = (question or "").strip()
        limit = max(1, min(int(limit), 100))
        node_labels = node_labels or []

        base: dict[str, Any] = {
            "question": q,
            "cypher": "",
            "params": {},
            "intent": "unknown",
            "backend": settings.TEXT_TO_CYPHER_BACKEND,
            "labels": list(node_labels),
            "llm_used": False,
        }

        if not q:
            base["intent"] = "empty"
            return base

        # 预留：LLM 后端（未单独接入时统一走规则降级）
        if settings.TEXT_TO_CYPHER_BACKEND == "llm":
            logger.info("TEXT_TO_CYPHER_BACKEND=llm 未接入独立 LLM 通道，回退规则模板")

        label = _detect_label(q)

        # 1) 统计数量
        if _is_count(q):
            if label:
                base["cypher"] = f"MATCH (n:`{label}`) RETURN count(n) AS count"
                base["intent"] = "count_by_label"
            else:
                base["cypher"] = "MATCH (n) RETURN count(n) AS count"
                base["intent"] = "count_all"
            return base

        # 2) 实体间关系
        pair = _extract_relation_pair(q)
        if pair is not None:
            a, b = pair
            base["cypher"] = (
                "MATCH (a)-[r]->(b) "
                "WHERE toLower(toString(a.name)) CONTAINS toLower($a) "
                "AND toLower(toString(b.name)) CONTAINS toLower($b) "
                "RETURN a, type(r) AS relation, b LIMIT $limit"
            )
            base["params"] = {"a": a, "b": b, "limit": limit}
            base["intent"] = "entity_relations"
            return base

        # 3) 列出某类实体
        if label and _is_list(q):
            base["cypher"] = f"MATCH (n:`{label}`) RETURN n LIMIT $limit"
            base["params"] = {"limit": limit}
            base["intent"] = "list_by_label"
            return base

        # 4) 回退：关键词检索
        kw = _extract_keyword(q)
        base["cypher"] = (
            "MATCH (n) WHERE any(key IN keys(n) "
            "WHERE toLower(toString(n[key])) CONTAINS toLower($kw)) "
            "RETURN n LIMIT $limit"
        )
        base["params"] = {"kw": kw, "limit": limit}
        base["intent"] = "keyword_search"
        return base

    def validate(self, cypher: str) -> tuple[bool, str]:
        """只读安全校验。"""
        return _validate_read_only(cypher or "")


# 全局单例
text_to_cypher_service = TextToCypherService()
