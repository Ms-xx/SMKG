"""
任务服务门面（插件化架构迁移：实现已迁至 `app/plugins/task/service.py`）。

- 兼容再导出：既有 `from app.services.task_service import TaskService` 不受影响。
- 运行期消费者应经 `registry.get("task")` 动态寻址。
"""

from __future__ import annotations

from app.plugins.task.service import TaskService

__all__ = ["TaskService"]
