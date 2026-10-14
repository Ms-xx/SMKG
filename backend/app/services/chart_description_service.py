# -*- coding: utf-8 -*-
"""
图表描述服务门面（插件化架构迁移：实现已迁至 `app/plugins/chart_description/service.py`）。
兼容再导出：既有 `from app.services.chart_description_service import ChartDescriptionService` 不受影响。
"""

from __future__ import annotations

from app.plugins.chart_description.service import (
    ChartDescriptionService,
    chart_description_service,
)

__all__ = ["ChartDescriptionService", "chart_description_service"]
