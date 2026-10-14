from loguru import logger
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plugin.base import Plugin
from app.models.comment import Notification
from app.models.user import User


class NotificationService:
    # ─── 插件协议 ──────────────────────────────────────────────────────────
    async def on_start(self) -> None:
        logger.info("notification plugin started")

    async def on_stop(self) -> None:
        logger.info("notification plugin stopped")

    def health(self) -> dict:
        return {"backend": "notification", "available": True}

    async def unread_count(self, db: AsyncSession, user_id: str) -> int:
        result = await db.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        )
        return result.scalar() or 0

    async def list_notifications(
        self,
        db: AsyncSession,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        unread_only: bool = False,
    ):
        query = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            query = query.where(Notification.is_read.is_(False))

        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query)

        query = (
            query.order_by(Notification.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(query)
        notifications = result.scalars().all()

        items = []
        for n in notifications:
            sender_name = None
            if n.sender_id:
                r = await db.execute(select(User).where(User.id == n.sender_id))
                s = r.scalar_one_or_none()
                if s:
                    sender_name = s.username
            items.append(
                {
                    "id": n.id,
                    "type": n.type,
                    "title": n.title,
                    "content": n.content,
                    "sender_id": n.sender_id,
                    "sender_name": sender_name,
                    "resource_type": n.resource_type,
                    "resource_id": n.resource_id,
                    "is_read": n.is_read,
                    "created_at": n.created_at,
                }
            )

        unread = await self.unread_count(db, user_id)
        return items, total, unread

    async def mark_read(self, db: AsyncSession, notification_id: str, user_id: str) -> bool:
        result = await db.execute(
            update(Notification)
            .where(Notification.id == notification_id, Notification.user_id == user_id)
            .values(is_read=True)
        )
        return result.rowcount > 0

    async def mark_all_read(self, db: AsyncSession, user_id: str) -> int:
        result = await db.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
            .values(is_read=True)
        )
        return result.rowcount


class NotificationPlugin(Plugin):
    """官方插件：notification —— 通知服务（存量迁移自 app/services/notification_service.py）。"""

    name = "notification"
    version = "1.0.0"
    config_prefix = ""
    requires: list[str] = []
    type = "service"
    legacy_module = "app.services.notification_service"

    def create(self, registry, settings) -> NotificationService:
        return NotificationService()


plugin = NotificationPlugin()
