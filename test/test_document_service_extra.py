# -*- coding: utf-8 -*-
"""document_service 补充测试：归属校验、状态过滤、触发解析、页面元素。"""
import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.services.document_service import DocumentService
from app.schemas.document import DocumentUpdate
from app.models.document import Document, DocumentPage, DocumentElement
from app.utils.minio_client import MinioClient


class FakeUploadFile:
    def __init__(self, filename, content=b"fake-pdf-body"):
        self.filename = filename
        self.content = content
        self.content_type = "application/pdf"

    async def read(self):
        return self.content


def _mock_minio(monkeypatch):
    monkeypatch.setattr(
        MinioClient, "upload_file",
        lambda self, object_name, data, content_type="application/pdf": object_name,
    )
    monkeypatch.setattr(MinioClient, "delete_file", lambda self, object_name: None)


@pytest.mark.asyncio
async def test_get_document_forbidden(db, monkeypatch):
    _mock_minio(monkeypatch)
    svc = DocumentService()
    doc = await svc.upload_document(db, FakeUploadFile("a.pdf"), "T", "owner")
    await db.commit()

    with pytest.raises(HTTPException) as exc:
        await svc.get_document(db, doc.id, user_id="intruder")
    assert exc.value.status_code == 403

    # scope_all 绕过归属校验
    assert (await svc.get_document(db, doc.id, user_id="intruder", scope_all=True)).id == doc.id


@pytest.mark.asyncio
async def test_list_documents_status_and_scope(db, monkeypatch):
    _mock_minio(monkeypatch)
    svc = DocumentService()
    await svc.upload_document(db, FakeUploadFile("a.pdf"), "A", "u1")
    d2 = await svc.upload_document(db, FakeUploadFile("b.pdf"), "B", "u1")
    await db.commit()
    d2.status = "parsed"
    await db.commit()

    docs, total = await svc.list_documents(db, 1, 10, status="parsed")
    assert total == 1 and docs[0].title == "B"

    # 归属过滤：other 看不到任何文档
    docs, total = await svc.list_documents(db, 1, 10, user_id="other")
    assert total == 0


@pytest.mark.asyncio
async def test_trigger_parsing_already_parsing(db, monkeypatch):
    _mock_minio(monkeypatch)
    svc = DocumentService()
    doc = await svc.upload_document(db, FakeUploadFile("a.pdf"), "T", "u1")
    await db.commit()
    doc.status = "parsing"
    await db.commit()

    with pytest.raises(HTTPException) as exc:
        await svc.trigger_parsing(db, doc.id, "u1")
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_trigger_parsing_invalid_status(db, monkeypatch):
    _mock_minio(monkeypatch)
    svc = DocumentService()
    doc = await svc.upload_document(db, FakeUploadFile("a.pdf"), "T", "u1")
    await db.commit()
    doc.status = "parsed"
    await db.commit()

    with pytest.raises(HTTPException) as exc:
        await svc.trigger_parsing(db, doc.id, "u1")
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_trigger_parsing_celery_success(db, monkeypatch):
    _mock_minio(monkeypatch)
    svc = DocumentService()
    doc = await svc.upload_document(db, FakeUploadFile("a.pdf"), "T", "u1")
    await db.commit()

    class _FakeCeleryTask:
        id = "celery-123"

    class _FakeTask:
        def delay(self, doc_id):
            return _FakeCeleryTask()

    monkeypatch.setattr("app.workers.parsing_tasks.parse_document_task", _FakeTask())
    r = await svc.trigger_parsing(db, doc.id, "u1")
    assert r["status"] == "pending"
    assert r["celery_task_id"] == "celery-123"


@pytest.mark.asyncio
async def test_trigger_parsing_celery_unavailable(db, monkeypatch):
    _mock_minio(monkeypatch)
    svc = DocumentService()
    doc = await svc.upload_document(db, FakeUploadFile("a.pdf"), "T", "u1")
    await db.commit()

    class _FakeTask:
        def delay(self, doc_id):
            raise RuntimeError("broker unreachable")

    monkeypatch.setattr("app.workers.parsing_tasks.parse_document_task", _FakeTask())
    r = await svc.trigger_parsing(db, doc.id, "u1")
    assert r["status"] == "completed"

    refreshed = (
        await db.execute(select(Document).where(Document.id == doc.id))
    ).scalar_one()
    assert refreshed.status == "parsed"


@pytest.mark.asyncio
async def test_get_page_elements_not_found(db, monkeypatch):
    _mock_minio(monkeypatch)
    svc = DocumentService()
    doc = await svc.upload_document(db, FakeUploadFile("a.pdf"), "T", "u1")
    await db.commit()

    with pytest.raises(HTTPException) as exc:
        await svc.get_page_elements(db, doc.id, 1)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_page_elements_success(db, monkeypatch):
    _mock_minio(monkeypatch)
    svc = DocumentService()
    doc = await svc.upload_document(db, FakeUploadFile("a.pdf"), "T", "u1")
    await db.commit()

    page = DocumentPage(document_id=doc.id, page_number=1)
    db.add(page)
    await db.flush()
    db.add(DocumentElement(page_id=page.id, element_type="text", bbox=[0, 0, 1, 1], content="x"))
    await db.commit()

    p, elements = await svc.get_page_elements(db, doc.id, 1)
    assert p.page_number == 1
    assert len(elements) == 1