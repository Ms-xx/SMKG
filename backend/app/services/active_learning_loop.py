# -*- coding: utf-8 -*-
"""
active_learning_loop 门面（插件化架构迁移：实现已迁至 `app/plugins/active_learning_loop/service.py`）。
兼容再导出：既有 `from app.services.<源> import ...` 不受影响。
"""

from __future__ import annotations

from app.plugins.active_learning_loop.service import (
    ActiveLearningLoopService,
    active_learning_loop_service,
    evaluate_loop,
    predict_soft,
    train_surrogate,
)

__all__ = [
    "ActiveLearningLoopService",
    "active_learning_loop_service",
    "evaluate_loop",
    "predict_soft",
    "train_surrogate",
]
