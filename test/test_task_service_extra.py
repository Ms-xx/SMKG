# -*- coding: utf-8 -*-
"""task_service 补充测试：Celery 状态同步、revoke、重试成功、未知类型等分支。"""
import pytest

from app.models.task import Task
from app.schemas.task import TaskAssign
from app.services.task_service import TaskService


async def _make_task(db, task_type="parsing", assigned_to=None, assigned_by=None,
                     status="pending", celery_task_id=None, document_id="doc1", progress=0):
    t = Task(
        task_type=task_type, document_id=document_id, assigned_to=assigned_to,
        assigned_by=assigned_by, status=status, celery_task_id=celery_task_id, progress=progress,
    )
    db.add(t)
    await db.flush()
    await db.refresh(t)
    return t


@pytest.mark.asyncio
async def test_get_task_with_celery_status(db, monkeypatch):
    svc = TaskService()
    t1 = await _make_task(db)  # 无 celery_task_id
    r = await svc.get_task_with_celery_status(db, t1.id)
    assert r["task"].id == t1.id
    assert r["celery_status"] is None

    monkeypatch.setattr(
        TaskService, "_get_celery_task_status",
        lambda self, cid: {"state": "SUCCESS", "info": {}},
    )
    t2 = await _make_task(db, celery_task_id="celery-1")
    r = await svc.get_task_with_celery_status(db, t2.id)
    assert r["celery_status"]["state"] == "SUCCESS"


@pytest.mark.asyncio
async def test_sync_task_progress_states(db, monkeypatch):
    svc = TaskService()

    # PROGRESS → running
    monkeypatch.setattr(TaskService, "_get_celery_task_status",
                        lambda self, cid: {"state": "PROGRESS", "info": {"progress": 42}})
    t = await _make_task(db, status="pending", celery_task_id="c1")
    out = await svc.sync_task_progress(db, t.id)
    assert out["status"] == "running"
    assert out["progress"] == 42

    # SUCCESS → completed
    monkeypatch.setattr(TaskService, "_get_celery_task_status",
                        lambda self, cid: {"state": "SUCCESS", "info": {}})
    t2 = await _make_task(db, status="running", celery_task_id="c2")
    out = await svc.sync_task_progress(db, t2.id)
    assert out["status"] == "completed" and out["progress"] == 100

    # FAILURE → failed
    monkeypatch.setattr(TaskService, "_get_celery_task_status",
                        lambda self, cid: {"state": "FAILURE", "info": "boom"})
    t3 = await _make_task(db, status="running", celery_task_id="c3")
    out = await svc.sync_task_progress(db, t3.id)
    assert out["status"] == "failed"

    # REVOKED → cancelled
    monkeypatch.setattr(TaskService, "_get_celery_task_status",
                        lambda self, cid: {"state": "REVOKED", "info": {}})
    t4 = await _make_task(db, status="running", celery_task_id="c4")
    out = await svc.sync_task_progress(db, t4.id)
    assert out["status"] == "cancelled"


@pytest.mark.asyncio
async def test_list_tasks_sync_progress(db, monkeypatch):
    svc = TaskService()
    await _make_task(db, task_type="parsing", assigned_to="u1", status="pending", celery_task_id="c1")
    monkeypatch.setattr(TaskService, "_get_celery_task_status",
                        lambda self, cid: {"state": "PROGRESS", "info": {"progress": 55}})
    tasks, total = await svc.list_tasks(db, 1, 10, sync_progress=True)
    assert total == 1
    assert tasks[0].progress == 55
    assert tasks[0].status == "running"


@pytest.mark.asyncio
async def test_cancel_pause_with_revoke(db, monkeypatch):
    svc = TaskService()
    calls = []
    monkeypatch.setattr(TaskService, "_revoke_celery_task", lambda self, cid: calls.append(cid))

    t = await _make_task(db, status="running", celery_task_id="c1")
    await svc.cancel_task(db, t.id)
    assert calls == ["c1"]
    assert (await svc.get_task(db, t.id)).status == "cancelled"

    calls.clear()
    t2 = await _make_task(db, status="running", celery_task_id="c2")
    await svc.pause_task(db, t2.id)
    assert calls == ["c2"]
    assert (await svc.get_task(db, t2.id)).status == "paused"


@pytest.mark.asyncio
async def test_retry_task_success(db, monkeypatch):
    svc = TaskService()

    class _FakeCeleryTask:
        def __init__(self, tid):
            self.id = tid

    class _FakeParse:
        def delay(self, doc_id):
            return _FakeCeleryTask("new-celery-1")

    monkeypatch.setattr("app.workers.parsing_tasks.parse_document_task", _FakeParse())
    t = await _make_task(db, status="failed", document_id="doc1", task_type="parsing")
    r = await svc.retry_task(db, t.id)
    assert r["message"] == "任务已重新提交"
    assert r["task"].celery_task_id == "new-celery-1"


@pytest.mark.asyncio
async def test_retry_task_unknown_type(db):
    svc = TaskService()
    t = await _make_task(db, status="failed", document_id="doc1", task_type="others")
    r = await svc.retry_task(db, t.id)
    assert r["error"] == "未知任务类型"


# ── Celery 状态查询（_get_celery_task_status）───────────────────────────────
def test_get_celery_task_status_query_task(monkeypatch):
    svc = TaskService()

    class _FakeInspector:
        def query_task(self, tid):
            return {"state": "SUCCESS", "info": {}}

    class _FakeControl:
        def inspect(self):
            return _FakeInspector()

    class _FakeCelery:
        control = _FakeControl()

        def AsyncResult(self, tid):
            raise AssertionError("不应走到 AsyncResult 分支")

    monkeypatch.setattr("app.core.celery_app.celery_app", _FakeCelery())
    r = svc._get_celery_task_status("t1")
    assert r["state"] == "SUCCESS"


def test_get_celery_task_status_async_result(monkeypatch):
    svc = TaskService()

    class _FakeInspector:
        def query_task(self, tid):
            return None

    class _FakeControl:
        def inspect(self):
            return _FakeInspector()

    class _FakeResult:
        state = "PENDING"

        def ready(self):
            return False

        @property
        def info(self):
            return {}

    class _FakeCelery:
        control = _FakeControl()

        def AsyncResult(self, tid):
            return _FakeResult()

    monkeypatch.setattr("app.core.celery_app.celery_app", _FakeCelery())
    r = svc._get_celery_task_status("t1")
    assert r["state"] == "PENDING"