# -*- coding: utf-8 -*-
"""评论服务 DB 集成测试：创建（含 @ 提及）、列表、删除。"""
import os
import sys

import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.models.annotation import Annotation
from app.models.user import User
from app.services.comment_service import CommentService, MENTION_RE


async def _make_user(db, username, email):
    u = User(username=username, email=email, password_hash="x", role="annotator")
    db.add(u)
    await db.flush()
    return u


async def _make_annotation(db, document_id="doc1"):
    a = Annotation(document_id=document_id, annotation_type="entity", content={}, annotated_by="u1")
    db.add(a)
    await db.flush()
    return a


def test_mention_regex():
    assert MENTION_RE.findall("hi @alice and @bob_1") == ["alice", "bob_1"]
    assert MENTION_RE.findall("@中文用户 你好") == ["中文用户"]
    assert MENTION_RE.findall("no mention") == []


@pytest.mark.asyncio
async def test_create_comment_missing_annotation(db):
    svc = CommentService()
    assert await svc.create_comment(db, "no-ann", "hello", None, "u1") is None


@pytest.mark.asyncio
async def test_create_comment_with_mentions(db):
    ann = await _make_annotation(db)
    alice = await _make_user(db, "alice", "alice@x.com")
    await _make_user(db, "bob", "bob@x.com")

    svc = CommentService()
    result = await svc.create_comment(db, ann.id, "hi @alice", None, "u1")
    assert result["id"] is not None
    assert result["content"] == "hi @alice"
    assert result["mentions"] == [alice.id]
    assert result["username"] is None  # u1 不存在


@pytest.mark.asyncio
async def test_list_comments(db):
    ann = await _make_annotation(db)
    svc = CommentService()
    await svc.create_comment(db, ann.id, "first", None, "u1")
    await svc.create_comment(db, ann.id, "second", None, "u1")

    items, total = await svc.list_comments(db, annotation_id=ann.id)
    assert total == 2

    items, total = await svc.list_comments(db, document_id=ann.document_id)
    assert total == 2


@pytest.mark.asyncio
async def test_delete_comment_permissions(db):
    ann = await _make_annotation(db)
    svc = CommentService()
    c = await svc.create_comment(db, ann.id, "hi", None, "u1")

    # 非作者删除返回 None（无权限）
    assert await svc.delete_comment(db, c["id"], "u2") is None
    # 作者删除返回 True
    assert await svc.delete_comment(db, c["id"], "u1") is True
    # 已删除返回 False
    assert await svc.delete_comment(db, c["id"], "u1") is False