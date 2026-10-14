# -*- coding: utf-8 -*-
"""
citation_link_service 门面（插件化架构迁移：实现已迁至 `app/plugins/citation_link/service.py`）。
兼容再导出：既有 `from app.services.<源> import ...` 不受影响。
"""

from __future__ import annotations

from app.plugins.citation_link.service import (
    CitationLinkService,
    build_citation_map,
    citation_link_service,
    extract_inline_citations,
    extract_title_tree,
)

__all__ = [
    "CitationLinkService",
    "build_citation_map",
    "citation_link_service",
    "extract_inline_citations",
    "extract_title_tree",
]
