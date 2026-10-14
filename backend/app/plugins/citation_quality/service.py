# -*- coding: utf-8 -*-
"""
引用含金量筛选服务（步骤 20【P1】模块四）

职责：
识别并剔除**应付式引用**（仅在 Related Work 里罗列、无实质承接的引用），保留真正
对本文有支撑作用的引用。对同一文档，输出每条参考文献的含金量分数与信号明细，
可按阈值过滤出"应付式引用"，且给出可解释依据（非黑箱）。

信号设计（可解释优先，纯函数确定性打分，LLM 仅可选增强）：
  ① 位置权重   — Abstract / Intro / Method / Experiments 高，Related Work 罗列低；
  ② 正文出现次数 — 出现次数越多支撑越实；
  ③ 数值/结论表述 — 伴随 "outperforms / follows / improves / achieve" 等结论性动词；
  ④ 共享主题/作者 — 与本文共享主题或作者；
  ⑤ 是否有 CITES 边 — 有对应引用边（步骤16 的 references / Neo4j CITES）。

只做接口层过滤/打标，不删原始数据。
"""
from __future__ import annotations

import re
from typing import Any

from loguru import logger

from app.core.config import settings
from app.core.plugin.base import Plugin

# 引用出现位置权重（页面段标题归一化）
_POSITION_WEIGHTS = {
    "abstract": 0.9,
    "intro": 0.8,
    "introduction": 0.8,
    "method": 0.85,
    "approach": 0.85,
    "experiments": 0.9,
    "results": 0.85,
    "evaluation": 0.85,
    "conclusion": 0.6,
    "related work": 0.25,
    "related_work": 0.25,
    "background": 0.35,
    "preliminaries": 0.4,
    "other": 0.5,
}

# 结论性/数值表述（第③信号）
_CONCLUSION_TERMS = [
    "outperform",
    "outperforms",
    "surpass",
    "improve",
    "improves",
    "follow",
    "follows",
    "achieve",
    "achieves",
    "exceed",
    "exceeds",
    "leverage",
    "based on",
    "inspired by",
    "extends",
    "builds on",
    "优于",
    "超过",
    "改进",
    "采用",
]

# 应付式阈值（≤ 该值标记为 perfunctory）
PERFUNCTORY_THRESHOLD = 0.4
SUPPORTING_THRESHOLD = 0.7

# 段标题识别（定位引用所在位置）
_SECTION_RE = re.compile(
    r"^\s*\d*\.?\s*(abstract|introduction|intro|related\s+work|background|method|"
    r"approach|experiments|experimental\s+setup|results|evaluation|conclusion|"
    r"preliminaries)\b",
    re.IGNORECASE,
)
_NUMERIC_REF_RE = re.compile(r"[\[［【]\s*(\d{1,3}(?:\s*[,，、\-–]\s*\d{1,3})*)\s*[\]］】]")


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _fold_ws(text: str) -> str:
    return " ".join(str(text).split()).lower()


def score_reference(
    ref: dict[str, Any], context: dict[str, Any], has_cites_edge: bool = False
) -> dict[str, Any]:
    """单条参考文献含金量打分（纯函数）。

    ref: {index, title, authors?}
    context: {
        position: str           —— 引用出现位置（abstract/intro/method/experiments/related work/other）
        occurrences: int        —— 在正文出现的次数
        context_text: str       —— 该引用附近的正文片段（用于第③信号）
        shared_topic: bool      —— 与本文共享主题
        shared_author: bool     —— 与本文共享作者
    }
    has_cites_edge: 是否有对应 CITES 边。

    返回 {score(0~1), label(core/supporting/perfunctory), signals:[...], detail}
    """
    position = (context.get("position") or "other").lower()
    pos_w = _POSITION_WEIGHTS.get(position, _POSITION_WEIGHTS["other"])
    pos_level = pos_w / 0.9  # 位置以 abstract=0.9 为满分归一
    occurrences = int(context.get("occurrences") or 0)
    occ_level = _clamp01(occurrences * 0.25)
    text = _fold_ws(context.get("context_text") or "")
    has_conclusion = bool(context.get("numeric")) or any(t in text for t in _CONCLUSION_TERMS)
    shared_topic = bool(context.get("shared_topic"))
    shared_author = bool(context.get("shared_author"))

    # 加权和：weight×level / 总权重，各信号相对重要性不同
    factors = [
        (0.35, pos_level),
        (0.20, occ_level),
        (0.20, 1.0 if has_conclusion else 0.0),
        (0.10, 1.0 if shared_topic else 0.0),
        (0.05, 1.0 if shared_author else 0.0),
        (0.10, 1.0 if has_cites_edge else 0.0),
    ]
    total_w = sum(w for w, _ in factors)
    score = _clamp01(sum(w * lvl for w, lvl in factors) / total_w if total_w else 0.0)
    score = round(score, 3)

    label = (
        "core"
        if score >= SUPPORTING_THRESHOLD
        else ("supporting" if score >= PERFUNCTORY_THRESHOLD else "perfunctory")
    )
    signals = [
        {"signal": "position", "level": round(pos_level, 2), "detail": position},
        {
            "signal": "occurrences",
            "level": occurrences,
            "detail": f"正文出现 {occurrences} 次",
        },
        {
            "signal": "conclusion",
            "hit": has_conclusion,
            "detail": "伴随结论/数值表述" if has_conclusion else "无结论性表述",
        },
        {"signal": "shared_topic", "hit": shared_topic},
        {"signal": "shared_author", "hit": shared_author},
        {"signal": "cites_edge", "hit": has_cites_edge},
    ]
    return {
        "index": ref.get("index"),
        "title": (ref.get("title") or "")[:120],
        "score": score,
        "label": label,
        "signals": signals,
        "position": position,
        "occurrences": occurrences,
    }


def _detect_position(body_text: str, offset: int) -> str:
    """依据段标题把引用 offset 映射到所在节。"""
    head = str(body_text)[: max(0, offset)]
    found: list[tuple[int, str]] = []
    for m in _SECTION_RE.finditer(head):
        if len(m.group(0).strip()) < 40:
            found.append((m.end(), _norm_section(m.group(1))))
    return found[-1][1] if found else "other"


def _norm_section(s: str) -> str:
    s = (s or "").strip().lower()
    if "related" in s:
        return "related_work"
    return s


def _short_key(title: str) -> str:
    """参考文献标题 → 检索键（去掉停用词，尽量精确）。"""
    t = _fold_ws(title)
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    words = [
        w
        for w in t.split()
        if w not in {"the", "a", "an", "of", "and", "for", "on", "in", "to", "with"}
    ]
    return " ".join(words) if words else t


def analyze_document(document: dict[str, Any], cites_edges: dict | None = None) -> dict[str, Any]:
    """对单篇文档的每条参考文献打分（纯函数）。

    document: {document_id, title, authors?, references: [{index,title,authors?}],
               pages: [str] 或 [{text,page_number}]}
    cites_edges: {ref_index(str|int): bool} 或 {title_key: bool}，缺失视为 False。

    返回 {document_id, total, perfunctory_count, supporting_count, core_count,
          refs:[score_reference 输出], thresholds}
    """
    pages = document.get("pages") or []
    if isinstance(pages, list) and pages and isinstance(pages[0], dict):
        body = "\n".join(p.get("text") or "" for p in pages if isinstance(p, dict))
    elif isinstance(pages, str):
        body = pages
    else:
        body = "\n".join(str(p) for p in pages)
    body_low = body.lower()
    doc_title = _fold_ws(document.get("title") or "")
    doc_authors = {a.lower() for a in (document.get("authors") or [])}
    cites_edges = cites_edges or {}

    scored: list[dict[str, Any]] = []
    for ref in document.get("references") or []:
        title = ref.get("title") or ref.get("raw") or ""
        ref_index = ref.get("index")
        title_key = _short_key(title)
        # 出现次数与首现位置：优先用 [n] 数字标记（正文行文真实引用），退化为标题键
        occurrences = 0
        first_off = -1
        if ref_index is not None:
            idx = str(ref_index).strip()
            if idx.isdigit():
                num_re = re.compile(r"\[\s*" + re.escape(idx) + r"\s*\](?![0-9])")
                for mo in num_re.finditer(body):
                    occurrences += 1
                    if first_off < 0:
                        first_off = mo.start()
        if occurrences == 0 and title_key:
            occurrences = body_low.count(title_key)
            first_off = body_low.find(title_key)
        position = _detect_position(body, first_off) if first_off >= 0 else "other"
        # 该引用附近上下文（含结论性表述信号）
        ctx_text = str(body[max(0, first_off - 80) : first_off + 120]) if first_off >= 0 else ""
        ctx_text += ref.get("context_text") or ""
        has_numeric = bool(re.search(r"\d+(?:\.\d+)?%?\s", ctx_text))
        ref_authors = {a.lower() for a in (ref.get("authors") or [])}
        shared_author = bool(ref_authors & doc_authors)
        # 共享主题：参考文献标题关键词与本文标题有重合（启发式）
        shared_topic = _topics_overlap(title_key, _short_key(doc_title))
        # CITES 边
        has_edge = bool(
            cites_edges.get(str(ref_index), cites_edges.get(ref_index, False))
            or cites_edges.get(title_key, False)
        )
        context = {
            "position": position,
            "occurrences": occurrences,
            "context_text": ctx_text,
            "shared_topic": bool(shared_topic),
            "shared_author": bool(shared_author),
            "numeric": has_numeric,
        }
        scored.append(score_reference(ref, context, has_edge))

    total = len(scored)
    return {
        "document_id": document.get("document_id") or document.get("id"),
        "title": document.get("title"),
        "total": total,
        "core_count": sum(1 for s in scored if s["label"] == "core"),
        "supporting_count": sum(1 for s in scored if s["label"] == "supporting"),
        "perfunctory_count": sum(1 for s in scored if s["label"] == "perfunctory"),
        "thresholds": {
            "perfunctory_threshold": PERFUNCTORY_THRESHOLD,
            "supporting_threshold": SUPPORTING_THRESHOLD,
        },
        "refs": scored,
    }


def _topics_overlap(a: str, b: str) -> bool:
    wa, wb = set(a.split()), set(b.split())
    if not wa or not wb:
        return False
    return len(wa & wb) >= 1


def score_documents(document_list: list[dict[str, Any]]) -> dict[str, Any]:
    """批量评分：对多篇文档打分并汇总（纯函数）。"""
    results = [analyze_document(d) for d in document_list or []]
    total_refs = sum(r["total"] for r in results)
    total_perf = sum(r["perfunctory_count"] for r in results)
    total_core = sum(r["core_count"] for r in results)
    perf_refs = [
        {
            "document_id": r["document_id"],
            "title": r.get("title"),
            "refs": [
                {
                    "index": s["index"],
                    "title": s["title"],
                    "score": s["score"],
                    "signals": s["signals"],
                }
                for s in r["refs"]
                if s["label"] == "perfunctory"
            ],
        }
        for r in results
    ]
    return {
        "backend": "builtin",
        "document_count": len(results),
        "total_refs": total_refs,
        "perfunctory_count": total_perf,
        "core_count": total_core,
        "perfunctory_refs": [p for p in perf_refs if p["refs"]],
        "documents": results,
    }


class CitationQualityService:
    # ─── 插件协议 ──────────────────────────────────────────────────────────
    async def on_start(self) -> None:
        logger.info("citation_quality plugin started")

    async def on_stop(self) -> None:
        logger.info("citation_quality plugin stopped")

    def health(self):
        return {"backend": "citation_quality", "available": self.available}

    @property
    def available(self) -> bool:
        return settings.CITATION_GRAPH_ENABLED

    def score(self, ref, context, has_cites_edge=False) -> dict[str, Any]:
        return score_reference(ref, context, has_cites_edge)

    def analyze(self, document, cites_edges=None) -> dict[str, Any]:
        return analyze_document(document, cites_edges)

    def batch(self, documents) -> dict[str, Any]:
        return score_documents(documents)


# 全局单例
citation_quality_service = CitationQualityService()


class CitationQualityPlugin(Plugin):
    """官方插件：citation_quality —— 引用含金量筛选服务（存量迁移自 app/services/citation_quality_service.py）。

    - 配置沿用全局 settings（`CITATION_GRAPH_*` 键）。
    - 纯函数确定性打分，无重型运行时资源；`create()` 返回全新实例供 registry 寻址，
      模块级单例 `citation_quality_service` 供门面再导出。
    - 消费者动态寻址：`registry.get("citation_quality")`。
    """

    name = "citation_quality"
    version = "1.0.0"
    config_prefix = ""
    requires: list[str] = []
    type = "service"
    legacy_module = "app.services.citation_quality_service"

    def create(self, registry, settings) -> CitationQualityService:
        return CitationQualityService()


plugin = CitationQualityPlugin()
