# -*- coding: utf-8 -*-
"""auth 模块 HTTP 集成测试：注册/登录/刷新/登出/当前用户/改密。"""
import pytest

from conftest import API_PREFIX


@pytest.mark.asyncio
async def test_register_and_login(client):
    r = await client.post(f"{API_PREFIX}/auth/register", json={
        "username": "alice", "email": "alice@example.com", "password": "secret123",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["username"] == "alice"
    assert body["role"] == "user"
    assert body["is_active"] is True
    assert "password_hash" not in body

    # 登录成功
    r = await client.post(f"{API_PREFIX}/auth/login", json={
        "username": "alice", "password": "secret123",
    })
    assert r.status_code == 200
    token_body = r.json()
    assert token_body["access_token"]
    assert token_body["refresh_token"]
    assert token_body["token_type"] == "bearer"

    # 密码错误
    r = await client.post(f"{API_PREFIX}/auth/login", json={
        "username": "alice", "password": "bad",
    })
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_register_duplicate_and_invalid(client):
    await client.post(f"{API_PREFIX}/auth/register", json={
        "username": "bob", "email": "bob@example.com", "password": "pw123456",
    })
    # 重复用户名
    r = await client.post(f"{API_PREFIX}/auth/register", json={
        "username": "bob", "email": "other@example.com", "password": "pw123456",
    })
    assert r.status_code == 400
    # 重复邮箱
    r = await client.post(f"{API_PREFIX}/auth/register", json={
        "username": "bob2", "email": "bob@example.com", "password": "pw123456",
    })
    assert r.status_code == 400
    # 非法邮箱
    r = await client.post(f"{API_PREFIX}/auth/register", json={
        "username": "bob3", "email": "not-an-email", "password": "pw123456",
    })
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_refresh_token_flow(client):
    r = await client.post(f"{API_PREFIX}/auth/register", json={
        "username": "carol", "email": "carol@example.com", "password": "pw123456",
    })
    login = await client.post(f"{API_PREFIX}/auth/login", json={
        "username": "carol", "password": "pw123456",
    })
    refresh = login.json()["refresh_token"]

    r = await client.post(f"{API_PREFIX}/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200
    assert r.json()["access_token"]

    # access token 不能作为 refresh token
    access = login.json()["access_token"]
    r = await client.post(f"{API_PREFIX}/auth/refresh", json={"refresh_token": access})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_and_logout(client, token):
    await client.post(f"{API_PREFIX}/auth/register", json={
        "username": "dave", "email": "dave@example.com", "password": "pw123456",
    })
    login = await client.post(f"{API_PREFIX}/auth/login", json={
        "username": "dave", "password": "pw123456",
    })
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    r = await client.get(f"{API_PREFIX}/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["username"] == "dave"

    r = await client.post(f"{API_PREFIX}/auth/logout", headers=headers)
    assert r.status_code == 200

    # 未带 token
    r = await client.get(f"{API_PREFIX}/auth/me")
    assert r.status_code == 401

    # 用户不存在
    r = await client.get(f"{API_PREFIX}/auth/me", headers=token("no-such-user", "user"))
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_change_password_validation(client, token):
    headers = token("u1", "user")

    # 缺少字段
    r = await client.post(f"{API_PREFIX}/auth/change-password", json={}, headers=headers)
    assert r.status_code == 400

    # 新密码过短
    r = await client.post(
        f"{API_PREFIX}/auth/change-password",
        json={"old_password": "old", "new_password": "123"},
        headers=headers,
    )
    assert r.status_code == 400