# -*- coding: utf-8 -*-
"""comments / notifications 模块 HTTP 集成测试：评论提及 + 通知流程。"""
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
async def test_comment_mention_and_notification(client, token):
    await _register(client, "author")
    await _register(client, "mentionee")
    author_headers = await _login_headers(client, "author")
    mentionee_headers = await _login_headers(client, "mentionee")

    # 创建标注（admin）
    admin = token("admin-1", "admin")
    r = await client.post(f"{API_PREFIX}/annotations/", json={
        "document_id": "doc1", "annotation_type": "entity", "content": {"name": "X"},
    }, headers=admin)
    ann_id = r.json()["id"]

    # 作者发评论并 @mentionee
    r = await client.post(f"{API_PREFIX}/comments/", json={
        "annotation_id": ann_id, "content": "@mentionee 请看一下",
    }, headers=author_headers)
    assert r.status_code == 201
    comment = r.json()
    assert comment["username"] == "author"
    assert len(comment["mentions"]) == 1
    cid = comment["id"]

    # 列表评论
    r = await client.get(f"{API_PREFIX}/comments/", params={"annotation_id": ann_id}, headers=author_headers)
    assert r.status_code == 200
    assert r.json()["total"] == 1

    # mentionee 收到通知
    r = await client.get(f"{API_PREFIX}/notifications/", headers=mentionee_headers)
    assert r.status_code == 200
    assert r.json()["unread_count"] == 1
    nid = r.json()["items"][0]["id"]

    r = await client.get(f"{API_PREFIX}/notifications/unread-count", headers=mentionee_headers)
    assert r.json()["count"] == 1

    r = await client.post(f"{API_PREFIX}/notifications/{nid}/read", headers=mentionee_headers)
    assert r.status_code == 200

    # 删除评论：他人无权限
    r = await client.delete(f"{API_PREFIX}/comments/{cid}", headers=mentionee_headers)
    assert r.status_code == 403

    # 作者删除
    r = await client.delete(f"{API_PREFIX}/comments/{cid}", headers=author_headers)
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_comment_not_found_annotation(client, token):
    await _register(client, "cuser")
    headers = await _login_headers(client, "cuser")
    r = await client.post(f"{API_PREFIX}/comments/", json={
        "annotation_id": "no-ann", "content": "hi",
    }, headers=headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_notifications_read_all(client):
    await _register(client, "nuser")
    headers = await _login_headers(client, "nuser")

    r = await client.post(f"{API_PREFIX}/notifications/read-all", headers=headers)
    assert r.status_code == 200

    # 不存在的通知
    r = await client.post(f"{API_PREFIX}/notifications/no-id/read", headers=headers)
    assert r.status_code == 404