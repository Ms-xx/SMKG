"""
通知服务门面（插件化架构迁移：实现已迁至 `app/plugins/notification/service.py`）。

- 兼容再导出：既有 `from app.services.notification_service import NotificationService`
  不受影响。
- 运行期消费者应经 `registry.get("notification")` 动态寻址。
"""

from __future__ import annotations

from app.plugins.notification.service import NotificationService

__all__ = ["NotificationService"]
