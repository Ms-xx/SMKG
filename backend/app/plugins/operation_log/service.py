from datetime import datetime

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plugin.base import Plugin
from app.models.annotation import OperationLog


class OperationLogService:
    # ─── 插件协议 ──────────────────────────────────────────────────────────
    async def on_start(self) -> None:
        logger.info("operation_log plugin started")

    async def on_stop(self) -> None:
        logger.info("operation_log plugin stopped")

    def health(self) -> dict:
        return {"backend": "operation_log", "available": True}

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


class OperationLogPlugin(Plugin):
    """官方插件：operation_log —— 操作日志服务（存量迁移自 app/services/operation_log_service.py）。"""

    name = "operation_log"
    version = "1.0.0"
    config_prefix = ""
    requires: list[str] = []
    type = "service"
    legacy_module = "app.services.operation_log_service"

    def create(self, registry, settings) -> OperationLogService:
        return OperationLogService()


plugin = OperationLogPlugin()
