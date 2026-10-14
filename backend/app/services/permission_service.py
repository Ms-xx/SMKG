"""
权限服务门面（插件化架构迁移：实现已迁至 `app/plugins/permission/service.py`）。

- 兼容再导出：既有 `from app.services.permission_service import PermissionService`
  不受影响。
- 运行期消费者应经 `registry.get("permission")` 动态寻址。
"""

from __future__ import annotations

from app.plugins.permission.service import PermissionService

__all__ = ["PermissionService"]
