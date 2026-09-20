# -*- coding: utf-8 -*-
"""用户服务 DB 集成测试（SQLite 异步 session）。"""
import os
import sys

import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.models.user import User
from app.schemas.user import UserUpdate
from app.services.user_service import UserService


async def _make_user(db, username="alice", email="alice@x.com", role="annotator", is_active=True):
    u = User(username=username, email=email, password_hash="x", role=role, is_active=is_active, full_name="Alice")
    db.add(u)
    await db.flush()
    return u


@pytest.mark.asyncio
async def test_get_user_by_id(db):
    u = await _make_user(db)
    svc = UserService()
    found = await svc.get_user_by_id(db, u.id)
    assert found.username == "alice"

    assert await svc.get_user_by_id(db, "no-such-id") is None


@pytest.mark.asyncio
async def test_list_users_filters(db):
    await _make_user(db, username="alice", email="a@x.com", role="annotator")
    await _make_user(db, username="bob", email="b@x.com", role="reviewer", is_active=False)
    svc = UserService()

    users, total = await svc.list_users(db, 1, 10)
    assert total == 2

    users, total = await svc.list_users(db, 1, 10, role="annotator")
    assert total == 1 and users[0].username == "alice"

    users, total = await svc.list_users(db, 1, 10, keyword="bo")
    assert total == 1 and users[0].username == "bob"


@pytest.mark.asyncio
async def test_update_user(db):
    u = await _make_user(db)
    svc = UserService()
    updated = await svc.update_user(db, u.id, UserUpdate(full_name="Bob"))
    assert updated.full_name == "Bob"

    assert await svc.update_user(db, "no-such-id", UserUpdate(full_name="X")) is None


@pytest.mark.asyncio
async def test_update_role_and_status(db):
    u = await _make_user(db)
    svc = UserService()
    await svc.update_role(db, u.id, "admin")
    await svc.update_status(db, u.id, False)

    found = await svc.get_user_by_id(db, u.id)
    assert found.role == "admin"
    assert found.is_active is False

    assert await svc.update_role(db, "no-such-id", "admin") is None
    assert await svc.update_status(db, "no-such-id", True) is None


@pytest.mark.asyncio
async def test_delete_user(db):
    u = await _make_user(db)
    svc = UserService()
    assert await svc.delete_user(db, u.id) is True
    assert await svc.delete_user(db, u.id) is False


@pytest.mark.asyncio
async def test_list_mentionable(db):
    await _make_user(db, username="alice", email="a@x.com")
    await _make_user(db, username="bob", email="b@x.com", is_active=False)
    svc = UserService()
    result = await svc.list_mentionable(db)
    assert [r["username"] for r in result] == ["alice"]