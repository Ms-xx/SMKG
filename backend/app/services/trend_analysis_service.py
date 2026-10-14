# -*- coding: utf-8 -*-
"""
trend_analysis_service 门面（插件化架构迁移：实现已迁至 `app/plugins/trend_analysis/service.py`）。
兼容再导出：既有 `from app.services.<源> import ...` 不受影响。
"""

from __future__ import annotations

from app.plugins.trend_analysis.service import (
    TrendAnalysisService,
    _bucket_key,
    trend_analysis_service,
)

__all__ = [
    "TrendAnalysisService",
    "_bucket_key",
    "trend_analysis_service",
]
