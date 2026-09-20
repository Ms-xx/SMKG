from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.annotation import Annotation, AnnotationVersion
from app.schemas.annotation import AnnotationCreate, AnnotationUpdate
from app.services.operation_log_service import OperationLogService


class AnnotationConflict(Exception):
    """标注乐观锁冲突：提交的 base_updated_at 与库中当前 updated_at 不一致。"""

    def __init__(self, annotation_id: str) -> None:
        self.annotation_id = annotation_id
        super().__init__(f"Annotation {annotation_id} was modified by someone else")


def _normalize_dt(value):
    """纳秒/时区归一化，便于乐观锁时间戳比对（DATETIME 精度为秒级）。"""
    if value is None:
        return None
    if getattr(value, "tzinfo", None) is not None:
        value = value.replace(tzinfo=None)
    return value.replace(microsecond=0)


class AnnotationService:
    def __init__(self):
        self.log_service = OperationLogService()

    async def create_annotation(
        self,
        db: AsyncSession,
        annotation_data: AnnotationCreate,
        user_id: str,
        ip_address: str = None,
    ) -> Annotation:
        annotation = Annotation(
            document_id=annotation_data.document_id,
            element_id=annotation_data.element_id,
            annotation_type=annotation_data.annotation_type,
            content=annotation_data.content,
            confidence=annotation_data.confidence,
            annotated_by=user_id,
        )
        db.add(annotation)
        await db.flush()
        await db.refresh(annotation)

        version = AnnotationVersion(
            annotation_id=annotation.id,
            content=annotation_data.content,
            changed_by=user_id,
            change_type="create",
        )
        db.add(version)

        await self.log_service.log_operation(
            db,
            user_id,
            "create",
            "annotation",
            annotation.id,
            {"annotation_type": annotation.annotation_type, "document_id": annotation.document_id},
            ip_address,
        )
        return annotation

    async def get_annotation(self, db: AsyncSession, annotation_id: str):
        result = await db.execute(select(Annotation).where(Annotation.id == annotation_id))
        return result.scalar_one_or_none()

    async def update_annotation(
        self,
        db: AsyncSession,
        annotation_id: str,
        update_data: AnnotationUpdate,
        user_id: str,
        ip_address: str = None,
    ):
        annotation = await self.get_annotation(db, annotation_id)
        if not annotation:
            return None

        # 乐观锁：提交基数与库中不一致 → 冲突（不覆盖他人修改）
        base_updated_at = update_data.base_updated_at
        if base_updated_at is not None and _normalize_dt(annotation.updated_at) != _normalize_dt(
            base_updated_at
        ):
            raise AnnotationConflict(annotation_id)

        changed_fields = update_data.model_dump(exclude_unset=True, exclude={"base_updated_at"})
        for field, value in changed_fields.items():
            setattr(annotation, field, value)

        version = AnnotationVersion(
            annotation_id=annotation.id,
            content=annotation.content,
            changed_by=user_id,
            change_type="update",
        )
        db.add(version)
        await db.flush()
        await db.refresh(annotation)

        await self.log_service.log_operation(
            db,
            user_id,
            "update",
            "annotation",
            annotation.id,
            {"fields": list(changed_fields.keys())},
            ip_address,
        )
        return annotation

    async def submit_annotation(
        self, db: AsyncSession, annotation_id: str, user_id: str, ip_address: str = None
    ):
        annotation = await self.get_annotation(db, annotation_id)
        if not annotation:
            return None
        annotation.status = "submitted"
        await db.flush()
        await db.refresh(annotation)

        await self.log_service.log_operation(
            db,
            user_id,
            "submit",
            "annotation",
            annotation.id,
            {"status": annotation.status},
            ip_address,
        )
        return annotation

    async def first_review(
        self,
        db: AsyncSession,
        annotation_id: str,
        approved: bool,
        comment: str,
        reviewer_id: str,
        ip_address: str = None,
    ):
        """初审：submitted → pending_final（通过）或 rejected（驳回）。"""
        annotation = await self.get_annotation(db, annotation_id)
        if not annotation or annotation.status != "submitted":
            return None
        annotation.status = "pending_final" if approved else "rejected"
        annotation.first_reviewed_by = reviewer_id
        annotation.first_review_comment = comment
        annotation.first_reviewed_at = datetime.utcnow()

        version = AnnotationVersion(
            annotation_id=annotation.id,
            content=annotation.content,
            changed_by=reviewer_id,
            change_type="first_review",
        )
        db.add(version)
        await db.flush()
        await db.refresh(annotation)

        await self.log_service.log_operation(
            db,
            reviewer_id,
            "first_review",
            "annotation",
            annotation.id,
            {"approved": approved, "comment": comment},
            ip_address,
        )
        return annotation

    async def final_review(
        self,
        db: AsyncSession,
        annotation_id: str,
        approved: bool,
        comment: str,
        reviewer_id: str,
        ip_address: str = None,
    ):
        """终审：pending_final → approved（通过）或 rejected（驳回）。"""
        annotation = await self.get_annotation(db, annotation_id)
        if not annotation or annotation.status != "pending_final":
            return None
        annotation.status = "approved" if approved else "rejected"
        annotation.final_reviewed_by = reviewer_id
        annotation.final_review_comment = comment
        annotation.final_reviewed_at = datetime.utcnow()

        version = AnnotationVersion(
            annotation_id=annotation.id,
            content=annotation.content,
            changed_by=reviewer_id,
            change_type="final_review",
        )
        db.add(version)
        await db.flush()
        await db.refresh(annotation)

        await self.log_service.log_operation(
            db,
            reviewer_id,
            "final_review",
            "annotation",
            annotation.id,
            {"approved": approved, "comment": comment},
            ip_address,
        )
        return annotation

    async def get_document_annotations(
        self, db: AsyncSession, document_id: str, status: str = None
    ):
        query = select(Annotation).where(Annotation.document_id == document_id)
        if status:
            query = query.where(Annotation.status == status)
        result = await db.execute(query.order_by(Annotation.created_at.desc()))
        return result.scalars().all()

    async def get_versions(self, db: AsyncSession, annotation_id: str):
        result = await db.execute(
            select(AnnotationVersion)
            .where(AnnotationVersion.annotation_id == annotation_id)
            .order_by(AnnotationVersion.created_at)
        )
        return result.scalars().all()
