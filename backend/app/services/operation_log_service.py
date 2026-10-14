"""
操作日志服务门面（插件化架构迁移：实现已迁至 `app/plugins/operation_log/service.py`）。

- 兼容再导出：既有 `from app.services.operation_log_service import OperationLogService`
  不受影响。
- 运行期消费者应经 `registry.get("operation_log")` 动态寻址。
"""

from __future__ import annotations

from app.plugins.operation_log.service import OperationLogService

__all__ = ["OperationLogService"]
