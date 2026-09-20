# -*- coding: utf-8 -*-
"""
auth_service 单元测试
覆盖：创建用户、按用户名/邮箱查询、密码校验
"""
import pytest

from app.services.auth_service import AuthService
from app.schemas.user import UserCreate


@pytest.mark.asyncio
async def test_create_and_find_user(db):
    svc = AuthService()
    user = await svc.create_user(
        db,
        UserCreate(
            username="alice",
            email="alice@example.com",
            password="secret123",
            full_name="Alice",
        ),
    )
    await db.commit()

    assert user.id
    assert user.username == "alice"
    assert user.role == "user"
    assert user.is_active is True
    # 密码不应以明文保存
    assert user.password_hash != "secret123"

    found = await svc.get_user_by_username(db, "alice")
    assert found is not None
    assert found.id == user.id

    by_email = await svc.get_user_by_email(db, "alice@example.com")
    assert by_email is not None
    assert by_email.id == user.id


@pytest.mark.asyncio
async def test_authenticate_user(db):
    svc = AuthService()
    await svc.create_user(
        db,
        UserCreate(
            username="bob",
            email="bob@example.com",
            password="pw123456",
        ),
    )
    await db.commit()

    ok = await svc.authenticate_user(db, "bob", "pw123456")
    assert ok is not None
    assert ok.username == "bob"

    wrong = await svc.authenticate_user(db, "bob", "bad-pass")
    assert wrong is None

    missing = await svc.authenticate_user(db, "nobody", "pw123456")
    assert missing is None