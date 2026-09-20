# -*- coding: utf-8 -*-
"""
测试「上传 → 解析 → 结果入库」闭环
- 用 DocumentService.upload_document 真实上传到 MinIO 并写 Document 记录
- 用 Celery eager 模式执行 parse_document_task（真实 MinIO 下载 + PyMuPDF/pdfplumber 解析 + 写库）
- 校验 document_pages / document_elements 生成结果

用法：python test/test_upload_parse_loop.py
（Celery eager 模式下任务在同进程执行，无需单独起 worker）
"""
import asyncio
import os
import sys

# 将 backend 加入 sys.path 以便 import app.*
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, BACKEND_DIR)

import fitz  # PyMuPDF

from app.core.celery_app import celery_app
from app.services.document_service import DocumentService
from app.workers.parsing_tasks import parse_document_task
from app.core.database import async_session, get_db_context
from app.models.document import Document, DocumentPage, DocumentElement
from sqlalchemy import select, func

# 自包含样例 PDF（带文本层，保证 PyMuPDF 能提取到文本）
SAMPLE_PDF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_text.pdf")


def ensure_sample_pdf(path: str, pages: int = 3) -> None:
    """生成带文本层的样例 PDF（首次运行生成，之后复用）。"""
    if os.path.exists(path):
        return
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        lines = [
            f"Test Document - Page {i + 1}",
            "This is a generated sample PDF used to verify the",
            "upload -> parse -> persist pipeline end-to-end.",
            "",
            "It contains a real text layer so PyMuPDF can extract",
            "text and write DocumentElement rows into the database.",
        ]
        y = 72.0
        for line in lines:
            page.insert_text((72.0, y), line, fontsize=12)
            y += 24.0
    doc.save(path)
    doc.close()


class FakeUploadFile:
    def __init__(self, filename, content, content_type="application/pdf"):
        self.filename = filename
        self.content = content
        self.content_type = content_type

    async def read(self):
        return self.content


async def main():
    ensure_sample_pdf(SAMPLE_PDF)
    content = open(SAMPLE_PDF, "rb").read()
    print("[info] 样例 PDF 大小:", len(content), "bytes")

    # 1) 上传
    svc = DocumentService()
    fake_file = FakeUploadFile("loop_test.pdf", content)

    with get_db_context() as db:
        from app.models.user import User
        admin_uid = db.execute(
            select(User.id).where(User.username == "admin")
        ).scalar_one()

    async with async_session() as db:
        doc = await svc.upload_document(db, fake_file, "loop_test", admin_uid)
        doc_id = doc.id
        await db.commit()
    print("[ok] upload -> document_id =", doc_id)

    # 2) 解析（Celery eager 模式执行真实任务）
    celery_app.conf.update(task_always_eager=True, task_eager_propagates=True)
    eager = parse_document_task.delay(doc_id)
    result = eager.result
    print("[ok] parse task result =", result)

    # 3) 校验入库结果
    with get_db_context() as db:
        doc = db.execute(select(Document).where(Document.id == doc_id)).scalar_one()
        pages = db.execute(
            select(DocumentPage).where(DocumentPage.document_id == doc_id)
        ).scalars().all()
        page_ids = [p.id for p in pages]
        text_cnt = 0
        table_cnt = 0
        if page_ids:
            text_cnt = db.execute(
                select(func.count()).where(
                    DocumentElement.page_id.in_(page_ids),
                    DocumentElement.element_type == "text",
                )
            ).scalar_one()
            table_cnt = db.execute(
                select(func.count()).where(
                    DocumentElement.page_id.in_(page_ids),
                    DocumentElement.element_type == "table",
                )
            ).scalar_one()

        print("-" * 50)
        print(f"document.status    = {doc.status}")
        print(f"document.page_count= {doc.page_count}")
        print(f"document.title     = {doc.title!r}")
        print(f"pages 记录数       = {len(pages)}")
        print(f"text 元素数        = {text_cnt}")
        print(f"table 元素数       = {table_cnt}")
        print("-" * 50)

        ok = (doc.status == "parsed") and (len(pages) > 0) and (text_cnt > 0)
        print("[PASS] 上传→解析→入库 闭环打通" if ok else "[FAIL] 闭环未完全打通")

        # 清理测试数据（便于重复运行）
        if page_ids:
            db.execute(
                DocumentElement.__table__.delete().where(
                    DocumentElement.page_id.in_(page_ids)
                )
            )
        db.execute(
            DocumentPage.__table__.delete().where(
                DocumentPage.document_id == doc_id
            )
        )
        db.execute(Document.__table__.delete().where(Document.id == doc_id))
        db.commit()
        print("[info] 已清理测试数据 document_id =", doc_id)


if __name__ == "__main__":
    asyncio.run(main())