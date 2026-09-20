import re
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.annotation import Annotation
from app.models.comment import AnnotationComment, Notification
from app.models.user import User
from app.services.operation_log_service import OperationLogService

# 匹配 @用户名 提及（用户名允许字母/数字/下划线/点/连字符/中文）
MENTION_RE = re.compile(r"@([\w\u4e00-\u9fa5.-]+)")


class CommentService:
    def __init__(self):
        self.log_service = OperationLogService()

    async def _user_info(self, db: AsyncSession, user_id: str) -> dict:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            return {"username": user.username, "full_name": user.full_name}
        return {"username": None, "full_name": None}

    async def _resolve_mentions(
        self, db: AsyncSession, content: str, exclude_user_id: str
    ) -> List[User]:
        """解析 content 中的 @username，返回去重、排除发送者本人的用户列表。"""
        names = set(MENTION_RE.findall(content))
        if not names:
            return []
        users: List[User] = []
        seen = set()
        for name in names:
            result = await db.execute(select(User).where(User.username == name))
            user = result.scalar_one_or_none()
            if user and user.id != exclude_user_id and user.id not in seen:
                seen.add(user.id)
                users.append(user)
        return users

    async def create_comment(
        self,
        db: AsyncSession,
        annotation_id: str,
        content: str,
        parent_id: Optional[str],
        user_id: str,
        ip_address: Optional[str] = None,
    ):
        result = await db.execute(select(Annotation).where(Annotation.id == annotation_id))
        if not result.scalar_one_or_none():
            return None

        mentioned = await self._resolve_mentions(db, content, user_id)

        comment = AnnotationComment(
            annotation_id=annotation_id,
            parent_id=parent_id,
            user_id=user_id,
            content=content,
            mentions=[u.id for u in mentioned],
        )
        db.add(comment)
        await db.flush()

        # 通知被 @ 提及的用户
        for u in mentioned:
            db.add(
                Notification(
                    user_id=u.id,
                    type="mention",
                    title="有人在评论中提及了你",
                    content=content,
                    sender_id=user_id,
                    resource_type="comment",
                    resource_id=comment.id,
                )
            )

        # 回复时通知父评论作者
        if parent_id:
            p = await db.execute(select(AnnotationComment).where(AnnotationComment.id == parent_id))
            parent_comment = p.scalar_one_or_none()
            if parent_comment and parent_comment.user_id != user_id:
                db.add(
                    Notification(
                        user_id=parent_comment.user_id,
                        type="reply",
                        title="有人回复了你的评论",
                        content=content,
                        sender_id=user_id,
                        resource_type="comment",
                        resource_id=comment.id,
                    )
                )

        await db.flush()
        await db.refresh(comment)

        await self.log_service.log_operation(
            db,
            user_id,
            "comment",
            "annotation",
            annotation_id,
            {"comment_id": comment.id},
            ip_address,
        )

        info = await self._user_info(db, user_id)
        return {
            "id": comment.id,
            "annotation_id": comment.annotation_id,
            "parent_id": comment.parent_id,
            "user_id": comment.user_id,
            "content": comment.content,
            "mentions": comment.mentions or [],
            "created_at": comment.created_at,
            "updated_at": comment.updated_at,
            **info,
        }

    async def list_comments(
        self,
        db: AsyncSession,
        annotation_id: Optional[str] = None,
        document_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ):
        query = select(AnnotationComment)
        if annotation_id:
            query = query.where(AnnotationComment.annotation_id == annotation_id)
        if document_id:
            query = query.join(Annotation, AnnotationComment.annotation_id == Annotation.id).where(
                Annotation.document_id == document_id
            )

        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query)

        query = (
            query.order_by(AnnotationComment.created_at.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(query)
        comments = result.scalars().all()

        items = []
        for c in comments:
            info = await self._user_info(db, c.user_id)
            items.append(
                {
                    "id": c.id,
                    "annotation_id": c.annotation_id,
                    "parent_id": c.parent_id,
                    "user_id": c.user_id,
                    "content": c.content,
                    "mentions": c.mentions or [],
                    "created_at": c.created_at,
                    "updated_at": c.updated_at,
                    **info,
                }
            )
        return items, total

    async def delete_comment(
        self, db: AsyncSession, comment_id: str, user_id: str, ip_address: Optional[str] = None
    ):
        """返回 True=删除成功，False=不存在，None=无权限。"""
        result = await db.execute(
            select(AnnotationComment).where(AnnotationComment.id == comment_id)
        )
        comment = result.scalar_one_or_none()
        if not comment:
            return False
        if comment.user_id != user_id:
            return None
        await db.delete(comment)
        await self.log_service.log_operation(
            db,
            user_id,
            "comment_delete",
            "annotation",
            comment.annotation_id,
            {"comment_id": comment_id},
            ip_address,
        )
        return True
