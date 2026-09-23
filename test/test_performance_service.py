# -*- coding: utf-8 -*-
"""系统性能探测（步骤 11）测试。

覆盖：DB 探测可用、结构完整性、summary 汇总；Redis/Neo4j 不可达时优雅降级。
"""
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import pytest  # noqa: E402

from app.services.performance_service import performance_service  # noqa: E402


@pytest.mark.asyncio
async def test_check_db_available(db):
    """SQLite override 下 DB 探测应可用，Redis/Neo4j 结构完整（无论是否可达）。"""
    result = await performance_service.check(db)
    assert result["db"]["available"] is True
    assert result["db"]["latency_ms"] is not None
    assert "redis" in result and "available" in result["redis"]
    assert "neo4j" in result and "available" in result["neo4j"]


@pytest.mark.asyncio
async def test_check_summary(db):
    """summary 汇总：checked=3，且 DB 可用计数 >= 1。"""
    result = await performance_service.check(db)
    assert result["summary"]["checked"] == 3
    assert result["summary"]["available"] >= 1
    assert result["summary"]["max_latency_ms"] is not None


@pytest.mark.asyncio
async def test_performance_endpoint(client, token):
    """HTTP 端点：鉴权 + 返回探测结构。"""
    from conftest import API_PREFIX

    headers = token("u1", "admin")
    r = await client.get(f"{API_PREFIX}/system/performance", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert "db" in body and "redis" in body and "neo4j" in body and "summary" in body


@pytest.mark.asyncio
async def test_performance_endpoint_requires_auth(client):
    from conftest import API_PREFIX

    assert (await client.get(f"{API_PREFIX}/system/performance")).status_code == 401