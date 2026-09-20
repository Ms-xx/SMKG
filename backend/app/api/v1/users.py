from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import SYSTEM_USER_MANAGE, require_permission
from app.core.security import get_current_user
from app.schemas.user import MentionableUser, UserListResponse, UserResponse, UserUpdate
from app.services.user_service import UserService

router = APIRouter()
user_service = UserService()


@router.get("/", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    keyword: Optional[str] = None,
    current_user: dict = Depends(require_permission(SYSTEM_USER_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    users, total = await user_service.list_users(db, page, page_size, role, is_active, keyword)
    return UserListResponse(items=users, total=total, page=page, page_size=page_size)


@router.get("/mentionable", response_model=list[MentionableUser])
async def list_mentionable_users(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """返回可被 @ 提及的活跃用户列表（用于评论提及自动补全）。"""
    return await user_service.list_mentionable(db)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user["role"] != "admin" and current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    user = await user_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    update_data: UserUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user["role"] != "admin" and current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    user = await user_service.update_user(db, user_id, update_data)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: str,
    role: str,
    current_user: dict = Depends(require_permission(SYSTEM_USER_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    user = await user_service.update_role(db, user_id, role)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: str,
    is_active: bool,
    current_user: dict = Depends(require_permission(SYSTEM_USER_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    user = await user_service.update_status(db, user_id, is_active)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    current_user: dict = Depends(require_permission(SYSTEM_USER_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    deleted = await user_service.delete_user(db, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
