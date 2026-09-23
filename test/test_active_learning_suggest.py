# -*- coding: utf-8 -*-
"""主动学习低置信度样本推送（GET /active-learning/suggest）DB 集成测试。

覆盖：低置信度优先排序、已标注元素排除、按文档过滤、权限校验。
"""
import os
import sys

import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.models.annotation import Annotation
from app.models.document import Document, DocumentElement, DocumentPage

from conftest import API_PREFIX

SUGGEST = f"{API_PREFIX}/active-learning/suggest"


def _make_doc(doc_id, title):
    return Document(id=doc_id, title=title, file_path=f"/tmp/{doc_id}.pdf", uploaded_by="u1")


def _make_page(page_id, doc_id, number):
    return DocumentPage(id=page_id, document_id=doc_id, page_number=number)


def _make_element(el_id, page_id, confidence, content="Perovskite solar cell", el_type="text"):
    return DocumentElement(
        id=el_id,
        page_id=page_id,
        element_type=el_type,
        bbox=[0, 0, 100, 20],
        content=content,
        confidence=confidence,
    )


async def _seed_base_sample_pool(db):
    """播种：doc1 下三个元素（confidence 0.9 / 0.2 / None），doc2 下一个元素（0.1）。"""
    db.add_all(
        [
            _make_doc("doc1", "Low Confidence Paper"),
            _make_doc("doc2", "Another Paper"),
            _make_page("page1", "doc1", 1),
            _make_page("page2", "doc2", 1),
            _make_element("el_high", "page1", 0.9),
            _make_element("el_low", "page1", 0.2),
            _make_element("el_none", "page1", None),
            _make_element("el_doc2", "page2", 0.1),
        ]
    )
    await db.commit()


@pytest.mark.asyncio
async def test_suggest_orders_by_low_confidence(db, client, token):
    await _seed_base_sample_pool(db)
    headers = token("u1", "admin")

    r = await client.get(SUGGEST, params={"top_k": 10}, headers=headers)
    assert r.status_code == 200
    body = r.json()

    assert body["strategy"] == "uncertainty"
    assert body["total"] == 4
    assert body["selected"] == 4

    # 置信度升序：0.1(any) < 0.2 < 0.5(None→0.5) < 0.9
    ordered = [x["element_id"] for x in body["results"]]
    assert ordered == ["el_doc2", "el_low", "el_none", "el_high"]
    confidences = [x["confidence"] for x in body["results"]]
    assert confidences == [0.1, 0.2, 0.5, 0.9]
    # score = 1 - confidence
    assert body["results"][0]["score"] == 0.9
    assert body["results"][0]["document_title"] == "Another Paper"


@pytest.mark.asyncio
async def test_suggest_excludes_annotated_elements(db, client, token):
    await _seed_base_sample_pool(db)
    db.add(
        Annotation(
            document_id="doc1",
            element_id="el_low",
            annotation_type="entity",
            content={"name": "Perovskite"},
            annotated_by="u1",
        )
    )
    await db.commit()

    headers = token("u1", "admin")
    r = await client.get(SUGGEST, params={"top_k": 10}, headers=headers)
    assert r.status_code == 200
    body = r.json()

    ordered = [x["element_id"] for x in body["results"]]
    assert "el_low" not in ordered
    assert body["total"] == 3


@pytest.mark.asyncio
async def test_suggest_filter_by_document(db, client, token):
    await _seed_base_sample_pool(db)
    headers = token("u1", "admin")

    r = await client.get(SUGGEST, params={"document_id": "doc1", "top_k": 10}, headers=headers)
    assert r.status_code == 200
    body = r.json()

    ordered = [x["document_id"] for x in body["results"]]
    assert set(ordered) == {"doc1"}
    assert body["total"] == 3
    assert [x["element_id"] for x in body["results"]] == ["el_low", "el_none", "el_high"]


@pytest.mark.asyncio
async def test_suggest_top_k_limit(db, client, token):
    await _seed_base_sample_pool(db)
    headers = token("u1", "admin")

    r = await client.get(SUGGEST, params={"top_k": 2}, headers=headers)
    assert r.status_code == 200
    body = r.json()

    assert body["total"] == 4
    assert body["selected"] == 2
    assert len(body["results"]) == 2
    assert body["results"][0]["rank"] == 1


@pytest.mark.asyncio
async def test_suggest_requires_annotation_read_permission(db, client, token):
    await _seed_base_sample_pool(db)
    headers = token("u2", "user")

    r = await client.get(SUGGEST, headers=headers)
    assert r.status_code == 403
