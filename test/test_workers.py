# -*- coding: utf-8 -*-
"""Celery worker 任务测试：mock update_state / Neo4j / MinIO，覆盖轻量任务与统计任务。"""
import pytest
from celery.app.task import Task


@pytest.fixture(autouse=True)
def _mock_update_state(monkeypatch):
    """Celery 任务未接入 broker 时 update_state 会因 task_id 为空而报错，直接禁用它。"""
    monkeypatch.setattr(Task, "update_state", lambda self, *a, **k: None)


def test_extract_entities_task():
    from app.workers.extraction_tasks import extract_entities_task

    r = extract_entities_task.run("d1")
    assert r == {"status": "success", "document_id": "d1"}


def test_build_knowledge_graph_task_trivial():
    from app.workers.extraction_tasks import build_knowledge_graph_task

    r = build_knowledge_graph_task.run("d1")
    assert r == {"status": "success", "document_id": "d1"}


def test_parse_batch_documents_task(monkeypatch):
    from app.workers.parsing_tasks import parse_batch_documents_task

    class _FakeAsyncTask:
        def __init__(self, tid):
            self.id = tid

    class _FakeParseTask:
        def delay(self, doc_id):
            return _FakeAsyncTask(f"task-{doc_id}")

    monkeypatch.setattr("app.workers.parsing_tasks.parse_document_task", _FakeParseTask())
    r = parse_batch_documents_task(["d1", "d2"])
    assert r["status"] == "submitted"
    assert r["total_documents"] == 2
    assert r["tasks"][0]["task_id"] == "task-d1"


def test_update_graph_statistics_task(monkeypatch):
    from app.utils.neo4j_client import Neo4jClient
    from app.workers.graph_tasks import update_graph_statistics_task

    async def _fake_execute_query(self, query, params=None):
        return [{"total": 5}]

    monkeypatch.setattr(Neo4jClient, "execute_query", _fake_execute_query)
    r = update_graph_statistics_task.run()
    assert r["total_nodes"] == 5
    assert r["total_relations"] == 5
    assert r["node_types"] == [{"total": 5}]
    assert r["relation_types"] == [{"total": 5}]
    assert "updated_at" in r


def test_update_graph_statistics_task_failure(monkeypatch):
    from app.utils.neo4j_client import Neo4jClient
    from app.workers.graph_tasks import update_graph_statistics_task

    async def _boom(self, query, params=None):
        raise RuntimeError("neo4j down")

    monkeypatch.setattr(Neo4jClient, "execute_query", _boom)
    r = update_graph_statistics_task.run()
    assert r["status"] == "failed"
    assert "neo4j down" in r["error"]