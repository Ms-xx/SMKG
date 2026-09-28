"""
文档解析Celery任务
实现完整的PDF解析流程,包括文本提取、表格提取、图像提取、公式识别等
"""

import json
import logging
import os
import tempfile

from app.core.celery_app import celery_app
from app.core.database import get_db_context
from app.models.document import Document, DocumentElement, DocumentPage
from app.models.task import Task
from app.services.deduplication_service import extract_affiliations
from app.services.parsing_service import ParsingService
from app.utils.minio_client import MinioClient

logger = logging.getLogger(__name__)


def _download_to_temp(document_id: str, minio_client) -> str:
    """步骤 1：下载文件到临时路径，返回 tmp_path。"""
    with get_db_context() as db:
        from sqlalchemy import select

        result = db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()

        if not document:
            raise ValueError(f"Document {document_id} not found")

        file_path = document.file_path

    file_data = minio_client.download_file(file_path)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file_data)
        tmp_path = tmp.name

    return tmp_path


def _extract_all_content(self, parsing_service, tmp_path: str, document_id: str, minio_client):
    """步骤 2-5：提取全部内容，返回 (text_result, tables, images, references)。"""
    self.update_state(state="PROGRESS", meta={"progress": 30, "step": "extracting_text"})
    text_result = parsing_service.extract_text_with_pymupdf(tmp_path)

    self.update_state(state="PROGRESS", meta={"progress": 50, "step": "extracting_tables"})
    tables = parsing_service.extract_tables_with_pdfplumber(tmp_path)

    self.update_state(state="PROGRESS", meta={"progress": 70, "step": "extracting_images"})
    with tempfile.TemporaryDirectory() as output_dir:
        images = parsing_service.extract_images(tmp_path, output_dir)

        image_paths = []
        for img_path in images:
            img_name = os.path.basename(img_path)
            with open(img_path, "rb") as _f:
                img_data = _f.read()

            minio_path = f"images/{document_id}/{img_name}"
            minio_client.upload_file(minio_path, img_data, "image/png")
            image_paths.append(minio_path)

    self.update_state(state="PROGRESS", meta={"progress": 85, "step": "extracting_references"})
    references = parsing_service.extract_references(tmp_path)
    return text_result, tables, images, references


def _save_parsing_results(
    document_id: str, text_result: dict, tables: list, references: list
) -> None:
    """步骤 6：保存解析结果到数据库。"""
    from sqlalchemy import select

    with get_db_context() as db:
        document = db.execute(
            select(Document).where(Document.id == document_id)
        ).scalar_one_or_none()

        if text_result["metadata"]:
            metadata = text_result["metadata"]
            if metadata.get("title"):
                document.title = metadata["title"]
            if metadata.get("author"):
                authors_list = [metadata["author"]]
                document.authors = authors_list

        document.page_count = text_result["metadata"]["page_count"]
        document.status = "parsed"
        document.references = references
        full_text = " ".join(p.get("text") or "" for p in text_result["pages"])
        document.affiliations = extract_affiliations(full_text)

        for page_info in text_result["pages"]:
            page = DocumentPage(
                document_id=document_id,
                page_number=page_info["page_number"],
                image_path=f"images/{document_id}/page_{page_info['page_number']}.png",
            )
            db.add(page)
            db.flush()
            db.refresh(page)

            if page_info.get("text"):
                element = DocumentElement(
                    page_id=page.id,
                    element_type="text",
                    bbox=json.dumps([0, 0, page_info["width"], page_info["height"]]),
                    content=page_info["text"],
                    confidence=0.95,
                )
                db.add(element)

        for table_info in tables:
            page_result = db.execute(
                select(DocumentPage).where(
                    DocumentPage.document_id == document_id,
                    DocumentPage.page_number == table_info["page_number"],
                )
            )
            page = page_result.scalar_one_or_none()

            if page:
                element = DocumentElement(
                    page_id=page.id,
                    element_type="table",
                    bbox=json.dumps([]),
                    content=None,
                    metadata={"data": table_info["data"]},
                    confidence=0.90,
                )
                db.add(element)

        db.commit()


def _handle_parse_failure(document_id: str, error_msg: str) -> None:
    """失败时 document + task 状态回写（两处 try/except 合并）。"""
    from sqlalchemy import select

    try:
        with get_db_context() as db:
            document = db.execute(
                select(Document).where(Document.id == document_id)
            ).scalar_one_or_none()
            if document:
                document.status = "failed"
                db.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning("解析失败后更新文档状态失败: %s", e)

    try:
        with get_db_context() as db:
            task_result = db.execute(
                select(Task)
                .where(Task.document_id == document_id, Task.task_type == "parsing")
                .order_by(Task.created_at.desc())
                .limit(1)
            )
            task = task_result.scalar_one_or_none()
            if task:
                task.status = "failed"
                task.error_message = error_msg
                db.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning("解析失败后更新任务状态失败: %s", e)


@celery_app.task(name="parse_document", bind=True, queue="parsing")
def parse_document_task(self, document_id: str):
    """
    文档解析主任务
    Args:
        document_id: 文档ID
    Returns:
        解析结果
    """
    parsing_service = ParsingService()
    minio_client = MinioClient()

    try:
        self.update_state(state="PROGRESS", meta={"progress": 10, "step": "downloading"})
        tmp_path = _download_to_temp(document_id, minio_client)

        try:
            text_result, tables, images, references = _extract_all_content(
                self, parsing_service, tmp_path, document_id, minio_client
            )

            self.update_state(state="PROGRESS", meta={"progress": 90, "step": "saving_results"})
            _save_parsing_results(document_id, text_result, tables, references)

            self.update_state(state="PROGRESS", meta={"progress": 100, "step": "completed"})

            return {
                "status": "success",
                "document_id": document_id,
                "metadata": text_result["metadata"],
                "pages_parsed": len(text_result["pages"]),
                "tables_found": len(tables),
                "images_count": len(images),
                "references_count": len(references),
            }

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    except Exception as e:
        error_msg = str(e)
        _handle_parse_failure(document_id, error_msg)

        return {
            "status": "failed",
            "document_id": document_id,
            "error": error_msg,
        }


@celery_app.task(name="parse_batch_documents", queue="parsing")
def parse_batch_documents_task(document_ids: list):
    """
    批量解析文档任务
    Args:
        document_ids: 文档ID列表
    Returns:
        批量处理结果
    """
    results = []
    for doc_id in document_ids:
        # 为每个文档创建单独的解析任务
        result = parse_document_task.delay(doc_id)
        results.append({"document_id": doc_id, "task_id": result.id})

    return {
        "status": "submitted",
        "total_documents": len(document_ids),
        "tasks": results,
    }
