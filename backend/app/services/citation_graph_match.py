# -*- coding: utf-8 -*-
"""
引用匹配纯函数（步骤 16.1）。

匹配键优先级：DOI 归一化 → 题名精确 → 题名 token Jaccard ≥ 0.9 模糊 → unmatched。
纯函数、无 I/O、无外部依赖；容错归一化，不抛异常。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Sequence


class MatchType(str, Enum):
    DOI = "doi"
    ARXIV_ID = "arxiv_id"
    TITLE_EXACT = "title_exact"
    TITLE_FUZZY = "title_fuzzy"
    UNMATCHED = "unmatched"


@dataclass(frozen=True)
class MatchResult:
    """不可变匹配结果。"""

    doc_id: str | None
    match_type: MatchType
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "match_type": self.match_type.value,
            "confidence": self.confidence,
        }


_DOI_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
)


def normalize_doi(raw: str | None) -> str | None:
    """归一化 DOI：去 URL 前缀、小写、去空白；空/非法返回 None。"""
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if not s:
        return None
    for prefix in _DOI_PREFIXES:
        if s.startswith(prefix):
            s = s[len(prefix) :]
            break
    s = s.strip()
    if not s:
        return None
    # 合法 DOI 至少含一个斜杠或 10. 前缀
    if "/" not in s and not s.startswith("10."):
        return None
    return s


_ARXIV_MARKED_RE = re.compile(
    r"arxiv[\s:./-]*((?:\d{4}\.\d{4,5})|(?:[a-z-]+(?:\.[a-z]{2})?/\d{7}))(v\d+)?",
    re.IGNORECASE,
)
_ARXIV_BARE_RE = re.compile(r"(?<![\d.])(\d{4}\.\d{4,5})(?!\d)")

# arXiv id 的常见承载字段（按可信度降序）
_REF_ARXIV_FIELDS = ("arxiv_id", "eprint", "raw", "doi", "title", "journal")
_CAND_ARXIV_FIELDS = (
    "arxiv_id",
    "eprint",
    "doi",
    "file_path",
    "file_name",
    "title",
    "id",
)


def normalize_arxiv_id(raw: Any) -> str | None:
    """从文本 / DOI / 文件名中提取规范 arXiv id（小写、去版本号），失败返回 None。

    识别顺序：① 带 arXiv 标记或 DOI 载体（`10.48550/arXiv.1607.06450`）；
    ② 裸号 `NNNN.NNNNN`。None / 空串 / 序列容器均容错返回 None。
    """
    if raw is None:
        return None
    if isinstance(raw, (list, tuple, set)):
        raw = " ".join(str(x) for x in raw)
    text = str(raw).strip()
    if not text:
        return None
    marked = _ARXIV_MARKED_RE.search(text)
    if marked:
        return marked.group(1).lower().rstrip(".")
    bare = _ARXIV_BARE_RE.search(text)
    if bare:
        return bare.group(1)
    return None


def _extract_arxiv_ids(source: Any, fields: Sequence[str]) -> list[str]:
    """按字段优先级去重提取 arXiv id 列表。"""
    if not isinstance(source, dict):
        single = normalize_arxiv_id(source)
        return [single] if single else []
    found: list[str] = []
    for field in fields:
        aid = normalize_arxiv_id(source.get(field))
        if aid and aid not in found:
            found.append(aid)
    return found


def _match_by_arxiv_id(
    reference: dict[str, Any], candidates: Sequence[dict[str, Any]]
) -> MatchResult | None:
    """arXiv id 匹配（第二优先级），返回 MatchResult | None。"""
    ref_ids = set(_extract_arxiv_ids(reference, _REF_ARXIV_FIELDS))
    if not ref_ids:
        return None
    for cand in candidates:
        if ref_ids & set(_extract_arxiv_ids(cand, _CAND_ARXIV_FIELDS)):
            return MatchResult(
                doc_id=_cand_id(cand),
                match_type=MatchType.ARXIV_ID,
                confidence=1.0,
            )
    return None


_TITLE_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_TITLE_WS_RE = re.compile(r"\s+")


def normalize_title(raw: str | None) -> str:
    """归一化题名：小写、去标点、压缩空白；空输入返回空字符串。"""
    if raw is None:
        return ""
    s = str(raw).lower()
    s = _TITLE_PUNCT_RE.sub(" ", s)
    s = _TITLE_WS_RE.sub(" ", s).strip()
    return s


def _token_jaccard(a: str, b: str) -> float:
    """题名 token Jaccard 相似度。"""
    ta = set(a.split())
    tb = set(b.split())
    if not ta or not tb:
        return 0.0
    inter = ta & tb
    union = ta | tb
    return len(inter) / len(union)


_FUZZY_THRESHOLD = 0.9


def _match_by_doi(
    reference: dict[str, Any], candidates: Sequence[dict[str, Any]]
) -> MatchResult | None:
    """DOI 匹配，返回 MatchResult | None。"""
    ref_doi = normalize_doi(reference.get("doi"))
    if not ref_doi:
        return None
    for cand in candidates:
        cand_doi = normalize_doi(cand.get("doi"))
        if cand_doi and cand_doi == ref_doi:
            return MatchResult(
                doc_id=_cand_id(cand),
                match_type=MatchType.DOI,
                confidence=1.0,
            )
    return None


def _match_by_title_exact(
    reference: dict[str, Any], candidates: Sequence[dict[str, Any]]
) -> MatchResult | None:
    """题名精确匹配，返回 MatchResult | None。"""
    ref_title = normalize_title(reference.get("title"))
    if not ref_title:
        return None
    for cand in candidates:
        cand_title = normalize_title(cand.get("title"))
        if cand_title and cand_title == ref_title:
            return MatchResult(
                doc_id=_cand_id(cand),
                match_type=MatchType.TITLE_EXACT,
                confidence=1.0,
            )
    return None


def _match_by_title_fuzzy(
    reference: dict[str, Any], candidates: Sequence[dict[str, Any]]
) -> MatchResult | None:
    """题名模糊匹配（Jaccard ≥ 0.9），返回 MatchResult | None。"""
    ref_title = normalize_title(reference.get("title"))
    if not ref_title:
        return None
    best_cand: dict[str, Any] | None = None
    best_score = 0.0
    for cand in candidates:
        cand_title = normalize_title(cand.get("title"))
        if not cand_title:
            continue
        score = _token_jaccard(ref_title, cand_title)
        if score > best_score:
            best_score = score
            best_cand = cand
    if best_cand is not None and best_score >= _FUZZY_THRESHOLD:
        return MatchResult(
            doc_id=_cand_id(best_cand),
            match_type=MatchType.TITLE_FUZZY,
            confidence=round(best_score, 4),
        )
    return None


_MATCHERS = (
    _match_by_doi,
    _match_by_arxiv_id,
    _match_by_title_exact,
    _match_by_title_fuzzy,
)


def match_reference_to_document(
    reference: dict[str, Any],
    candidates: Sequence[dict[str, Any]],
) -> MatchResult:
    """按优先级匹配参考文献到候选文档。

    优先级：DOI 归一化 → arXiv id → 题名精确 → 题名 token Jaccard ≥ 0.9 → unmatched。
    先命中即返回（短路）。

    候选文档字段：doc_id（或 id）、doi、title、arxiv_id、file_path。
    """
    if not candidates:
        return MatchResult(doc_id=None, match_type=MatchType.UNMATCHED, confidence=0.0)

    for matcher in _MATCHERS:
        result = matcher(reference, candidates)
        if result is not None:
            return result

    return MatchResult(doc_id=None, match_type=MatchType.UNMATCHED, confidence=0.0)


def _cand_id(cand: dict[str, Any]) -> str | None:
    """从候选文档提取标识（doc_id 优先于 id）。"""
    cid = cand.get("doc_id") or cand.get("id")
    return str(cid) if cid is not None else None


def build_candidate_index(documents: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """构建候选文档索引（DOI / arXiv id / 归一化题名 → doc_id），供批量匹配复用。"""
    by_doi: dict[str, str] = {}
    by_title: dict[str, str] = {}
    by_arxiv: dict[str, str] = {}
    for doc in documents:
        cid = _cand_id(doc)
        if cid is None:
            continue
        doi = normalize_doi(doc.get("doi"))
        if doi:
            by_doi[doi] = cid
        title = normalize_title(doc.get("title"))
        if title:
            by_title[title] = cid
        for aid in _extract_arxiv_ids(doc, _CAND_ARXIV_FIELDS):
            by_arxiv.setdefault(aid, cid)
    return {
        "by_doi": by_doi,
        "by_title": by_title,
        "by_arxiv": by_arxiv,
        "documents": list(documents),
    }
