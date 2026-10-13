from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import DOCUMENT_READ, DOCUMENT_WRITE, require_permission
from app.services import repo_recommend_service as rrs
from app.services.repo_availability_service import check_github_online

router = APIRouter()


class RecommendRequest(BaseModel):
    local_references: List[dict] = []
    candidates: List[dict] = []


class FeedbackRequest(BaseModel):
    repo: str = Field(..., description="owner/repo")
    sentiment: str = Field("like", description="like | dislike")
    record_id: Optional[str] = None
    comment: Optional[str] = None


@router.post("/recommend")
async def recommend(
    body: RecommendRequest,
    current_user: dict = Depends(require_permission(DOCUMENT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """复现性优先推荐：相关性(步骤8) + 开源复现性(star) + 用户反馈加权排序，并持久化推荐记录。"""
    feedback = await rrs.aggregate_repo_feedback(db)
    ranked = rrs.recommend_ranked(
        body.local_references, body.candidates, feedback=feedback
    )
    online = any(
        r.get("source") == "online" for c in ranked for r in (c.get("repos") or [])
    )
    persisted: list[dict] = []
    for item in ranked:
        persisted.append(
            await rrs.persist_record(
                db,
                {
                    "user_id": current_user["user_id"],
                    "title": item.get("title") or "",
                    "correlation_score": item.get("correlation_score"),
                    "reproducibility_score": item.get("reproducibility_score"),
                    "feedback_score": item.get("feedback_score"),
                    "total_score": item.get("total_score"),
                    "repos": item.get("repos") or [],
                    "reason": item.get("reason"),
                    "backend": "builtin",
                },
            )
        )
    await db.commit()
    return {
        "backend": "builtin",
        "github_online": True if online else False,
        "count": len(ranked),
        "recommendations": ranked,
        "records": persisted,
    }


@router.post("/feedback")
async def feedback(
    body: FeedbackRequest,
    current_user: dict = Depends(require_permission(DOCUMENT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    """点赞/踩互动（幂等 upsert）：记录对某开源仓库可复现性的偏好，参与后续排序。"""
    try:
        row = await rrs.upsert_feedback(
            db,
            user_id=current_user["user_id"],
            repo=body.repo,
            sentiment=body.sentiment,
            record_id=body.record_id,
            comment=body.comment,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    await db.commit()
    return {"ok": True, "feedback": row}


@router.get("/online")
async def online_probe(current_user: dict = Depends(require_permission(DOCUMENT_READ))):
    """GitHub 在线抓取可用性探测（用于前端如实标注「在线/离线降级」）。"""
    return {"github_online": check_github_online()}


@router.get("/records")
async def records(
    limit: int = 100,
    current_user: dict = Depends(require_permission(DOCUMENT_READ)),
    db: AsyncSession = Depends(get_db),
):
    return {
        "backend": "builtin",
        "count": len(await rrs.list_records(db, limit)),
        "items": await rrs.list_records(db, limit),
    }


@router.get("/feedback")
async def feedback_list(
    current_user: dict = Depends(require_permission(DOCUMENT_READ)),
    db: AsyncSession = Depends(get_db),
):
    return {
        "backend": "builtin",
        "count": len(await rrs.list_feedback(db)),
        "items": await rrs.list_feedback(db),
    }
