# -*- coding: utf-8 -*-
"""
Future Work 前沿探索服务（步骤 22【P0】模块五）

职责：
提取多篇论文的 Future Work，结合「时间线 + 后续论文进展」自动排除已被后续工作
解决的旧 idea，只保留真正有价值的探索方向；判定必须可回溯到原文片段与文档 id
（不接受只给结论）。

依赖策略（可插拔、可降级）：
- `extract_future_work` / `judge_resolved` / `scan_future_work` 均为纯 Python
  确定性函数，零第三方依赖，永远可复现；
- LLM 仅作可选的措辞润色（不参与判定），未配置时降级纯规则。

判定信号（可解释优先）：
- idea 的提出年份（文档 year）；
- 该 idea 被「已解决」＝存在**年份更晚**的后续论文，其摘要/结论正文命中该 idea
  关键词，并伴随 "we solve/address/overcome/improve" 等表述，且被判为存在
  CITES 边或共享主题；
- 无 `year` / 无 CITES 边 / 无后续论文 → 降级标记低置信度不予定论。
"""
from __future__ import annotations

import re
from typing import Any

from app.core.config import settings

# future work 引出语（中英文）。命中即视为一个候选 idea 的起点
_FUTURE_WORK_RE = re.compile(
    r"(?:future\s+work|future\s+research|future\s+direction|as\s+future\s+steps?"
    r"|we\s+(?:also\s+)?(?:plan|leave|intend|expect|hope|seek|aim)\s+(?:to)?"
    r"|remains?\s+(?:an\s+)?(?:open|a\s+crucial|a\s+key)\s+(?:problem|question|challenge)"
    r"|下一步|未来工作|展望|有待|将来)\s*[：:\-—]?\s*",
    re.IGNORECASE,
)

# “已解决”信号词：出现即提高判定权重
_SOLVE_WORDS = [
    "we solve",
    "we address",
    "we overcome",
    "we improve",
    "we introduce",
    "we propose",
    "we present",
    "we tackle",
    "we resolve",
    "solved by",
    "addressed by",
    "overcome",
    "我们解决",
    "我们提出",
    "解决了",
    "已解决",
]

# 抽取的 idea 片段长度
_IDEA_CHARS = 220


def _fold_ws(text: str) -> str:
    return " ".join(str(text).split())


def _year_of(doc: dict[str, Any]) -> int | None:
    y = doc.get("year")
    try:
        return int(y)
    except (TypeError, ValueError):
        return None


def _doc_id_of(doc: dict[str, Any]) -> str:
    return str(doc.get("document_id") or doc.get("id") or "")


def _doc_text(doc: dict[str, Any]) -> str:
    if isinstance(doc, dict):
        direct = doc.get("text")
        if direct:
            return _fold_ws(str(direct))
        pages = doc.get("pages") or []
        if isinstance(pages, list) and pages and isinstance(pages[0], dict):
            return _fold_ws(
                "\n".join(p.get("text") or "" for p in pages if isinstance(p, dict))
            )
        if isinstance(pages, str):
            return _fold_ws(pages)
        return _fold_ws(" ".join(str(p) for p in pages))
    return _fold_ws(str(doc))


def extract_future_work(chunks: list[str]) -> list[dict[str, Any]]:
    """从 chunk 文本中抽取 future work idea。

    chunks: list[str]。返回 [{keyword, idea, snippet}]，其中 snippet 为含出处的原文片段。
    无 future work 语段 → 返回空列表。
    """
    results: list[dict[str, Any]] = []
    for raw in chunks or []:
        text = str(raw)
        # 按先后顺序取 matches，跳过嵌套在已抽取 idea 区域内的后续触发（避免同句重复）
        consumed_until = 0
        for m in _FUTURE_WORK_RE.finditer(text):
            if m.start() < consumed_until:
                continue
            tail = text[m.end() :].strip()
            stop = _first_stop(tail)
            idea = _fold_ws(tail[:stop])[:_IDEA_CHARS]
            if not idea:
                continue
            start = max(0, m.start() - 60)
            snippet = _fold_ws(text[start : m.end() + min(160, len(tail))])
            results.append(
                {
                    "keyword": m.group(0).strip()[:40],
                    "idea": idea,
                    "snippet": snippet,
                }
            )
            consumed_until = m.end() + stop
    return results


def _first_stop(text: str) -> int:
    stops = [(text.find(s), len(s)) for s in (". ", "。", "\n", ". 我们", ". This")]
    valid = [i for i, _ in stops if i >= 0]
    if not valid:
        return len(text)
    return min(valid) + 6


def judge_resolved(
    idea: dict[str, Any], later_papers: list[dict[str, Any]]
) -> dict[str, Any]:
    """判定 idea 是否已被后续论文解决。

    idea: {idea, keyword, snippet}
    later_papers: 后续论文列表（year 更晚 / 或调用方已过滤），每项形如
        {document_id, title, year, text, has_cites_edge: bool}

    判定：存在后续论文命中 idea 关键词 + 解决信号词，即 resolved。CITES 边/共享主题
    用于加权；无 year / 无 CITES 边且检不到后文 → 低置信度降级。
    """
    idea_text = (idea.get("idea") or "").lower()
    kws = _idea_keywords(idea_text)
    hits: list[dict[str, Any]] = []
    resolved = False
    confidence_base = 0.5  # 无年份/无边时为低置信度，0.5 及以下
    canonical_edge = False

    for p in later_papers or []:
        has_noted_year = _year_of(p) is not None
        text = _doc_text(p).lower()
        kw_hit = any(kw and kw in text for kw in kws)
        can_hit = any(w in text for w in _SOLVE_WORDS)
        edge = bool(p.get("has_cites_edge"))
        if edge:
            canonical_edge = True
        if kw_hit and can_hit:
            resolved = True
            hits.append(
                {
                    "document_id": _doc_id_of(p),
                    "title": p.get("title"),
                    "year": _year_of(p),
                    "note": f"后文命中关键词与解决表述（CITES边={edge}）",
                }
            )
            if has_noted_year and edge:
                confidence_base = 0.95
            elif has_noted_year:
                confidence_base = max(confidence_base, 0.85)
    # 无年/无边为低置信度
    if not later_papers or all(_year_of(p) is None for p in later_papers):
        if not hits:
            confidence_base = min(confidence_base, 0.3)
        else:
            confidence_base = min(confidence_base, 0.5)
    if not canonical_edge and hits:
        confidence_base = min(max(confidence_base, 0.4), 0.75)

    return {
        "resolved": resolved,
        "confidence": round(confidence_base, 2),
        "resolved_by": hits,
        "keywords": kws[:5],
        "reason": (
            "被后续论文解决（命中关键词+解决表述）"
            if resolved
            else "未发现后续论文解决该 idea"
        ),
    }


def _idea_keywords(idea_text: str) -> list[str]:
    """从 idea 抽取关键词：取非停用词 token 前几个（长度≥4 的拉丁词元）。"""
    toks = [
        t
        for t in re.findall(r"[A-Za-z][A-Za-z0-9\-]{3,}", idea_text)
        if t.lower()
        not in {
            "that",
            "this",
            "these",
            "those",
            "with",
            "from",
            "into",
            "more",
            "most",
            "than",
            "then",
            "them",
            "they",
            "there",
            "their",
            "much",
            "many",
            "also",
            "even",
            "work",
        }
    ]
    seen: list[str] = []
    for t in toks:
        if t.lower() not in [s.lower() for s in seen]:
            seen.append(t)
    return seen[:5] or [idea_text[:20]]


def _time_window(documents: list[dict[str, Any]]) -> dict[str, Any]:
    """复用步骤12时间桶能力：按年份频率分桶（年份 → 篇数）。"""
    bins: dict[int, int] = {}
    for d in documents or []:
        y = _year_of(d)
        if y is not None:
            bins[y] = bins.get(y, 0) + 1
    return {"time_buckets": [{"year": k, "count": v} for k, v in sorted(bins.items())]}


def scan_future_work(documents: list[dict[str, Any]]) -> dict[str, Any]:
    """对语料库扫描全部 Future Work，并结合时间线+后文判定“已被解决”。

    documents: [{document_id, title, year, pages:[{text,page_number}] 或 str, references, authors}]
    返回：
      backend: "builtin"
      time_buckets: 年份时间桶（复用步骤12）
      ideas: [{document_id, title, year, keyword, idea, snippet, resolved, confidence, resolved_by, reason}]
    """
    ideas: list[dict[str, Any]] = []
    for doc in documents or []:
        doc_id = _doc_id_of(doc)
        idea_year = _year_of(doc)
        text = _doc_text(doc)
        chunks = [text] if text else []
        for fw in extract_future_work(chunks):
            later = []
            for other in documents or []:
                if other is doc:
                    continue
                oy = _year_of(other)
                # 后续论文：年份更晚；无年份的语料仍纳入以便降级判定
                if oy is not None and idea_year is not None and oy <= idea_year:
                    continue
                has_edge = _has_cites_edge(doc, other)
                later.append(
                    {
                        "document_id": _doc_id_of(other),
                        "title": other.get("title"),
                        "year": oy,
                        "text": _doc_text(other),
                        "has_cites_edge": has_edge,
                    }
                )
            judgement = judge_resolved(fw, later)
            ideas.append(
                {
                    "document_id": doc_id,
                    "title": doc.get("title"),
                    "year": idea_year,
                    "keyword": fw.get("keyword"),
                    "idea": fw.get("idea"),
                    "snippet": fw.get("snippet"),
                    "resolved": judgement["resolved"],
                    "confidence": judgement["confidence"],
                    "resolved_by": [r["document_id"] for r in judgement["resolved_by"]],
                    "evidence": [
                        {
                            "document_id": r["document_id"],
                            "title": r["title"],
                            "year": r["year"],
                        }
                        for r in judgement["resolved_by"]
                    ],
                    "reason": judgement["reason"],
                }
            )
    # 已解决进入排除组，待探索保留
    excluded = [i for i in ideas if i["resolved"]]
    candidates = [i for i in ideas if not i["resolved"]]
    timeline = _time_window(documents)
    return {
        "backend": "builtin",
        "idea_count": len(ideas),
        "excluded_count": len(excluded),
        "candidate_count": len(candidates),
        "time_buckets": timeline["time_buckets"],
        "excluded": excluded,
        "candidates": candidates,
    }


def _has_cites_edge(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """启发式：a 与 b 是否有 CITES 边（共享作者 或 a 的 references 命中 b）。

    无元数据时返回 False（触发低置信度降级），不据此编造。
    """
    a_refs = a.get("references") or []
    b_title = (b.get("title") or "").strip().lower()
    for r in a_refs:
        t = (r.get("title") or "").strip().lower()
        if t and b_title and (t == b_title or t in b_title or b_title in t):
            return True
        if (
            r.get("doi")
            and b.get("doi")
            and str(r.get("doi")).strip().lower() == str(b.get("doi")).strip().lower()
        ):
            return True
    a_auth = set(a.get("authors") or [])
    b_auth = set(b.get("authors") or [])
    if a_auth and b_auth and a_auth & b_auth:
        return True
    return False


class FutureWorkService:
    @property
    def available(self) -> bool:
        return settings.CITATION_GRAPH_ENABLED

    def extract(self, chunks: list[str]) -> list[dict[str, Any]]:
        return extract_future_work(chunks)

    def judge(
        self, idea: dict[str, Any], later: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return judge_resolved(idea, later)

    def scan(self, documents: list[dict[str, Any]]) -> dict[str, Any]:
        return scan_future_work(documents)


# 全局单例
future_work_service = FutureWorkService()
