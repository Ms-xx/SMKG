from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import (
    ANNOTATION_READ,
    ANNOTATION_REVIEW,
    ANNOTATION_WRITE,
    require_permission,
)
from app.schemas.annotation import (
    AnnotationCreate,
    AnnotationResponse,
    AnnotationUpdate,
    AnnotationVersionResponse,
    ReviewRequest,
)
from app.services.annotation_agreement_service import annotation_agreement_service
from app.services.annotation_service import AnnotationConflict, AnnotationService
from app.services.operation_log_service import OperationLogService
from app.services.realtime_service import broadcast_annotation_event, lock_manager

router = APIRouter()
annotation_service = AnnotationService()
operation_log_service = OperationLogService()


@router.post("/", response_model=AnnotationResponse, status_code=201)
async def create_annotation(
    annotation: AnnotationCreate,
    request: Request,
    current_user: dict = Depends(require_permission(ANNOTATION_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request.client else None
    result = await annotation_service.create_annotation(db, annotation, current_user["user_id"], ip)
    await broadcast_annotation_event(
        result.document_id,
        "annotation.created",
        annotation=result,
        user_id=current_user["user_id"],
    )
    return result


@router.get("/", response_model=list[AnnotationResponse])
async def list_annotations(
    document_id: Optional[str] = None,
    annotation_type: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(require_permission(ANNOTATION_READ)),
    db: AsyncSession = Depends(get_db),
):
    if document_id:
        return await annotation_service.get_document_annotations(db, document_id, status)
    return []


@router.get("/document/{document_id}", response_model=list[AnnotationResponse])
async def get_document_annotations(
    document_id: str,
    current_user: dict = Depends(require_permission(ANNOTATION_READ)),
    db: AsyncSession = Depends(get_db),
):
    return await annotation_service.get_document_annotations(db, document_id)


@router.put("/{annotation_id}", response_model=AnnotationResponse)
async def update_annotation(
    annotation_id: str,
    annotation: AnnotationUpdate,
    request: Request,
    current_user: dict = Depends(require_permission(ANNOTATION_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request.client else None
    try:
        result = await annotation_service.update_annotation(
            db, annotation_id, annotation, current_user["user_id"], ip
        )
    except AnnotationConflict:
        raise HTTPException(
            status_code=409,
            detail="标注已被他人修改，请刷新后重试",
        ) from None
    if not result:
        raise HTTPException(status_code=404, detail="Annotation not found")
    await broadcast_annotation_event(
        result.document_id,
        "annotation.updated",
        annotation=result,
        user_id=current_user["user_id"],
    )
    return result


@router.post("/{annotation_id}/submit")
async def submit_annotation(
    annotation_id: str,
    request: Request,
    current_user: dict = Depends(require_permission(ANNOTATION_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request.client else None
    result = await annotation_service.submit_annotation(
        db, annotation_id, current_user["user_id"], ip
    )
    if not result:
        raise HTTPException(status_code=404, detail="Annotation not found")
    await broadcast_annotation_event(
        result.document_id,
        "annotation.submitted",
        annotation=result,
        user_id=current_user["user_id"],
    )
    return {"message": "Annotation submitted for review"}


@router.post("/{annotation_id}/lock")
async def lock_annotation(
    annotation_id: str,
    current_user: dict = Depends(require_permission(ANNOTATION_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    """锁定标注：同一时刻仅允许一个用户编辑（Redis SET NX + TTL，可降级内存）。"""
    annotation = await annotation_service.get_annotation(db, annotation_id)
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")
    acquired = await lock_manager.acquire(annotation_id, current_user["user_id"])
    if not acquired:
        owner = await lock_manager.owner(annotation_id)
        raise HTTPException(status_code=409, detail=f"标注已被用户 {owner} 锁定")
    await broadcast_annotation_event(
        annotation.document_id,
        "annotation.locked",
        annotation_id=annotation_id,
        user_id=current_user["user_id"],
    )
    return {"locked": True, "owner": current_user["user_id"]}


@router.post("/{annotation_id}/unlock")
async def unlock_annotation(
    annotation_id: str,
    current_user: dict = Depends(require_permission(ANNOTATION_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    annotation = await annotation_service.get_annotation(db, annotation_id)
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")
    await lock_manager.release(annotation_id, current_user["user_id"])
    await broadcast_annotation_event(
        annotation.document_id,
        "annotation.unlocked",
        annotation_id=annotation_id,
        user_id=current_user["user_id"],
    )
    return {"locked": False}


@router.post("/{annotation_id}/first-review")
async def first_review_annotation(
    annotation_id: str,
    review: ReviewRequest,
    request: Request,
    current_user: dict = Depends(require_permission(ANNOTATION_REVIEW)),
    db: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request.client else None
    result = await annotation_service.first_review(
        db, annotation_id, review.approved, review.comment, current_user["user_id"], ip
    )
    if not result:
        raise HTTPException(
            status_code=409, detail="Annotation not found or not in 'submitted' state"
        )
    await broadcast_annotation_event(
        result.document_id,
        "annotation.reviewed",
        annotation=result,
        user_id=current_user["user_id"],
        extra={"review_stage": "first_review", "approved": review.approved},
    )
    return {"message": "Annotation passed/rejected in first review", "annotation": result}


@router.post("/{annotation_id}/final-review")
async def final_review_annotation(
    annotation_id: str,
    review: ReviewRequest,
    request: Request,
    current_user: dict = Depends(require_permission(ANNOTATION_REVIEW)),
    db: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request.client else None
    result = await annotation_service.final_review(
        db, annotation_id, review.approved, review.comment, current_user["user_id"], ip
    )
    if not result:
        raise HTTPException(
            status_code=409, detail="Annotation not found or not in 'pending_final' state"
        )
    await broadcast_annotation_event(
        result.document_id,
        "annotation.reviewed",
        annotation=result,
        user_id=current_user["user_id"],
        extra={"review_stage": "final_review", "approved": review.approved},
    )
    return {"message": "Annotation approved/rejected in final review", "annotation": result}


@router.get("/{annotation_id}/versions", response_model=list[AnnotationVersionResponse])
async def get_annotation_versions(
    annotation_id: str,
    current_user: dict = Depends(require_permission(ANNOTATION_READ)),
    db: AsyncSession = Depends(get_db),
):
    return await annotation_service.get_versions(db, annotation_id)


@router.delete("/{annotation_id}", status_code=204)
async def delete_annotation(
    annotation_id: str,
    request: Request,
    current_user: dict = Depends(require_permission(ANNOTATION_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    annotation = await annotation_service.get_annotation(db, annotation_id)
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")
    document_id = annotation.document_id
    await db.delete(annotation)
    ip = request.client.host if request.client else None
    await operation_log_service.log_operation(
        db,
        current_user["user_id"],
        "delete",
        "annotation",
        annotation_id,
        {"annotation_type": annotation.annotation_type, "document_id": document_id},
        ip,
    )
    await broadcast_annotation_event(
        document_id,
        "annotation.deleted",
        annotation_id=annotation_id,
        user_id=current_user["user_id"],
    )


class AgreementRequest(BaseModel):
    ratings: list[list[Any]] = Field(
        ..., description="样本 × 标注员 矩阵；单元格为类别标签，None 表示缺失"
    )
    metrics: Optional[list[str]] = Field(
        None, description="cohens | fleiss | krippendorff；不填默认全部"
    )
    krippendorff_metric: Optional[str] = Field("nominal", description="nominal | interval | ratio")


@router.post("/agreement")
async def annotation_agreement(
    body: AgreementRequest,
    current_user: dict = Depends(require_permission(ANNOTATION_READ)),
):
    """标注一致性评估：Fleiss' Kappa / Cohen's Kappa / Krippendorff's Alpha。"""
    return annotation_agreement_service.evaluate(
        ratings=body.ratings,
        metrics=body.metrics,
        krippendorff_metric=body.krippendorff_metric,
    )
