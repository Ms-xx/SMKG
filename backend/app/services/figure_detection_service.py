# -*- coding: utf-8 -*-
"""
图表/公式检测服务门面（插件化架构迁移：实现已迁至 `app/plugins/figure_detection/service.py`）。
兼容再导出：既有 `from app.services.figure_detection_service import FigureDetectionService` 不受影响。
"""

from __future__ import annotations

from app.plugins.figure_detection.service import (
    FigureDetectionService,
    figure_detection_service,
)

__all__ = ["FigureDetectionService", "figure_detection_service"]
