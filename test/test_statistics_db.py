# -*- coding: utf-8 -*-
"""工作量统计服务 DB 集成测试（get_user_stats / get_team_dashboard）。"""
import os
import sys

import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.models.annotation import Annotation
from app.models.task import Task
from app.models.user import User
from app.services.statistics_service import StatisticsService


async def _make_user(db, username, email):
    u = User(username=username, email=email, password_hash="x", role="annotator")
    db.add(u)
    await db.flush()
    return u


async def _make_annotation(db, user_id, status):
    a = Annotation(document_id="doc1", annotation_type="entity", content={}, annotated_by=user_id, status=status)
    db.add(a)
    await db.flush()


async def _make_task(db, user_id, status):
    t = Task(task_type="annotation", assigned_to=user_id, status=status)
    db.add(t)
    await db.flush()


@pytest.mark.asyncio
async def test_get_user_stats(db):
    u = await _make_user(db, "alice", "alice@x.com")
    await _make_annotation(db, u.id, "approved")
    await _make_annotation(db, u.id, "approved")
    await _make_annotation(db, u.id, "rejected")
    await _make_task(db, u.id, "completed")

    svc = StatisticsService()
    stats = await svc.get_user_stats(db, u.id)
    assert stats["username"] == "alice"
    assert stats["annotation_total"] == 3
    assert stats["annotation_approved"] == 2
    assert stats["annotation_rejected"] == 1
    assert stats["accuracy_rate"] == 66.7
    assert stats["task_total"] == 1
    assert stats["task_completed"] == 1

    assert await svc.get_user_stats(db, "no-id") is None


@pytest.mark.asyncio
async def test_get_team_dashboard(db):
    u1 = await _make_user(db, "alice", "alice@x.com")
    u2 = await _make_user(db, "bob", "bob@x.com")
    await _make_annotation(db, u1.id, "approved")
    await _make_annotation(db, u2.id, "approved")
    await _make_annotation(db, u2.id, "draft")
    await _make_task(db, u1.id, "pending")

    svc = StatisticsService()
    dash = await svc.get_team_dashboard(db)
    assert dash["total_users"] == 2
    # 按标注量降序：bob(2) 在 alice(1) 前
    assert dash["items"][0]["username"] == "bob"