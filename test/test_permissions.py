# -*- coding: utf-8 -*-
"""RBAC 权限模块单元测试：权限码常量 / has_permission / require_permission 工厂。"""
import os
import sys

import pytest
from fastapi import HTTPException

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.core.permissions import (
    ALL_PERMISSIONS,
    PERMISSION_DESCRIPTIONS,
    ADMIN_ROLE,
    has_permission,
    has_any_permission,
    require_permission,
    require_any_permission,
)


def test_permission_constants_complete():
    assert len(ALL_PERMISSIONS) == 10
    assert len(PERMISSION_DESCRIPTIONS) == 10
    assert "document:read" in ALL_PERMISSIONS
    assert "system:audit:read" in ALL_PERMISSIONS


def test_has_permission_admin_bypass():
    assert has_permission({"role": "admin"}, "document:write") is True


def test_has_permission_all_wildcard():
    assert has_permission({"role": "annotator", "permissions": ["all"]}, "document:write") is True


def test_has_permission_exact():
    user = {"role": "annotator", "permissions": ["annotation:read"]}
    assert has_permission(user, "annotation:read") is True
    assert has_permission(user, "annotation:write") is False


def test_has_any_permission():
    user = {"role": "annotator", "permissions": ["annotation:read"]}
    assert has_any_permission(user, "document:read", "annotation:read") is True
    assert has_any_permission(user, "document:read", "task:read") is False


def test_require_permission_allowed():
    checker = require_permission("annotation:read")

    async def run():
        return await checker(current_user={"role": "annotator", "permissions": ["annotation:read"]})

    import asyncio
    assert asyncio.run(run())["permissions"] == ["annotation:read"]


def test_require_permission_denied_403():
    checker = require_permission("annotation:write")

    async def run():
        return await checker(current_user={"role": "annotator", "permissions": ["annotation:read"]})

    import asyncio
    with pytest.raises(HTTPException) as exc:
        asyncio.run(run())
    assert exc.value.status_code == 403


def test_require_any_permission_allowed():
    checker = require_any_permission("document:read", "annotation:read")

    async def run():
        return await checker(current_user={"role": "annotator", "permissions": ["annotation:read"]})

    import asyncio
    assert asyncio.run(run())["role"] == "annotator"


def test_require_any_permission_denied():
    checker = require_any_permission("document:read", "task:read")

    async def run():
        return await checker(current_user={"role": "annotator", "permissions": ["annotation:read"]})

    import asyncio
    with pytest.raises(HTTPException) as exc:
        asyncio.run(run())
    assert exc.value.status_code == 403