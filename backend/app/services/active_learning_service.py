"""
主动学习服务门面（插件化架构迁移：实现已迁至 `app/plugins/active_learning/service.py`）。

- 兼容再导出：既有 `from app.services.active_learning_service import ActiveLearningService,
  entropy, ...` 不受影响。
- 运行期消费者应经 `registry.get("active_learning")` 动态寻址。
"""

from __future__ import annotations

from app.plugins.active_learning.service import (
    DIVERSITY_METHODS,
    QBC_METHODS,
    UNCERTAINTY_METHODS,
    ActiveLearningService,
    active_learning_service,
    core_set_indices,
    disagreement,
    diversity_select,
    entropy,
    kmeans_pp_indices,
    least_confidence,
    margin,
    qbc_score,
    uncertainty_score,
    vote_entropy,
)

__all__ = [
    "UNCERTAINTY_METHODS",
    "DIVERSITY_METHODS",
    "QBC_METHODS",
    "entropy",
    "least_confidence",
    "margin",
    "uncertainty_score",
    "vote_entropy",
    "disagreement",
    "qbc_score",
    "core_set_indices",
    "kmeans_pp_indices",
    "diversity_select",
    "ActiveLearningService",
    "active_learning_service",
]
