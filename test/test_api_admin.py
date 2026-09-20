# -*- coding: utf-8 -*-
"""models / permissions / operation-logs / statistics 模块 HTTP 集成测试。"""
import pytest

from conftest import API_PREFIX


# ── models ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_model_crud(client, token):
    admin = token("admin-1", "admin")

    # 非 admin 注册模型 → 403
    r = await client.post(f"{API_PREFIX}/models/", json={
        "name": "ner-model", "version": "v1", "model_type": "ner",
    }, headers=token("u1", "user"))
    assert r.status_code == 403

    r = await client.post(f"{API_PREFIX}/models/", json={
        "name": "ner-model", "version": "v1", "model_type": "ner",
    }, headers=admin)
    assert r.status_code == 201
    mid = r.json()["id"]

    r = await client.get(f"{API_PREFIX}/models/", headers=token("u1", "user"))
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = await client.get(f"{API_PREFIX}/models/{mid}", headers=admin)
    assert r.status_code == 200
    assert r.json()["name"] == "ner-model"

    r = await client.put(f"{API_PREFIX}/models/{mid}/status", json={"is_active": True}, headers=admin)
    assert r.status_code == 200
    assert r.json()["is_active"] is True

    r = await client.delete(f"{API_PREFIX}/models/{mid}", headers=admin)
    assert r.status_code == 204

    r = await client.get(f"{API_PREFIX}/models/no-id", headers=admin)
    assert r.status_code == 404


# ── permissions ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_permissions_definitions_and_roles(client, token):
    # 我的权限
    r = await client.get(f"{API_PREFIX}/permissions/me", headers=token("u1", "annotator"))
    assert r.status_code == 200
    assert r.json()["role"] == "annotator"

    # 权限定义
    r = await client.get(f"{API_PREFIX}/permissions/definitions", headers=token("u1", "user"))
    assert r.status_code == 200
    assert r.json()["total"] >= 10

    # roles 需要系统级权限
    r = await client.get(f"{API_PREFIX}/permissions/roles", headers=token("u1", "user"))
    assert r.status_code == 403

    r = await client.get(f"{API_PREFIX}/permissions/roles", headers=token("a", "admin"))
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_permissions_role_update(client, token, db):
    from app.models.role import Role

    # 更新不存在的角色 → 404
    admin = token("a", "admin")
    r = await client.put(f"{API_PREFIX}/permissions/roles/ghost",
                         json={"permissions": ["document:read"]}, headers=admin)
    assert r.status_code == 404

    # 种子角色后更新
    db.add(Role(name="annotator", permissions=[]))
    await db.commit()
    r = await client.put(f"{API_PREFIX}/permissions/roles/annotator",
                         json={"permissions": ["annotation:read", "annotation:write", "bogus"]}, headers=admin)
    assert r.status_code == 200
    # 非法权限码被过滤
    assert "bogus" not in r.json()["permissions"]
    assert "annotation:read" in r.json()["permissions"]


@pytest.mark.asyncio
async def test_rbac_granular_permission(client, token, db):
    """非 admin 角色拥有 annotation:read 才能访问标注列表。"""
    from app.models.role import Role

    db.add(Role(name="reviewer", permissions=["annotation:read"]))
    await db.commit()

    # 具备权限 → 200
    r = await client.get(f"{API_PREFIX}/annotations/",
                         params={"document_id": "doc1"},
                         headers=token("u1", "reviewer"))
    assert r.status_code == 200

    # 不具备 task:read → 403
    r = await client.get(f"{API_PREFIX}/tasks/", headers=token("u2", "reviewer"))
    assert r.status_code == 403


# ── operation-logs / statistics ──────────────────────────

@pytest.mark.asyncio
async def test_operation_logs_permission(client, token):
    r = await client.get(f"{API_PREFIX}/operation-logs/", headers=token("u1", "user"))
    assert r.status_code == 403

    r = await client.get(f"{API_PREFIX}/operation-logs/", headers=token("a", "admin"))
    assert r.status_code == 200
    assert r.json()["total"] == 0


@pytest.mark.asyncio
async def test_statistics(client, token):
    r = await client.get(f"{API_PREFIX}/statistics/personal", headers=token("u1", "user"))
    assert r.status_code == 200
    assert r.json()["annotation_total"] == 0

    r = await client.get(f"{API_PREFIX}/statistics/team", headers=token("u1", "user"))
    assert r.status_code == 200
    assert "items" in r.json()