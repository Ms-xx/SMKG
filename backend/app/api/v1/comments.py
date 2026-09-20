from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.comment import CommentCreate, CommentListResponse, CommentResponse
from app.services.comment_service import CommentService

router = APIRouter()
comment_service = CommentService()


@router.post("/", response_model=CommentResponse, status_code=201)
async def create_comment(
    comment: CommentCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """对标注结果添加评论，自动解析 @提及 并触发通知。"""
    ip = request.client.host if request.client else None
    result = await comment_service.create_comment(
        db, comment.annotation_id, comment.content, comment.parent_id, current_user["user_id"], ip
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return result


@router.get("/", response_model=CommentListResponse)
async def list_comments(
    annotation_id: Optional[str] = None,
    document_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """按标注或文档聚合查询评论。"""
    items, total = await comment_service.list_comments(
        db, annotation_id, document_id, page, page_size
    )
    return CommentListResponse(items=items, total=total, page=page, page_size=page_size)


@router.delete("/{comment_id}", status_code=204)
async def delete_comment(
    comment_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request.client else None
    result = await comment_service.delete_comment(db, comment_id, current_user["user_id"], ip)
    if result is None:
        raise HTTPException(status_code=403, detail="You can only delete your own comments")
    if not result:
        raise HTTPException(status_code=404, detail="Comment not found")
