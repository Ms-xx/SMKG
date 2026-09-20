# -*- coding: utf-8 -*-
"""users 模块 HTTP 集成测试：列表/详情/更新/角色/状态/删除/提及。"""
import pytest

from conftest import API_PREFIX


async def _register(client, username):
    await client.post(f"{API_PREFIX}/auth/register", json={
        "username": username, "email": f"{username}@example.com", "password": "pw123456",
    })


async def _login_headers(client, username):
    login = await client.post(f"{API_PREFIX}/auth/login", json={
        "username": username, "password": "pw123456",
    })
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.asyncio
async def test_list_users_admin_only(client, token):
    await _register(client, "u1")
    await _register(client, "u2")

    # 无权限用户 → 403
    r = await client.get(f"{API_PREFIX}/users/", headers=token("x", "user"))
    assert r.status_code == 403

    # admin → 200
    r = await client.get(f"{API_PREFIX}/users/", headers=token("admin-1", "admin"))
    assert r.status_code == 200
    assert r.json()["total"] == 2

    # 过滤
    r = await client.get(f"{API_PREFIX}/users/", params={"role": "user"}, headers=token("a", "admin"))
    assert r.status_code == 200
    assert r.json()["total"] == 2


@pytest.mark.asyncio
async def test_get_and_update_own_user(client):
    await _register(client, "self")
    headers = await _login_headers(client, "self")

    r = await client.get(f"{API_PREFIX}/users/mentionable", headers=headers)
    assert r.status_code == 200

    # 获取当前用户（先拿到 id）
    me = await client.get(f"{API_PREFIX}/auth/me", headers=headers)
    uid = me.json()["id"]

    r = await client.get(f"{API_PREFIX}/users/{uid}", headers=headers)
    assert r.status_code == 200
    assert r.json()["username"] == "self"

    # 更新自己的资料
    r = await client.put(f"{API_PREFIX}/users/{uid}", json={"full_name": "Self User"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["full_name"] == "Self User"

    # 非 admin 访问他人（含不存在的 id）→ 403（先校验归属）
    r = await client.get(f"{API_PREFIX}/users/no-such-id", headers=headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_user_permission_isolation(client):
    await _register(client, "owner")
    await _register(client, "other")
    owner_headers = await _login_headers(client, "owner")
    other_headers = await _login_headers(client, "other")

    owner_me = await client.get(f"{API_PREFIX}/auth/me", headers=owner_headers)
    owner_id = owner_me.json()["id"]

    # 其他用户访问 owner 的详情 → 403
    r = await client.get(f"{API_PREFIX}/users/{owner_id}", headers=other_headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_manage_user(client, token):
    await _register(client, "victim")
    headers = await _login_headers(client, "victim")
    victim_me = await client.get(f"{API_PREFIX}/auth/me", headers=headers)
    victim_id = victim_me.json()["id"]
    admin = token("admin-1", "admin")

    # 修改角色
    r = await client.put(f"{API_PREFIX}/users/{victim_id}/role", params={"role": "annotator"}, headers=admin)
    assert r.status_code == 200
    assert r.json()["role"] == "annotator"

    # 修改状态
    r = await client.put(f"{API_PREFIX}/users/{victim_id}/status", params={"is_active": "false"}, headers=admin)
    assert r.status_code == 200
    assert r.json()["is_active"] is False

    # 删除
    r = await client.delete(f"{API_PREFIX}/users/{victim_id}", headers=admin)
    assert r.status_code == 204

    # 删除后不存在
    r = await client.delete(f"{API_PREFIX}/users/{victim_id}", headers=admin)
    assert r.status_code == 404