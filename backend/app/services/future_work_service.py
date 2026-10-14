# -*- coding: utf-8 -*-
"""
Future Work 前沿探索服务门面（插件化架构迁移：实现已迁至 `app/plugins/future_work/service.py`）。

- 兼容再导出：既有 `from app.services.future_work_service import FutureWorkService /
  extract_future_work / judge_resolved / scan_future_work` 不受影响。
"""

from __future__ import annotations

from app.plugins.future_work.service import (
    FutureWorkService,
    extract_future_work,
    future_work_service,
    judge_resolved,
    scan_future_work,
)

__all__ = [
    "FutureWorkService",
    "future_work_service",
    "extract_future_work",
    "judge_resolved",
    "scan_future_work",
]
