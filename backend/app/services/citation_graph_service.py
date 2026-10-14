# -*- coding: utf-8 -*-
"""
citation_graph_service 门面（插件化架构迁移：实现已迁至 `app/plugins/citation_graph/service.py`）。
兼容再导出：既有 `from app.services.<源> import ...` 不受影响。
"""

from __future__ import annotations

from app.plugins.citation_graph.service import (
    CitationGraphService,
    betweenness_centrality,
    build_citation_network,
    citation_graph_service,
    deduplicate_future_work,
    generate_survey,
    key_papers,
    page_rank,
)

__all__ = [
    "CitationGraphService",
    "betweenness_centrality",
    "build_citation_network",
    "citation_graph_service",
    "deduplicate_future_work",
    "generate_survey",
    "key_papers",
    "page_rank",
]
