# -*- coding: utf-8 -*-
"""
document_service 单元测试
覆盖：上传、查询、列表、更新、删除（MinIO 方法已 mock）
"""
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
    """让 MinioClient 的上传/删除变成 no-op，避免依赖真实 MinIO。"""
    monkeypatch.setattr(
        MinioClient,
        "upload_file",
        lambda self, object_name, data, content_type="application/pdf": object_name,
    )
    monkeypatch.setattr(MinioClient, "delete_file", lambda self, object_name: None)


@pytest.mark.asyncio
async def test_upload_document(db, monkeypatch):
    uploaded = {}
    captured = {}

    def fake_upload(self, object_name, data, content_type="application/pdf"):
        captured["object_name"] = object_name
        captured["size"] = len(data)
        return object_name

    monkeypatch.setattr(MinioClient, "upload_file", fake_upload)

    svc = DocumentService()
    doc = await svc.upload_document(
        db, FakeUploadFile("paper.pdf", b"hello-pdf"), "My Paper", "user-1"
    )
    await db.commit()

    assert doc.id
    assert doc.title == "My Paper"
    assert doc.status == "uploaded"
    assert doc.file_path == "original/user-1/paper.pdf"
    assert doc.file_size == len(b"hello-pdf")
    assert captured["object_name"] == "original/user-1/paper.pdf"
    assert captured["size"] == len(b"hello-pdf")


@pytest.mark.asyncio
async def test_get_document_not_found(db):
    svc = DocumentService()
    with pytest.raises(HTTPException) as exc:
        await svc.get_document(db, "nonexistent-id")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_list_documents(db, monkeypatch):
    _mock_minio(monkeypatch)
    svc = DocumentService()
    await svc.upload_document(db, FakeUploadFile("a.pdf"), "Doc A", "user-1")
    await svc.upload_document(db, FakeUploadFile("b.pdf"), "Doc B", "user-1")
    await db.commit()

    docs, total = await svc.list_documents(db, page=1, page_size=10)
    assert total == 2
    assert len(docs) == 2

    docs2, total2 = await svc.list_documents(db, page=1, page_size=10, keyword="Doc A")
    assert total2 == 1
    assert docs2[0].title == "Doc A"


@pytest.mark.asyncio
async def test_update_document(db, monkeypatch):
    _mock_minio(monkeypatch)
    svc = DocumentService()
    doc = await svc.upload_document(db, FakeUploadFile("c.pdf"), "Old Title", "user-1")
    await db.commit()

    updated = await svc.update_document(db, doc.id, DocumentUpdate(title="New Title"))
    await db.commit()
    assert updated.title == "New Title"
    assert updated.status == "uploaded"


@pytest.mark.asyncio
async def test_delete_document_cascades(db, monkeypatch):
    _mock_minio(monkeypatch)
    svc = DocumentService()
    doc = await svc.upload_document(db, FakeUploadFile("d.pdf"), "To Delete", "user-1")
    await db.commit()

    page = DocumentPage(document_id=doc.id, page_number=1)
    db.add(page)
    await db.flush()
    db.add(
        DocumentElement(
            page_id=page.id,
            element_type="text",
            bbox=[0, 0, 10, 10],
            content="hello",
        )
    )
    await db.commit()

    await svc.delete_document(db, doc.id)
    await db.commit()

    remaining_doc = (
        await db.execute(select(Document).where(Document.id == doc.id))
    ).scalar_one_or_none()
    remaining_page = (
        await db.execute(select(DocumentPage).where(DocumentPage.document_id == doc.id))
    ).scalar_one_or_none()
    remaining_elem = (
        await db.execute(
            select(DocumentElement).where(DocumentElement.page_id == page.id)
        )
    ).scalar_one_or_none()

    assert remaining_doc is None
    assert remaining_page is None
    assert remaining_elem is None