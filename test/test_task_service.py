# -*- coding: utf-8 -*-
"""任务服务 DB 集成测试：创建/分配/归属校验/状态流转/列表/终止。"""
import os
import sys

import pytest
from fastapi import HTTPException

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.models.task import Task
from app.schemas.task import TaskCreate, TaskAssign
from app.services.task_service import TaskService


async def _make_task(db, task_type="parsing", assigned_to=None, assigned_by=None, status="pending", celery_task_id=None, document_id="doc1", progress=0):
    t = Task(
        task_type=task_type, document_id=document_id, assigned_to=assigned_to,
        assigned_by=assigned_by, status=status, celery_task_id=celery_task_id, progress=progress,
    )
    db.add(t)
    await db.flush()
    return t


@pytest.mark.asyncio
async def test_create_and_get_task(db):
    svc = TaskService()
    data = TaskCreate(task_type="parsing", document_id="doc1", priority=2)
    t = await svc.create_task(db, data, user_id="u1")
    assert t.status == "pending"
    assert t.assigned_by == "u1"

    found = await svc.get_task(db, t.id)
    assert found.priority == 2
    assert await svc.get_task(db, "no-id") is None


@pytest.mark.asyncio
async def test_get_task_scoped_permission(db):
    svc = TaskService()
    t = await _make_task(db, assigned_to="owner", assigned_by="creator")

    # 非负责人/创建人访问 → 403
    with pytest.raises(HTTPException) as exc:
        await svc.get_task_scoped(db, t.id, user_id="intruder")
    assert exc.value.status_code == 403

    # 负责人可访问
    assert (await svc.get_task_scoped(db, t.id, user_id="owner")).id == t.id
    # scope_all 绕过归属校验
    assert (await svc.get_task_scoped(db, t.id, user_id="intruder", scope_all=True)).id == t.id
    # 不存在返回 None
    assert await svc.get_task_scoped(db, "no-id", "owner") is None


@pytest.mark.asyncio
async def test_assign_task(db):
    svc = TaskService()
    t = await _make_task(db)
    updated = await svc.assign_task(db, t.id, TaskAssign(assigned_to="u2", priority=5), user_id="admin")
    assert updated.assigned_to == "u2"
    assert updated.priority == 5
    assert await svc.assign_task(db, "no-id", TaskAssign(assigned_to="x"), "admin") is None


@pytest.mark.asyncio
async def test_list_tasks_filters(db):
    svc = TaskService()
    await _make_task(db, task_type="parsing", assigned_to="u1", assigned_by="a", status="pending")
    await _make_task(db, task_type="extraction", assigned_to="u2", assigned_by="b", status="completed")

    tasks, total = await svc.list_tasks(db, 1, 10)
    assert total == 2

    tasks, total = await svc.list_tasks(db, 1, 10, status="completed")
    assert total == 1 and tasks[0].task_type == "extraction"

    # 归属过滤：u1 只能看到自己负责/创建的任务
    tasks, total = await svc.list_tasks(db, 1, 10, user_id="u1")
    assert total == 1


@pytest.mark.asyncio
async def test_cancel_pause_resume(db):
    svc = TaskService()
    t = await _make_task(db, status="running")

    paused = await svc.pause_task(db, t.id)
    assert paused.status == "paused"

    resumed = await svc.resume_task(db, t.id)
    assert resumed.status == "running"

    # pause 非 running 不生效
    t2 = await _make_task(db, status="pending")
    assert (await svc.pause_task(db, t2.id)).status == "pending"

    cancelled = await svc.cancel_task(db, t.id)
    assert cancelled.status == "cancelled"

    # cancel 已完成任务不生效
    t3 = await _make_task(db, status="completed")
    assert (await svc.cancel_task(db, t3.id)).status == "completed"


@pytest.mark.asyncio
async def test_sync_progress_no_celery(db):
    svc = TaskService()
    t = await _make_task(db, status="pending")
    out = await svc.sync_task_progress(db, t.id)
    assert out["status"] == "pending"

    out = await svc.sync_task_progress(db, "no-id")
    assert out["status"] is None


@pytest.mark.asyncio
async def test_retry_task_errors(db, monkeypatch):
    svc = TaskService()

    # 非 failed/cancelled 状态
    t1 = await _make_task(db, status="pending")
    assert (await svc.retry_task(db, t1.id))["error"].startswith("只能重试")

    # failed 但无关联文档
    t2 = await _make_task(db, status="failed", document_id=None)
    assert (await svc.retry_task(db, t2.id))["error"].startswith("该任务没有关联文档")

    # failed 有文档但 Celery 未运行：强制 .delay() 抛异常
    from app.workers.parsing_tasks import parse_document_task

    def boom(document_id):
        raise RuntimeError("broker unreachable")

    monkeypatch.setattr(parse_document_task, "delay", boom)
    t3 = await _make_task(db, status="failed", document_id="doc1")
    assert (await svc.retry_task(db, t3.id))["error"] == "Celery 未运行，无法重试"

    assert await svc.retry_task(db, "no-id") is None


@pytest.mark.asyncio
async def test_terminate_task(db):
    svc = TaskService()
    t = await _make_task(db)
    result = await svc.terminate_task(db, t.id)
    assert result["message"] == "任务已终止并删除"
    assert await svc.get_task(db, t.id) is None

    assert await svc.terminate_task(db, "no-id") is None