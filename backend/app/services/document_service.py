from typing import Optional

from fastapi import HTTPException, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.annotation import Annotation, AnnotationVersion
from app.models.document import Document, DocumentElement, DocumentPage
from app.models.task import Task
from app.schemas.document import DocumentUpdate
from app.utils.minio_client import MinioClient


class DocumentService:
    def __init__(self):
        self.minio_client = MinioClient()

    async def upload_document(
        self, db: AsyncSession, file: UploadFile, title: Optional[str], user_id: str
    ) -> Document:
        file_content = await file.read()
        file_size = len(file_content)
        object_name = f"original/{user_id}/{file.filename}"
        self.minio_client.upload_file(object_name, file_content, file.content_type)

        document = Document(
            title=title or file.filename,
            file_path=object_name,
            file_size=file_size,
            uploaded_by=user_id,
            status="uploaded",
        )
        db.add(document)
        await db.flush()
        await db.refresh(document)
        return document

    async def get_document(
        self, db: AsyncSession, document_id: str, user_id: str = None, scope_all: bool = False
    ):
        query = select(Document).where(Document.id == document_id)
        result = await db.execute(query)
        document = result.scalar_one_or_none()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        # 归属校验：非全局范围时仅允许文档上传者访问
        if user_id is not None and not scope_all and document.uploaded_by != user_id:
            raise HTTPException(status_code=403, detail="无权访问该文档")
        return document

    async def list_documents(
        self,
        db: AsyncSession,
        page: int,
        page_size: int,
        status: str = None,
        keyword: str = None,
        user_id: str = None,
        scope_all: bool = False,
    ):
        query = select(Document)
        if not scope_all and user_id is not None:
            query = query.where(Document.uploaded_by == user_id)
        if status:
            query = query.where(Document.status == status)
        if keyword:
            query = query.where(Document.title.ilike(f"%{keyword}%"))

        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query)

        query = (
            query.offset((page - 1) * page_size)
            .limit(page_size)
            .order_by(Document.created_at.desc())
        )
        result = await db.execute(query)
        documents = result.scalars().all()

        return documents, total

    async def update_document(
        self,
        db: AsyncSession,
        document_id: str,
        update_data: DocumentUpdate,
        user_id: str = None,
        scope_all: bool = False,
    ):
        document = await self.get_document(db, document_id, user_id, scope_all)
        for field, value in update_data.model_dump(exclude_unset=True).items():
            setattr(document, field, value)
        await db.flush()
        await db.refresh(document)
        return document

    async def delete_document(
        self, db: AsyncSession, document_id: str, user_id: str = None, scope_all: bool = False
    ):
        document = await self.get_document(db, document_id, user_id, scope_all)

        # 1. Delete annotation versions (cascade through annotations)
        ann_result = await db.execute(
            select(Annotation.id).where(Annotation.document_id == document_id)
        )
        ann_ids = [r[0] for r in ann_result.all()]
        if ann_ids:
            await db.execute(
                delete(AnnotationVersion).where(AnnotationVersion.annotation_id.in_(ann_ids))
            )

        # 2. Delete annotations
        await db.execute(delete(Annotation).where(Annotation.document_id == document_id))

        # 3. Delete tasks associated with this document
        await db.execute(delete(Task).where(Task.document_id == document_id))

        # 4. Delete document elements (through pages)
        page_result = await db.execute(
            select(DocumentPage.id).where(DocumentPage.document_id == document_id)
        )
        page_ids = [r[0] for r in page_result.all()]
        if page_ids:
            await db.execute(delete(DocumentElement).where(DocumentElement.page_id.in_(page_ids)))

        # 5. Delete document pages
        await db.execute(delete(DocumentPage).where(DocumentPage.document_id == document_id))

        # 6. Delete file from storage
        self.minio_client.delete_file(document.file_path)

        # 7. Delete document record
        await db.delete(document)

    async def trigger_parsing(
        self, db: AsyncSession, document_id: str, user_id: str, scope_all: bool = False
    ):
        document = await self.get_document(db, document_id, user_id, scope_all)

        # 允许重新解析的状态: uploaded, failed
        if document.status == "parsing":
            raise HTTPException(status_code=400, detail="文档正在解析中，请稍后再试")

        # 允许 failed 状态的文档重新解析
        if document.status not in ("uploaded", "failed"):
            raise HTTPException(
                status_code=400, detail=f"当前状态({document.status})不支持重新解析"
            )

        document.status = "parsing"
        await db.flush()

        try:
            from app.workers.parsing_tasks import parse_document_task

            celery_task = parse_document_task.delay(document_id)

            task = Task(
                task_type="parsing",
                document_id=document_id,
                status="pending",
                celery_task_id=celery_task.id,
            )
            db.add(task)
            await db.flush()
            await db.refresh(task)
            return {"task_id": task.id, "celery_task_id": celery_task.id, "status": "pending"}
        except Exception as e:
            # Celery not available, do mock parsing
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Celery unavailable, doing mock parse: {e}")

            # Simulate parsing after a delay
            task = Task(
                task_type="parsing",
                document_id=document_id,
                status="running",
                progress=0.0,
            )
            db.add(task)
            await db.flush()
            await db.refresh(task)

            # Immediately complete for demo (in real scenario, this would be a background job)
            document.status = "parsed"
            document.page_count = 1  # Mock data
            task.status = "completed"
            task.progress = 100.0

            return {"task_id": task.id, "status": "completed"}

    async def get_page_elements(self, db: AsyncSession, document_id: str, page_number: int):
        page_result = await db.execute(
            select(DocumentPage).where(
                DocumentPage.document_id == document_id,
                DocumentPage.page_number == page_number,
            )
        )
        page = page_result.scalar_one_or_none()
        if not page:
            raise HTTPException(status_code=404, detail="Page not found")

        elements_result = await db.execute(
            select(DocumentElement).where(DocumentElement.page_id == page.id)
        )
        elements = elements_result.scalars().all()
        return page, elements
