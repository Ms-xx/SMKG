from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import (
    ALL_PERMISSIONS,
    PERMISSION_DESCRIPTIONS,
    SYSTEM_ROLE_MANAGE,
    get_current_user_permissions,
    require_permission,
)
from app.schemas.role import (
    MyPermissionsResponse,
    PermissionInfo,
    PermissionListResponse,
    RoleListResponse,
    RolePermissionsUpdate,
    RoleResponse,
)
from app.services.permission_service import PermissionService

router = APIRouter()
permission_service = PermissionService()


@router.get("/me", response_model=MyPermissionsResponse)
async def get_my_permissions(
    current_user: dict = Depends(get_current_user_permissions),
):
    """返回当前用户的角色及有效权限码列表。"""
    return MyPermissionsResponse(
        role=current_user.get("role") or "",
        permissions=current_user.get("permissions") or [],
    )


@router.get("/definitions", response_model=PermissionListResponse)
async def get_permission_definitions(
    current_user: dict = Depends(get_current_user_permissions),
):
    """返回全部可分配权限码及其说明。"""
    items = [
        PermissionInfo(code=code, description=PERMISSION_DESCRIPTIONS.get(code, ""))
        for code in ALL_PERMISSIONS
    ]
    return PermissionListResponse(items=items, total=len(items))


@router.get("/roles", response_model=RoleListResponse)
async def list_roles(
    current_user: dict = Depends(require_permission(SYSTEM_ROLE_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """列出全部角色及其权限（仅系统级权限持有者）。"""
    roles = await permission_service.list_roles(db)
    items = [
        RoleResponse(
            id=r.id, name=r.name, description=r.description or "", permissions=r.permissions or []
        )
        for r in roles
    ]
    return RoleListResponse(items=items, total=len(items))


@router.put("/roles/{role_name}", response_model=RoleResponse)
async def update_role_permissions(
    role_name: str,
    body: RolePermissionsUpdate,
    current_user: dict = Depends(require_permission(SYSTEM_ROLE_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """更新指定角色的权限（仅系统级权限持有者）。"""
    role = await permission_service.update_role_permissions(db, role_name, body.permissions)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description or "",
        permissions=role.permissions or [],
    )
