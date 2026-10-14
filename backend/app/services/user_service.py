"""
用户服务门面（插件化架构迁移：实现已迁至 `app/plugins/user/service.py`）。

- 兼容再导出：既有 `from app.services.user_service import UserService` 不受影响。
- 运行期消费者应经 `registry.get("user")` 动态寻址。
"""

from __future__ import annotations

from app.plugins.user.service import UserService

__all__ = ["UserService"]
