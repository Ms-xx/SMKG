from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.annotation import Annotation
from app.models.task import Task
from app.models.user import User


class StatisticsService:
    """工作量统计：个人完成量、准确率、团队看板。"""

    async def get_user_stats(self, db: AsyncSession, user_id: str) -> Optional[dict]:
        """个人工作量统计（标注完成量 + 准确率 + 任务完成量）。"""
        users = await self._list_users(db, user_id)
        if not users:
            return None
        ann_by_user = await self._annotation_counts(db, user_id)
        task_by_user = await self._task_counts(db, user_id)
        return self._build_stats(
            users[0], ann_by_user.get(user_id, {}), task_by_user.get(user_id, {})
        )

    async def get_team_dashboard(self, db: AsyncSession) -> dict:
        """团队看板：按用户聚合的工作量统计。"""
        users = await self._list_users(db, None)
        ann_by_user = await self._annotation_counts(db, None)
        task_by_user = await self._task_counts(db, None)

        items = []
        for u in users:
            uid = u["id"]
            items.append(self._build_stats(u, ann_by_user.get(uid, {}), task_by_user.get(uid, {})))

        # 按标注完成量降序排列
        items.sort(key=lambda x: x["annotation_total"], reverse=True)
        return {"items": items, "total_users": len(items)}

    async def _list_users(self, db: AsyncSession, user_id: Optional[str]) -> List[dict]:
        query = select(User)
        if user_id:
            query = query.where(User.id == user_id)
        result = await db.execute(query)
        return [
            {"id": u.id, "username": u.username, "full_name": u.full_name, "role": u.role}
            for u in result.scalars().all()
        ]

    async def _annotation_counts(
        self, db: AsyncSession, user_id: Optional[str]
    ) -> Dict[str, Dict[str, int]]:
        """按标注人聚合各状态的标注数量。"""
        query = select(Annotation.annotated_by, Annotation.status, func.count())
        if user_id:
            query = query.where(Annotation.annotated_by == user_id)
        query = query.group_by(Annotation.annotated_by, Annotation.status)
        result = await db.execute(query)

        data: Dict[str, Dict[str, int]] = {}
        for uid, status, cnt in result.all():
            data.setdefault(uid, {})[status] = cnt
        return data

    async def _task_counts(
        self, db: AsyncSession, user_id: Optional[str]
    ) -> Dict[str, Dict[str, int]]:
        """按负责人聚合各状态的任务数量。"""
        query = select(Task.assigned_to, Task.status, func.count())
        if user_id:
            query = query.where(Task.assigned_to == user_id)
        query = query.group_by(Task.assigned_to, Task.status)
        result = await db.execute(query)

        data: Dict[str, Dict[str, int]] = {}
        for uid, status, cnt in result.all():
            if uid is None:
                continue
            data.setdefault(uid, {})[status] = cnt
        return data

    def _build_stats(
        self, user: dict, ann_counts: Dict[str, int], task_counts: Dict[str, int]
    ) -> dict:
        approved = ann_counts.get("approved", 0)
        rejected = ann_counts.get("rejected", 0)
        reviewed = approved + rejected
        accuracy_rate = round(approved / reviewed * 100, 1) if reviewed else None

        return {
            "user_id": user["id"],
            "username": user["username"],
            "full_name": user.get("full_name"),
            "role": user.get("role"),
            # 标注统计
            "annotation_total": sum(ann_counts.values()),
            "annotation_approved": approved,
            "annotation_rejected": rejected,
            "annotation_pending": ann_counts.get("submitted", 0)
            + ann_counts.get("pending_final", 0),
            "annotation_draft": ann_counts.get("draft", 0),
            "accuracy_rate": accuracy_rate,
            # 任务统计
            "task_total": sum(task_counts.values()),
            "task_completed": task_counts.get("completed", 0),
            "task_in_progress": task_counts.get("pending", 0)
            + task_counts.get("running", 0)
            + task_counts.get("paused", 0),
            "task_failed": task_counts.get("failed", 0),
        }
