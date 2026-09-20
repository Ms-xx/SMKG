# -*- coding: utf-8 -*-
"""权限服务 DB 集成测试。"""
import os
import sys

import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.models.role import Role
from app.services.permission_service import PermissionService


async def _make_role(db, name="annotator", permissions=None):
    r = Role(name=name, permissions=permissions or [])
    db.add(r)
    await db.flush()
    return r


@pytest.mark.asyncio
async def test_list_roles(db):
    await _make_role(db, "annotator")
    await _make_role(db, "reviewer")
    svc = PermissionService()
    roles = await svc.list_roles(db)
    assert {r.name for r in roles} == {"annotator", "reviewer"}


@pytest.mark.asyncio
async def test_get_role_by_name(db):
    await _make_role(db, "annotator")
    svc = PermissionService()
    role = await svc.get_role_by_name(db, "annotator")
    assert role is not None
    assert await svc.get_role_by_name(db, "missing") is None


@pytest.mark.asyncio
async def test_update_role_permissions_filters(db):
    await _make_role(db, "annotator", ["annotation:read"])
    svc = PermissionService()

    # 非法权限码被过滤、去重
    role = await svc.update_role_permissions(db, "annotator", ["annotation:read", "document:write", "bogus:perm", "annotation:read"])
    assert role.permissions == ["annotation:read", "document:write"]

    # 不存在角色返回 None
    assert await svc.update_role_permissions(db, "missing", []) is None