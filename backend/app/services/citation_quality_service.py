# -*- coding: utf-8 -*-
"""
引用含金量筛选服务门面（插件化架构迁移：实现已迁至 `app/plugins/citation_quality/service.py`）。

- 兼容再导出：既有 `from app.services.citation_quality_service import CitationQualityService /
  score_reference / analyze_document / score_documents` 不受影响。
"""

from __future__ import annotations

from app.plugins.citation_quality.service import (
    PERFUNCTORY_THRESHOLD,
    SUPPORTING_THRESHOLD,
    CitationQualityService,
    _short_key,
    analyze_document,
    citation_quality_service,
    score_documents,
    score_reference,
)

__all__ = [
    "CitationQualityService",
    "citation_quality_service",
    "score_reference",
    "analyze_document",
    "score_documents",
    "_short_key",
    "PERFUNCTORY_THRESHOLD",
    "SUPPORTING_THRESHOLD",
]
