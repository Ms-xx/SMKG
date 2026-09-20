from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import SYSTEM_AUDIT_READ, require_permission
from app.schemas.operation_log import OperationLogListResponse
from app.services.operation_log_service import OperationLogService

router = APIRouter()
operation_log_service = OperationLogService()


@router.get("/", response_model=OperationLogListResponse)
async def list_operation_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: dict = Depends(require_permission(SYSTEM_AUDIT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """查询操作日志，支持按用户/操作类型/资源类型/时间范围筛选。"""
    logs, total = await operation_log_service.list_logs(
        db, page, page_size, user_id, action, resource_type, start_date, end_date
    )
    return OperationLogListResponse(items=logs, total=total, page=page, page_size=page_size)
