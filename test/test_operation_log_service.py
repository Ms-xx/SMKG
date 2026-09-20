# -*- coding: utf-8 -*-
"""操作日志服务 DB 集成测试。"""
import os
import sys

import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.operation_log_service import OperationLogService


@pytest.mark.asyncio
async def test_log_and_list(db):
    svc = OperationLogService()
    await svc.log_operation(db, "u1", "create", "annotation", "ann1", {"k": "v"}, "1.2.3.4")
    await svc.log_operation(db, "u2", "update", "task", "task1")
    await db.flush()

    logs, total = await svc.list_logs(db, 1, 10)
    assert total == 2

    logs, total = await svc.list_logs(db, 1, 10, action="create")
    assert total == 1 and logs[0].user_id == "u1"

    logs, total = await svc.list_logs(db, 1, 10, user_id="u2")
    assert total == 1 and logs[0].action == "update"

    logs, total = await svc.list_logs(db, 1, 10, resource_type="annotation")
    assert total == 1


@pytest.mark.asyncio
async def test_list_logs_empty(db):
    svc = OperationLogService()
    logs, total = await svc.list_logs(db, 1, 10)
    assert total == 0 and logs == []