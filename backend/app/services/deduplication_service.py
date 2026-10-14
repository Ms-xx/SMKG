# -*- coding: utf-8 -*-
"""
deduplication_service 门面（插件化架构迁移：实现已迁至 `app/plugins/deduplication/service.py`）。
兼容再导出：既有 `from app.services.<源> import ...` 不受影响。
"""

from __future__ import annotations

from app.plugins.deduplication.service import (
    DeduplicationService,
    deduplication_service,
    extract_affiliations,
    extract_arxiv_version,
    hamming_distance,
    simhash_similarity,
)

__all__ = [
    "DeduplicationService",
    "deduplication_service",
    "extract_affiliations",
    "extract_arxiv_version",
    "hamming_distance",
    "simhash_similarity",
]
