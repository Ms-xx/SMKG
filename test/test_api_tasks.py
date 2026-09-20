# -*- coding: utf-8 -*-
"""tasks 模块 HTTP 集成测试：创建/列表/详情/分配/进度/状态流转/终止。"""
import pytest

from conftest import API_PREFIX


@pytest.mark.asyncio
async def test_create_and_get_task(client, token):
    headers = token("u1", "admin")
    r = await client.post(f"{API_PREFIX}/tasks/", json={
        "task_type": "parsing", "document_id": "doc1", "priority": 2,
    }, headers=headers)
    assert r.status_code == 201
    task = r.json()
    assert task["status"] == "pending"
    assert task["priority"] == 2
    tid = task["id"]

    r = await client.get(f"{API_PREFIX}/tasks/{tid}", headers=headers)
    assert r.status_code == 200
    assert r.json()["id"] == tid

    # 不存在
    r = await client.get(f"{API_PREFIX}/tasks/no-id", headers=headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_task_permission_denied(client, token):
    r = await client.post(f"{API_PREFIX}/tasks/", json={
        "task_type": "parsing", "document_id": "doc1",
    }, headers=token("u2", "user"))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_list_tasks(client, token):
    headers = token("u1", "admin")
    await client.post(f"{API_PREFIX}/tasks/", json={"task_type": "parsing", "document_id": "d1"}, headers=headers)
    await client.post(f"{API_PREFIX}/tasks/", json={"task_type": "extraction", "document_id": "d2"}, headers=headers)

    r = await client.get(f"{API_PREFIX}/tasks/", headers=headers)
    assert r.status_code == 200
    assert r.json()["total"] == 2

    r = await client.get(f"{API_PREFIX}/tasks/", params={"task_type": "extraction"}, headers=headers)
    assert r.json()["total"] == 1


@pytest.mark.asyncio
async def test_assign_task(client, token):
    headers = token("u1", "admin")
    r = await client.post(f"{API_PREFIX}/tasks/", json={"task_type": "parsing", "document_id": "d1"}, headers=headers)
    tid = r.json()["id"]

    r = await client.post(f"{API_PREFIX}/tasks/{tid}/assign", json={"assigned_to": "u2", "priority": 5}, headers=headers)
    assert r.status_code == 200
    assert r.json()["assigned_to"] == "u2"
    assert r.json()["priority"] == 5

    r = await client.get(f"{API_PREFIX}/tasks/{tid}/progress", headers=headers)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_task_lifecycle(client, token):
    headers = token("u1", "admin")
    r = await client.post(f"{API_PREFIX}/tasks/", json={"task_type": "parsing", "document_id": "d1"}, headers=headers)
    tid = r.json()["id"]

    # pause 非 running 不生效，但接口返回 200
    r = await client.post(f"{API_PREFIX}/tasks/{tid}/pause", headers=headers)
    assert r.status_code == 200

    r = await client.post(f"{API_PREFIX}/tasks/{tid}/resume", headers=headers)
    assert r.status_code == 200

    r = await client.post(f"{API_PREFIX}/tasks/{tid}/cancel", headers=headers)
    assert r.status_code == 200

    # 终止并删除
    r = await client.delete(f"{API_PREFIX}/tasks/{tid}/terminate", headers=headers)
    assert r.status_code == 200
    assert r.json()["message"] == "任务已终止并删除"


@pytest.mark.asyncio
async def test_retry_task_errors_via_api(client, token):
    headers = token("u1", "admin")
    r = await client.post(f"{API_PREFIX}/tasks/", json={"task_type": "parsing", "document_id": "d1"}, headers=headers)
    tid = r.json()["id"]

    # pending 状态不可重试
    r = await client.post(f"{API_PREFIX}/tasks/{tid}/retry", headers=headers)
    assert r.status_code == 200
    assert r.json()["error"].startswith("只能重试")

    # 不存在的任务
    r = await client.post(f"{API_PREFIX}/tasks/no-id/retry", headers=headers)
    assert r.status_code == 404