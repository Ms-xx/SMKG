"""
告警服务门面（插件化架构迁移：实现已迁至 `app/plugins/alert/service.py`）。

- 兼容再导出：既有 `from app.services.alert_service import build_webhook` 等不受影响。
- 运行期消费者应经 `registry.get("alert")` 动态寻址。
"""

from __future__ import annotations

from app.plugins.alert.service import (
    AlertService,
    build_webhook,
    format_dingtalk_markdown,
    format_wecom_markdown,
    sign_robot,
)

__all__ = [
    "AlertService",
    "build_webhook",
    "format_dingtalk_markdown",
    "format_wecom_markdown",
    "sign_robot",
]
