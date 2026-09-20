from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.annotation import OperationLog


class OperationLogService:
    async def log_operation(
        self,
        db: AsyncSession,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str = None,
        details: dict = None,
        ip_address: str = None,
    ) -> OperationLog:
        """记录一条操作日志（由调用方事务统一提交）。"""
        log = OperationLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
        )
        db.add(log)
        return log

    async def list_logs(
        self,
        db: AsyncSession,
        page: int,
        page_size: int,
        user_id: str = None,
        action: str = None,
        resource_type: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
    ):
        """按用户/类型/时间范围筛选操作日志。"""
        query = select(OperationLog)
        if user_id:
            query = query.where(OperationLog.user_id == user_id)
        if action:
            query = query.where(OperationLog.action == action)
        if resource_type:
            query = query.where(OperationLog.resource_type == resource_type)
        if start_date:
            query = query.where(OperationLog.created_at >= start_date)
        if end_date:
            query = query.where(OperationLog.created_at <= end_date)

        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query)

        query = (
            query.offset((page - 1) * page_size)
            .limit(page_size)
            .order_by(OperationLog.created_at.desc())
        )
        result = await db.execute(query)
        logs = result.scalars().all()
        return logs, total
