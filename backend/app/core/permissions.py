"""细粒度 RBAC 权限控制。

权限码采用 `resource:action` 约定，角色（roles 表）通过 `permissions` JSON 数组
持有权限码，管理员（admin）或以 `all` 为权限的角色拥有全部权限。

权限分为三级：
- 文档级：document:read / document:write（配合资源归属 owner 校验）
- 任务级：task:read / task:write（配合负责人归属校验）
- 系统级：system:user:manage / system:role:manage / system:audit:read
"""

from typing import List, Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.role import Role

# ── 文档级 ──────────────────────────────────────────────
DOCUMENT_READ = "document:read"
DOCUMENT_WRITE = "document:write"

# ── 任务级 ──────────────────────────────────────────────
TASK_READ = "task:read"
TASK_WRITE = "task:write"

# ── 标注级 ──────────────────────────────────────────────
ANNOTATION_READ = "annotation:read"
ANNOTATION_WRITE = "annotation:write"
ANNOTATION_REVIEW = "annotation:review"

# ── 系统级 ──────────────────────────────────────────────
SYSTEM_USER_MANAGE = "system:user:manage"
SYSTEM_ROLE_MANAGE = "system:role:manage"
SYSTEM_AUDIT_READ = "system:audit:read"

# 全部可分配权限码（不含 admin 通配符 all）
ALL_PERMISSIONS: List[str] = [
    DOCUMENT_READ,
    DOCUMENT_WRITE,
    TASK_READ,
    TASK_WRITE,
    ANNOTATION_READ,
    ANNOTATION_WRITE,
    ANNOTATION_REVIEW,
    SYSTEM_USER_MANAGE,
    SYSTEM_ROLE_MANAGE,
    SYSTEM_AUDIT_READ,
]

PERMISSION_DESCRIPTIONS: dict = {
    DOCUMENT_READ: "查看文档",
    DOCUMENT_WRITE: "上传/编辑/删除/解析文档",
    TASK_READ: "查看任务",
    TASK_WRITE: "创建/分配/操作任务",
    ANNOTATION_READ: "查看标注",
    ANNOTATION_WRITE: "创建/编辑标注",
    ANNOTATION_REVIEW: "审核标注",
    SYSTEM_USER_MANAGE: "用户管理",
    SYSTEM_ROLE_MANAGE: "角色权限管理",
    SYSTEM_AUDIT_READ: "查看操作日志",
}

ADMIN_ROLE = "admin"


async def get_role_permissions(db: AsyncSession, role_name: Optional[str]) -> List[str]:
    """读取指定角色的权限码列表。"""
    if not role_name:
        return []
    result = await db.execute(select(Role).where(Role.name == role_name))
    role = result.scalar_one_or_none()
    if not role or not role.permissions:
        return []
    return [p for p in role.permissions if isinstance(p, str)]


async def get_current_user_permissions(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """返回附带 permissions 列表的 current_user 依赖。"""
    permissions = await get_role_permissions(db, current_user.get("role"))
    current_user["permissions"] = permissions
    return current_user


def has_permission(user: dict, permission: str) -> bool:
    """判定当前用户是否具备某权限（admin 或 all 通配符自动放行）。"""
    if user.get("role") == ADMIN_ROLE:
        return True
    permissions = user.get("permissions") or []
    return "all" in permissions or permission in permissions


def has_any_permission(user: dict, *permissions: str) -> bool:
    """判定当前用户是否具备任一权限。"""
    if user.get("role") == ADMIN_ROLE:
        return True
    owned = set(user.get("permissions") or [])
    if "all" in owned:
        return True
    return any(p in owned for p in permissions)


def require_permission(permission: str):
    """依赖工厂：要求当前用户具备指定权限。"""

    async def checker(
        current_user: dict = Depends(get_current_user_permissions),
    ) -> dict:
        if not has_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少权限：{permission}",
            )
        return current_user

    return checker


def require_any_permission(*permissions: str):
    """依赖工厂：要求当前用户具备任意一个权限。"""

    async def checker(
        current_user: dict = Depends(get_current_user_permissions),
    ) -> dict:
        if not has_any_permission(current_user, *permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少权限：{' 或 '.join(permissions)}",
            )
        return current_user

    return checker
