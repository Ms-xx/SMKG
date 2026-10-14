"""
认证服务门面（插件化架构迁移：实现已迁至 `app/plugins/auth/service.py`）。

- 兼容再导出：既有 `from app.services.auth_service import AuthService` 不受影响。
- 运行期消费者应经 `registry.get("auth")` 动态寻址。
"""

from __future__ import annotations

from app.plugins.auth.service import AuthService

__all__ = ["AuthService"]
