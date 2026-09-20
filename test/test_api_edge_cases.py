# -*- coding: utf-8 -*-
"""API 边界用例：tasks/users 的 404 分支，以及 database.get_db_context。"""
import pytest

from conftest import API_PREFIX


@pytest.mark.asyncio
async def test_task_endpoints_not_found(client, token):
    headers = token("u1", "admin")
    r = await client.post(f"{API_PREFIX}/tasks/no-id/assign", json={"assigned_to": "x"}, headers=headers)
    assert r.status_code == 404
    r = await client.get(f"{API_PREFIX}/tasks/no-id/progress", headers=headers)
    assert r.status_code == 404
    r = await client.post(f"{API_PREFIX}/tasks/no-id/cancel", headers=headers)
    assert r.status_code == 404
    r = await client.post(f"{API_PREFIX}/tasks/no-id/pause", headers=headers)
    assert r.status_code == 404
    r = await client.post(f"{API_PREFIX}/tasks/no-id/resume", headers=headers)
    assert r.status_code == 404
    r = await client.delete(f"{API_PREFIX}/tasks/no-id/terminate", headers=headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_admin_manage_nonexistent_user(client, token):
    admin = token("admin-1", "admin")
    r = await client.get(f"{API_PREFIX}/users/no-id", headers=admin)
    assert r.status_code == 404

    r = await client.put(f"{API_PREFIX}/users/no-id", json={"full_name": "X"}, headers=admin)
    assert r.status_code == 404

    r = await client.put(f"{API_PREFIX}/users/no-id/role", params={"role": "annotator"}, headers=admin)
    assert r.status_code == 404

    r = await client.put(f"{API_PREFIX}/users/no-id/status", params={"is_active": "false"}, headers=admin)
    assert r.status_code == 404


def test_get_db_context(monkeypatch):
    from app.core import database

    class _FakeSession:
        def __init__(self):
            self.committed = False
            self.closed = False

        def commit(self):
            self.committed = True

        def rollback(self):
            pass

        def close(self):
            self.closed = True

    # 正常提交
    s1 = _FakeSession()
    monkeypatch.setattr(database, "sync_session", lambda: s1)
    with database.get_db_context() as session:
        assert session is s1
    assert s1.committed is True
    assert s1.closed is True

    # 异常回滚
    class _FailingSession(_FakeSession):
        def commit(self):
            raise RuntimeError("boom")

        def rollback(self):
            self.rolled_back = True

    s2 = _FailingSession()
    monkeypatch.setattr(database, "sync_session", lambda: s2)
    with pytest.raises(RuntimeError):
        with database.get_db_context():
            raise RuntimeError("inner")
    assert s2.rolled_back is True