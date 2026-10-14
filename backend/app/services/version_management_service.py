"""
版本管理服务门面（插件化架构迁移：实现已迁至 `app/plugins/version_management/service.py`）。

- 兼容再导出：既有 `from app.services.version_management_service import VersionManagementService`
  等不受影响。
- 运行期消费者应经 `registry.get("version_management")` 动态寻址。
"""

from __future__ import annotations

from app.plugins.version_management.service import (
    PIPELINE_STEPS,
    STAGES,
    VersionManagementService,
    compare_metrics,
    data_quality,
    dataset_hash,
    evaluate_retrain_trigger,
    version_management_service,
)

__all__ = [
    "STAGES",
    "PIPELINE_STEPS",
    "dataset_hash",
    "data_quality",
    "evaluate_retrain_trigger",
    "compare_metrics",
    "VersionManagementService",
    "version_management_service",
]
