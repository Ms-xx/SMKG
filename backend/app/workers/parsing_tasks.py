"""
文档解析Celery任务
实现完整的PDF解析流程,包括文本提取、表格提取、图像提取、公式识别等
"""

import logging
import os
import tempfile
from dataclasses import replace

from app.core.celery_app import celery_app
from app.core.database import get_db_context
from app.models.document import Document, DocumentElement, DocumentPage
from app.models.task import Task
from app.services.deduplication_service import extract_affiliations
from app.services.latex_format import (
    SOURCE_IMAGE,
    extract_formulas_from_text,
    normalize_latex,
    to_metadata,
)
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
    """步骤 2-7：提取全部内容。

    返回 (text_result, tables, images, references, headings, figures)。
    步骤 18 补强：额外抽取标题树（字号启发式，不依赖模型）与图表/公式检测结果，
    供 `_save_parsing_results` 落库为 DocumentElement。
    """
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

    self.update_state(state="PROGRESS", meta={"progress": 80, "step": "extracting_headings"})
    # 用 getattr：注入的 mock/精简解析服务可能没有这些方法，此时静默降级
    headings = _safe_call(
        getattr(parsing_service, "extract_headings_by_fontsize", None),
        tmp_path,
        default_pages=True,
    )

    self.update_state(state="PROGRESS", meta={"progress": 83, "step": "extracting_figures"})
    figures = _safe_call(
        getattr(parsing_service, "extract_figures", None),
        tmp_path,
        default_figures=True,
    )

    self.update_state(state="PROGRESS", meta={"progress": 85, "step": "extracting_references"})
    references = parsing_service.extract_references(tmp_path)
    return text_result, tables, images, references, headings, figures


def _safe_call(func, *args, **default):
    """调用可选增强步骤：方法不存在或抛异常都降级为空结果，不影响主解析链路。"""
    if func is None:
        return (
            {"metadata": {}, "figures": []}
            if default.get("default_figures")
            else {
                "metadata": {},
                "pages": [],
            }
        )
    try:
        return func(*args)
    except Exception as e:  # noqa: BLE001
        logger.warning("可选解析步骤 %s 失败，已降级跳过：%s", getattr(func, "__name__", func), e)
        if default.get("default_figures"):
            return {"metadata": {}, "figures": []}
        return {"metadata": {}, "pages": []}


def _save_heading_elements(db, document_id: str, headings: dict) -> int:
    """落库标题树元素（element_type='title'，metadata 记录层级与来源）。"""
    added = 0
    for page_info in (headings or {}).get("pages", []):
        page = _find_page(db, document_id, page_info.get("page_number"))
        if not page:
            continue
        for el in page_info.get("elements") or []:
            text = (el.get("text") or "").strip()
            if not text:
                continue
            db.add(
                DocumentElement(
                    page_id=page.id,
                    element_type="title",
                    bbox=list(el.get("bbox") or []),
                    content=text,
                    element_metadata={"level": el.get("level"), "source": "font_size_rule"},
                    confidence=0.80,
                )
            )
            added += 1
    return added


def _save_figure_elements(db, document_id: str, figures: dict) -> tuple[int, int]:
    """落库图表/公式元素（element_type='figure' | 'formula'）。

    公式统一按 LaTeX 口径落库：``content`` = 规范 LaTeX 主体（无定界符），
    ``element_metadata`` 携带 ``latex`` / ``latex_display`` / ``is_display`` /
    ``number`` / ``source`` / ``normalized`` / ``original``。

    注意：模型映射属性名为 ``element_metadata``（列名 ``metadata``）；写成
    ``metadata=...`` 会被 SQLAlchemy 当作基类 ``Base.metadata`` 而静默丢弃。

    与旧实现的区别：**公式识别失败不再被静默丢弃**——仍落库并标注
    ``normalized=false`` 与 ``error``，使"检测到公式但没能转成 LaTeX"可见可排查。

    Returns:
        ``(图表数, 公式数)``。
    """
    figure_added = 0
    formula_added = 0
    for fig in (figures or {}).get("figures", []):
        page = _find_page(db, document_id, fig.get("page_number"))
        if not page:
            continue
        cls = (fig.get("class") or "").lower()
        is_formula = "formula" in cls and "table" not in cls

        if not is_formula:
            caption = fig.get("caption")
            if not caption:
                continue
            db.add(
                DocumentElement(
                    page_id=page.id,
                    element_type="figure",
                    bbox=list(fig.get("bbox") or []),
                    content=caption,
                    element_metadata={
                        "class": fig.get("class"),
                        "confidence": fig.get("confidence"),
                    },
                    confidence=float(fig.get("confidence") or 0.7),
                )
            )
            figure_added += 1
            continue

        # 公式：此处再规范化一次（上游可能是注入的解析服务，只给了裸 latex）
        display_flag = fig.get("is_display")
        formula = normalize_latex(
            fig.get("latex") or fig.get("original") or "",
            display=display_flag if isinstance(display_flag, bool) else True,
            source=fig.get("source") or SOURCE_IMAGE,
            number=fig.get("number"),
        )
        # 上游已报告失败原因（如识别后端不可用）时以其为准——上游是根因，
        # 比本地"规范化后为空（empty）"更能说明问题，避免掩盖真实失败原因。
        if fig.get("error"):
            formula = replace(formula, error=str(fig["error"]), normalized=False)
        db.add(
            DocumentElement(
                page_id=page.id,
                element_type="formula",
                bbox=list(fig.get("bbox") or []),
                content=formula.latex,
                element_metadata={
                    "class": fig.get("class"),
                    "confidence": fig.get("confidence"),
                    **to_metadata(formula),
                },
                confidence=float(fig.get("confidence") or 0.7),
            )
        )
        formula_added += 1
    return figure_added, formula_added


def _save_text_formula_elements(db, document_id: str, text_result: dict) -> int:
    """落库正文**文本层**抽取的公式（element_type='formula'，source='text_layer'）。

    使 ``$...$`` / ``$$...$$`` / ``\\begin{equation}`` 等写法不再以裸文本留在正文中，
    而是以统一 LaTeX 形式进入公式元素，供详情页统一渲染。
    """
    added = 0
    for page_info in (text_result or {}).get("pages", []):
        formulas = extract_formulas_from_text(page_info.get("text") or "")
        if not formulas:
            continue
        page = _find_page(db, document_id, page_info.get("page_number"))
        if not page:
            continue
        for formula in formulas:
            db.add(
                DocumentElement(
                    page_id=page.id,
                    element_type="formula",
                    bbox=[],
                    content=formula.latex,
                    element_metadata={
                        "class": "text_formula",
                        "confidence": None,
                        **to_metadata(formula),
                    },
                    confidence=None,
                )
            )
            added += 1
    return added


def _find_page(db, document_id: str, page_number):
    """按文档 + 页码定位 DocumentPage（不存在返回 None）。"""
    from sqlalchemy import select

    if page_number is None:
        return None
    result = db.execute(
        select(DocumentPage).where(
            DocumentPage.document_id == document_id,
            DocumentPage.page_number == page_number,
        )
    )
    return result.scalar_one_or_none()


def _save_parsing_results(
    document_id: str,
    text_result: dict,
    tables: list,
    references: list,
    headings: dict | None = None,
    figures: dict | None = None,
) -> None:
    """步骤 6：保存解析结果到数据库（含步骤 18 补强的标题树与图表/公式元素）。"""
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
                    bbox=[0, 0, page_info["width"], page_info["height"]],
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
                    bbox=[],
                    content=None,
                    element_metadata={"data": table_info["data"]},
                    confidence=0.90,
                )
                db.add(element)

        heading_count = _save_heading_elements(db, document_id, headings or {})
        figure_count, image_formula_count = _save_figure_elements(db, document_id, figures or {})
        text_formula_count = _save_text_formula_elements(db, document_id, text_result)
        logger.info(
            "文档 %s 解析落库：标题 %s 个，图表 %s 个，公式 %s 个（图像 %s + 文本层 %s）",
            document_id,
            heading_count,
            figure_count,
            image_formula_count + text_formula_count,
            image_formula_count,
            text_formula_count,
        )

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
            (
                text_result,
                tables,
                images,
                references,
                headings,
                figures,
            ) = _extract_all_content(self, parsing_service, tmp_path, document_id, minio_client)

            self.update_state(state="PROGRESS", meta={"progress": 90, "step": "saving_results"})
            _save_parsing_results(document_id, text_result, tables, references, headings, figures)

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
