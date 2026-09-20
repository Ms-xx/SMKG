# -*- coding: utf-8 -*-
"""通知服务 DB 集成测试。"""
import os
import sys

import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.models.comment import Notification
from app.models.user import User
from app.services.notification_service import NotificationService


async def _make_user(db, username="sender", user_id_suffix=""):
    u = User(username=username, email=f"{username}{user_id_suffix}@x.com", password_hash="x", role="annotator")
    db.add(u)
    await db.flush()
    return u


@pytest.mark.asyncio
async def test_unread_count_and_mark(db):
    svc = NotificationService()
    db.add(Notification(user_id="u1", type="mention", title="t", is_read=False))
    db.add(Notification(user_id="u1", type="mention", title="t2", is_read=True))
    db.add(Notification(user_id="u1", type="mention", title="t3", is_read=False))
    await db.flush()

    assert await svc.unread_count(db, "u1") == 2

    items, total, unread = await svc.list_notifications(db, "u1")
    assert total == 3 and unread == 2

    items, total, unread = await svc.list_notifications(db, "u1", unread_only=True)
    assert total == 2


@pytest.mark.asyncio
async def test_mark_read_and_all_read(db):
    svc = NotificationService()
    n1 = Notification(user_id="u1", is_read=False)
    n2 = Notification(user_id="u1", is_read=False)
    db.add_all([n1, n2])
    await db.flush()

    assert await svc.mark_read(db, n1.id, "u1") is True
    assert await svc.mark_read(db, "no-id", "u1") is False

    # 标记全部已读（n1 已读，n2 未读）
    assert await svc.mark_all_read(db, "u1") == 1
    assert await svc.unread_count(db, "u1") == 0


@pytest.mark.asyncio
async def test_list_notifications_sender_name(db):
    u = await _make_user(db, username="sender")
    db.add(Notification(user_id="u1", sender_id=u.id, type="mention"))
    await db.flush()

    svc = NotificationService()
    items, total, unread = await svc.list_notifications(db, "u1")
    assert items[0]["sender_name"] == "sender"