# -*- coding: utf-8 -*-
"""核心安全模块单元测试：密码哈希 / JWT 签发与校验 / 角色依赖。"""
import os
import sys

import pytest
from fastapi import HTTPException

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    require_role,
)


def test_password_hash_and_verify():
    hashed = get_password_hash("secret123")
    assert hashed != "secret123"
    assert hashed.startswith("$2")
    assert verify_password("secret123", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_access_token_roundtrip():
    token = create_access_token({"sub": "u1", "role": "annotator"})
    payload = decode_token(token)
    assert payload["sub"] == "u1"
    assert payload["role"] == "annotator"
    assert payload["type"] == "access"
    assert "exp" in payload


def test_refresh_token_type():
    token = create_refresh_token({"sub": "u1"})
    assert decode_token(token)["type"] == "refresh"


def test_decode_invalid_token_raises_401():
    with pytest.raises(HTTPException) as exc:
        decode_token("not-a-valid-token")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_valid():
    token = create_access_token({"sub": "u1", "role": "annotator"})
    user = await get_current_user(token=token)
    assert user == {"user_id": "u1", "role": "annotator"}


@pytest.mark.asyncio
async def test_get_current_user_wrong_type():
    token = create_refresh_token({"sub": "u1"})
    with pytest.raises(HTTPException) as exc:
        await get_current_user(token=token)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_missing_sub():
    token = create_access_token({"role": "annotator"})
    with pytest.raises(HTTPException) as exc:
        await get_current_user(token=token)
    assert exc.value.status_code == 401


def test_require_role_admin_bypass():
    checker = require_role("annotator")
    import asyncio

    async def run():
        return await checker(current_user={"user_id": "u1", "role": "admin"})

    assert asyncio.run(run())["role"] == "admin"


def test_require_role_wrong_role_403():
    checker = require_role("reviewer")
    import asyncio

    async def run():
        return await checker(current_user={"user_id": "u1", "role": "annotator"})

    with pytest.raises(HTTPException) as exc:
        asyncio.run(run())
    assert exc.value.status_code == 403