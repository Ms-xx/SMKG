# -*- coding: utf-8 -*-
"""
citation_graph_match 门面（插件化架构迁移：实现已迁至 `app/plugins/citation_graph_match/service.py`）。
兼容再导出：既有 `from app.services.<源> import ...` 不受影响。
"""

from __future__ import annotations

from app.plugins.citation_graph_match.service import (
    MatchResult,
    MatchType,
    build_candidate_index,
    match_reference_to_document,
    normalize_arxiv_id,
    normalize_doi,
    normalize_title,
)

__all__ = [
    "MatchResult",
    "MatchType",
    "build_candidate_index",
    "match_reference_to_document",
    "normalize_arxiv_id",
    "normalize_doi",
    "normalize_title",
]
