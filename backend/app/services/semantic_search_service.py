# -*- coding: utf-8 -*-
"""
semantic_search_service 门面（插件化架构迁移：实现已迁至 `app/plugins/semantic_search/service.py`）。
兼容再导出：既有 `from app.services.<源> import ...` 不受影响。
"""

from __future__ import annotations

from app.plugins.semantic_search.service import (
    SemanticSearchService,
    facet_search,
    keyword_score,
    semantic_search_service,
    suggest,
    tokenize,
)

__all__ = [
    "SemanticSearchService",
    "facet_search",
    "keyword_score",
    "semantic_search_service",
    "suggest",
    "tokenize",
]
