from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.services.statistics_service import StatisticsService

router = APIRouter()
statistics_service = StatisticsService()


@router.get("/personal")
async def get_personal_stats(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """当前用户的个人工作量统计（完成量、准确率、任务完成量）。"""
    stats = await statistics_service.get_user_stats(db, current_user["user_id"])
    if stats is None:
        return {
            "user_id": current_user["user_id"],
            "username": None,
            "full_name": None,
            "role": None,
            "annotation_total": 0,
            "annotation_approved": 0,
            "annotation_rejected": 0,
            "annotation_pending": 0,
            "annotation_draft": 0,
            "accuracy_rate": None,
            "task_total": 0,
            "task_completed": 0,
            "task_in_progress": 0,
            "task_failed": 0,
        }
    return stats


@router.get("/team")
async def get_team_dashboard(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """团队看板：按用户聚合的工作量统计。"""
    return await statistics_service.get_team_dashboard(db)
