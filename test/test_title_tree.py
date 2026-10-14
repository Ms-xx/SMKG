# -*- coding: utf-8 -*-
"""标题树导航（TOC）接口集成测试：GET /documents/{id}/title-tree。"""
import pytest

from conftest import API_PREFIX

from app.models.document import DocumentElement, DocumentPage


PDF_BODY = b"%PDF-1.4 fake pdf content"


@pytest.mark.asyncio
async def _make_doc(client, token, db):
    headers = token("u1", "admin")
    r = await client.post(
        f"{API_PREFIX}/documents/upload",
        files={"file": ("t.pdf", PDF_BODY, "application/pdf")},
        headers=headers,
    )
    did = r.json()["id"]
    return did, headers


@pytest.mark.asyncio
async def test_title_tree_empty(client, token, db):
    """文档无 title 元素时返回空 tree。"""
    did, headers = await _make_doc(client, token, db)
    db.add(DocumentPage(document_id=did, page_number=1))
    await db.commit()

    r = await client.get(f"{API_PREFIX}/documents/{did}/title-tree", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["backend"] == "elements"
    assert body["tree"] == []


@pytest.mark.asyncio
async def test_title_tree_ordered(client, token, db):
    """按页/位置有序返回且 level 正确。"""
    did, headers = await _make_doc(client, token, db)

    p1 = DocumentPage(document_id=did, page_number=1)
    p2 = DocumentPage(document_id=did, page_number=2)
    db.add_all([p1, p2])
    await db.commit()
    await db.refresh(p1)
    await db.refresh(p2)

    # 在第 2 页放一个 level1、第 1 页放两个子标题，校验按页面排序 + level 口径
    db.add_all(
        [
            DocumentElement(
                page_id=p1.id,
                element_type="title",
                bbox=[0, 0, 1, 1],
                content="第一节",
                element_metadata={"level": 1},
            ),
            DocumentElement(
                page_id=p1.id,
                element_type="title",
                bbox=[0, 0, 1, 1],
                content="1.1 小节",
                element_metadata={"level": 2},
            ),
            DocumentElement(
                page_id=p2.id,
                element_type="text",  # 非 title 应被忽略
                bbox=[0, 0, 1, 1],
                content="正文",
                element_metadata={},
            ),
            DocumentElement(
                page_id=p2.id,
                element_type="title",
                bbox=[0, 0, 1, 1],
                content="引言",
                element_metadata={"level": 1},
            ),
            DocumentElement(
                page_id=p2.id,
                element_type="title",
                bbox=[0, 0, 1, 1],
                content="结论",
                element_metadata={},  # 缺 level 时降级为 3
            ),
        ]
    )
    await db.commit()

    r = await client.get(f"{API_PREFIX}/documents/{did}/title-tree", headers=headers)
    assert r.status_code == 200, r.text
    tree = r.json()["tree"]
    # 校验：按页有序（页内顺序因 element id 为随机 UUID 不保证插入序）
    pages = [t["page_number"] for t in tree]
    assert pages == sorted(pages)
    assert sorted((t["title"], t["level"]) for t in tree if t["page_number"] == 1) == sorted(
        [("第一节", 1), ("1.1 小节", 2)]
    )
    assert sorted((t["title"], t["level"]) for t in tree if t["page_number"] == 2) == sorted(
        [("引言", 1), ("结论", 3)]
    )
    assert len(tree) == 4


@pytest.mark.asyncio
async def test_title_tree_forbidden_other_user(client, token, db):
    """非上传者且无全局权限时返回 4xx。"""
    did, _ = await _make_doc(client, token, db)

    other = token("other", "user")
    r = await client.get(f"{API_PREFIX}/documents/{did}/title-tree", headers=other)
    assert r.status_code in (403, 404)