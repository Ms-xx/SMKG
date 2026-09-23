# -*- coding: utf-8 -*-
"""
版式联动阅读服务（对应 XiangMu 10.2 模块三）

职责：
1. 正文引用定位：正则识别正文中的 `[n]` / `[1,2]` / `(Author, Year)` 引用标记；
2. 引用 ↔ 参考文献双向映射：把正文引用位置与结构化 references 的 index 对齐；
3. 标题树提取：从 PDF 大纲（PyMuPDF get_toc）提取标题层级。

依赖策略（可插拔、可降级）：
- 纯 Python（re）零依赖；标题树读取依赖 PyMuPDF（fitz），缺失时降级为空树。
- 中英对比阅读与划词/整篇翻译依赖翻译模型/API，本服务不承担（见文档说明）。
"""
from __future__ import annotations

import re
from typing import Any

from app.core.config import settings

# 数字方括号引用：[1] / [1,2] / [3-5] / ［1］（全角）
_NUMERIC_RE = re.compile(r"[\[［【]\s*(\d{1,3}(?:\s*[,，、\-–]\s*\d{1,3})*)\s*[\]］】]")

# 作者-年份引用：(Vaswani et al., 2017) / Vaswani et al. 2017
_AUTHOR_YEAR_RE = re.compile(r"\(([^()]{0,80}?(?:19|20)\d{2}[a-z]?)\)")


def extract_inline_citations(text: str) -> list[dict[str, Any]]:
    """返回正文内引用标记列表，含参考编号 ref_index 与位置 start/end、来源片段。"""
    if not text:
        return []
    citations: list[dict[str, Any]] = []
    for m in _NUMERIC_RE.finditer(text):
        nums = re.findall(r"\d{1,3}", m.group(1))
        for n in nums:
            citations.append(
                {
                    "ref_index": int(n),
                    "start": m.start(),
                    "end": m.end(),
                    "kind": "numeric",
                    "raw": m.group(0),
                    "snippet": text[max(0, m.start() - 20) : m.end() + 20],
                }
            )
    for m in _AUTHOR_YEAR_RE.finditer(text):
        citations.append(
            {
                "ref_index": None,
                "start": m.start(),
                "end": m.end(),
                "kind": "author_year",
                "raw": m.group(1),
                "snippet": text[max(0, m.start() - 20) : m.end() + 20],
            }
        )
    return citations


def build_citation_map(pages_text: list[str], references: list[dict[str, Any]]) -> dict[str, Any]:
    """
    pages_text: 每页文本（列表，下标即页序）。
    references: reference_service 输出的结构化条目（含 index）。

    产出：
    - citations: 每个正文引用 + 所在 page_index/page_number + ref_index
    - by_reference: ref_index -> 引用位置列表（供前端从参考文献反查正文）
    """
    citations: list[dict[str, Any]] = []
    by_reference: dict[int, list[dict[str, Any]]] = {}
    for page_idx, text in enumerate(pages_text or []):
        for cit in extract_inline_citations(text):
            entry = {
                **cit,
                "page_index": page_idx,
                "page_number": page_idx + 1,
            }
            citations.append(entry)
            if cit["ref_index"] is not None:
                by_reference.setdefault(cit["ref_index"], []).append(entry)

    ref_indexes = sorted(
        {int(r.get("index")) for r in references or [] if r.get("index") is not None}
    )
    return {
        "backend": "rule",
        "total_citations": len(citations),
        "references_count": len(ref_indexes),
        "citations": citations,
        "by_reference": {str(k): v for k, v in by_reference.items()},
    }


def extract_title_tree(pdf_path: str) -> list[dict[str, Any]]:
    """读取 PDF 大纲标题树（层级 level，Fallback 降级为空）。"""
    try:
        import fitz  # noqa: F401
    except Exception:
        return []
    doc = None
    try:
        doc = fitz.open(pdf_path)
        toc = doc.get_toc()
    except Exception:
        return []
    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass
    return [
        {"level": item[0], "title": item[1], "page_number": item[2]}
        for item in toc
        if len(item) >= 3
    ]


class CitationLinkService:
    @property
    def available(self) -> bool:
        return settings.CITATION_LINK_ENABLED

    def build_map(self, pages_text: list[str], references: list[dict[str, Any]]) -> dict[str, Any]:
        return build_citation_map(pages_text, references)

    def title_tree(self, pdf_path: str) -> dict[str, Any]:
        return {"backend": "fitz", "tree": extract_title_tree(pdf_path)}


# 全局单例
citation_link_service = CitationLinkService()
