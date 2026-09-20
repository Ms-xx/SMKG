# -*- coding: utf-8 -*-
"""documents 模块 HTTP 集成测试：上传/列表/详情/更新/删除/解析/页面元素。"""
import pytest

from conftest import API_PREFIX


PDF_BODY = b"%PDF-1.4 fake pdf content"


@pytest.mark.asyncio
async def test_upload_and_get_document(client, token):
    headers = token("u1", "admin")
    r = await client.post(
        f"{API_PREFIX}/documents/upload",
        files={"file": ("paper.pdf", PDF_BODY, "application/pdf")},
        params={"title": "My Paper"},
        headers=headers,
    )
    assert r.status_code == 201
    doc = r.json()
    assert doc["title"] == "My Paper"
    assert doc["status"] == "uploaded"
    assert doc["file_path"].endswith("paper.pdf")
    did = doc["id"]

    r = await client.get(f"{API_PREFIX}/documents/{did}", headers=headers)
    assert r.status_code == 200
    assert r.json()["id"] == did

    # 不存在
    r = await client.get(f"{API_PREFIX}/documents/no-id", headers=headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_upload_rejects_non_pdf(client, token):
    headers = token("u1", "admin")
    r = await client.post(
        f"{API_PREFIX}/documents/upload",
        files={"file": ("a.txt", b"hello", "text/plain")},
        headers=headers,
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_list_and_update_and_delete(client, token):
    headers = token("u1", "admin")
    await client.post(
        f"{API_PREFIX}/documents/upload",
        files={"file": ("a.pdf", PDF_BODY, "application/pdf")},
        params={"title": "Doc A"},
        headers=headers,
    )
    r = await client.post(
        f"{API_PREFIX}/documents/upload",
        files={"file": ("b.pdf", PDF_BODY, "application/pdf")},
        params={"title": "Doc B"},
        headers=headers,
    )
    did = r.json()["id"]

    r = await client.get(f"{API_PREFIX}/documents/", headers=headers)
    assert r.status_code == 200
    assert r.json()["total"] == 2

    # 关键字过滤
    r = await client.get(f"{API_PREFIX}/documents/", params={"keyword": "Doc A"}, headers=headers)
    assert r.json()["total"] == 1

    # 更新
    r = await client.put(f"{API_PREFIX}/documents/{did}", json={"title": "Renamed"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["title"] == "Renamed"

    # 删除
    r = await client.delete(f"{API_PREFIX}/documents/{did}", headers=headers)
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_document_permission_denied(client, token):
    headers = token("u1", "user")
    r = await client.get(f"{API_PREFIX}/documents/", headers=headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_parse_document_mock(client, token, monkeypatch):
    headers = token("u1", "admin")
    r = await client.post(
        f"{API_PREFIX}/documents/upload",
        files={"file": ("p.pdf", PDF_BODY, "application/pdf")},
        headers=headers,
    )
    did = r.json()["id"]

    # 强制 Celery 不可用，走 mock 解析路径
    def _boom(document_id):
        raise RuntimeError("broker unreachable")

    monkeypatch.setattr("app.workers.parsing_tasks.parse_document_task.delay", _boom)

    r = await client.post(f"{API_PREFIX}/documents/{did}/parse", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert "task_id" in body
    assert body["status"] == "completed"


@pytest.mark.asyncio
async def test_page_elements(client, token, db):
    from app.models.document import DocumentPage

    headers = token("u1", "admin")
    r = await client.post(
        f"{API_PREFIX}/documents/upload",
        files={"file": ("p.pdf", PDF_BODY, "application/pdf")},
        headers=headers,
    )
    did = r.json()["id"]

    # 存在页面但无元素 → 空元素列表
    db.add(DocumentPage(document_id=did, page_number=1))
    await db.commit()

    r = await client.get(f"{API_PREFIX}/documents/{did}/pages/1/elements", headers=headers)
    assert r.status_code == 200
    assert r.json()["page_number"] == 1
    assert r.json()["elements"] == []

    # 页面不存在
    r = await client.get(f"{API_PREFIX}/documents/{did}/pages/99/elements", headers=headers)
    assert r.status_code == 404