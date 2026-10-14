# -*- coding: utf-8 -*-
"""
anomaly_detection_service 门面（插件化架构迁移：实现已迁至 `app/plugins/anomaly_detection/service.py`）。
兼容再导出：既有 `from app.services.<源> import ...` 不受影响。
"""

from __future__ import annotations

from app.plugins.anomaly_detection.service import (
    AnomalyDetectionService,
    _density,
    anomaly_detection_service,
)

__all__ = [
    "AnomalyDetectionService",
    "_density",
    "anomaly_detection_service",
]
