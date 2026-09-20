# -*- coding: utf-8 -*-
"""标注服务 DB 集成测试：创建/更新/提交/初审/终审/版本。"""
import os
import sys

import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.schemas.annotation import AnnotationCreate, AnnotationUpdate
from app.services.annotation_service import AnnotationService


def _create_data(document_id="doc1"):
    return AnnotationCreate(document_id=document_id, annotation_type="entity", content={"text": "material"}, confidence=0.9)


@pytest.mark.asyncio
async def test_create_and_get_annotation(db):
    svc = AnnotationService()
    ann = await svc.create_annotation(db, _create_data(), user_id="u1")
    assert ann.id is not None
    assert ann.status == "draft"
    assert ann.annotated_by == "u1"

    found = await svc.get_annotation(db, ann.id)
    assert found.document_id == "doc1"

    versions = await svc.get_versions(db, ann.id)
    assert len(versions) == 1 and versions[0].change_type == "create"


@pytest.mark.asyncio
async def test_update_annotation(db):
    svc = AnnotationService()
    ann = await svc.create_annotation(db, _create_data(), user_id="u1")
    updated = await svc.update_annotation(db, ann.id, AnnotationUpdate(content={"text": "updated"}), user_id="u1")
    assert updated.content == {"text": "updated"}
    assert await svc.update_annotation(db, "no-id", AnnotationUpdate(content={}), "u1") is None


@pytest.mark.asyncio
async def test_submit_and_reviews(db):
    svc = AnnotationService()
    ann = await svc.create_annotation(db, _create_data(), user_id="u1")

    submitted = await svc.submit_annotation(db, ann.id, "u1")
    assert submitted.status == "submitted"

    # 初审通过 → pending_final
    r1 = await svc.first_review(db, ann.id, approved=True, comment="ok", reviewer_id="r1")
    assert r1.status == "pending_final"

    # 终审通过 → approved
    r2 = await svc.final_review(db, ann.id, approved=True, comment="final ok", reviewer_id="r2")
    assert r2.status == "approved"
    assert r2.first_reviewed_by == "r1"
    assert r2.final_reviewed_by == "r2"

    # 非 submitted 状态初审返回 None
    assert await svc.first_review(db, ann.id, True, "x", "r1") is None


@pytest.mark.asyncio
async def test_reviews_reject(db):
    svc = AnnotationService()
    ann = await svc.create_annotation(db, _create_data(), user_id="u1")
    await svc.submit_annotation(db, ann.id, "u1")
    r = await svc.first_review(db, ann.id, approved=False, comment="no", reviewer_id="r1")
    assert r.status == "rejected"


@pytest.mark.asyncio
async def test_get_document_annotations(db):
    svc = AnnotationService()
    await svc.create_annotation(db, _create_data("docA"), user_id="u1")
    await svc.create_annotation(db, _create_data("docB"), user_id="u1")
    anns = await svc.get_document_annotations(db, "docA")
    assert len(anns) == 1
    assert await svc.get_versions(db, "no-id") == []