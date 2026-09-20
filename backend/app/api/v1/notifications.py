from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.comment import NotificationListResponse, UnreadCountResponse
from app.services.notification_service import NotificationService

router = APIRouter()
notification_service = NotificationService()


@router.get("/", response_model=NotificationListResponse)
async def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = False,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询当前用户的通知，附带未读数量。"""
    items, total, unread = await notification_service.list_notifications(
        db, current_user["user_id"], page, page_size, unread_only
    )
    return NotificationListResponse(
        items=items, total=total, unread_count=unread, page=page, page_size=page_size
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    count = await notification_service.unread_count(db, current_user["user_id"])
    return UnreadCountResponse(count=count)


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ok = await notification_service.mark_read(db, notification_id, current_user["user_id"])
    if not ok:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "marked as read"}


@router.post("/read-all")
async def mark_all_read(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await notification_service.mark_all_read(db, current_user["user_id"])
    return {"message": "all marked as read"}
