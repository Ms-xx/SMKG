# -*- coding: utf-8 -*-
"""core/dependencies 依赖注入函数测试（绕过 Depends 直接注入形参）。"""
import pytest

from app.core.dependencies import get_db_session, get_current_active_user


async def test_get_db_session_returns_session():
    stub = object()
    assert await get_db_session(session=stub) is stub


async def test_get_current_active_user_returns_user():
    stub = {"sub": "u1", "role": "user"}
    assert await get_current_active_user(current_user=stub) is stub