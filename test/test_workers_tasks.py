# -*- coding: utf-8 -*-
"""Celery worker 任务补测：parse_document_task / build_knowledge_graph_task / extract_and_build_graph_task。

通过 FakeSession / FakeResult 隔离数据库，通过假 MinioClient / Neo4jClient / ParsingService
隔离外部服务，无需真实 MySQL/Neo4j/MinIO 与重模型加载。
"""
import contextlib
from types import SimpleNamespace

import pytest
from celery.app.task import Task


@pytest.fixture(autouse=True)
def _mock_update_state(monkeypatch):
    """Celery 任务未接入 broker 时 update_state 会因 task_id 为空而报错，直接禁用它。"""
    monkeypatch.setattr(Task, "update_state", lambda self, *a, **k: None)


class _FakeResult:
    """同时支持 scalar_one_or_none() 与 scalars().all() 两种取值方式。"""

    def __init__(self, one=None, all_=None):
        self._one = one
        self._all = all_ if all_ is not None else ([one] if one is not None else [])

    def scalar_one_or_none(self):
        return self._one

    def scalars(self):
        return self

    def all(self):
        return self._all


class _FakeSession:
    """按调用顺序依次弹出预设的 execute 结果；add/flush/refresh 维护自增 id。"""

    def __init__(self, results=()):
        self._results = list(results)
        self._counter = 0

    def execute(self, stmt):
        if self._results:
            return self._results.pop(0)
        return _FakeResult()

    def add(self, obj):
        self._counter += 1
        obj.id = f"gen-{self._counter}"
        return obj

    def flush(self):
        return None

    def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            self._counter += 1
            obj.id = f"gen-{self._counter}"

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


# ---------- parse_document_task ----------


def test_parse_document_task_success(monkeypatch):
    from app.workers import parsing_tasks as pt

    doc = SimpleNamespace(
        id="d1", file_path="f.pdf", title=None, authors=None, page_count=0, status=None
    )
    # 主流程两次 document 查询（下载前 + 保存结果时）
    session = _FakeSession([_FakeResult(one=doc), _FakeResult(one=doc)])
    monkeypatch.setattr(pt, "get_db_context", lambda: contextlib.nullcontext(session))

    class _FakeMinio:
        def download_file(self, name):
            return b"fake-pdf"

        def upload_file(self, name, data, ct="application/pdf"):
            return name

    monkeypatch.setattr(pt, "MinioClient", _FakeMinio)

    class _FakeParsing:
        def extract_text_with_pymupdf(self, path):
            return {
                "metadata": {"title": "T", "author": "A", "page_count": 1},
                "pages": [
                    {"page_number": 1, "text": "hello", "width": 100, "height": 200}
                ],
            }

        def extract_tables_with_pdfplumber(self, path):
            return []

        def extract_images(self, path, out_dir):
            return []

        def extract_references(self, path):
            return []

    monkeypatch.setattr(pt, "ParsingService", _FakeParsing)

    r = pt.parse_document_task.run("d1")
    assert r["status"] == "success"
    assert r["document_id"] == "d1"
    assert r["pages_parsed"] == 1
    assert r["tables_found"] == 0
    assert r["images_count"] == 0


def test_parse_document_task_not_found(monkeypatch):
    from app.workers import parsing_tasks as pt

    session = _FakeSession([_FakeResult(one=None)])
    monkeypatch.setattr(pt, "get_db_context", lambda: contextlib.nullcontext(session))
    monkeypatch.setattr(pt, "ParsingService", lambda: SimpleNamespace())
    monkeypatch.setattr(pt, "MinioClient", lambda: SimpleNamespace())

    r = pt.parse_document_task.run("d1")
    assert r["status"] == "failed"
    assert "not found" in r["error"]


def test_parse_document_task_download_failure(monkeypatch):
    from app.workers import parsing_tasks as pt

    doc = SimpleNamespace(id="d1", file_path="f.pdf", status=None)
    # 第一个 result 供主流程 document 查询，第二个供 except 块的失败回写
    session = _FakeSession([_FakeResult(one=doc), _FakeResult(one=doc)])
    monkeypatch.setattr(pt, "get_db_context", lambda: contextlib.nullcontext(session))
    monkeypatch.setattr(pt, "ParsingService", lambda: SimpleNamespace())

    class _FakeMinio:
        def download_file(self, name):
            raise RuntimeError("minio down")

    monkeypatch.setattr(pt, "MinioClient", _FakeMinio)

    r = pt.parse_document_task.run("d1")
    assert r["status"] == "failed"
    assert "minio down" in r["error"]


# ---------- build_knowledge_graph_task ----------


def test_build_knowledge_graph_task_not_found(monkeypatch):
    from app.workers import graph_tasks as gt

    session = _FakeSession([_FakeResult(one=None)])
    monkeypatch.setattr(gt, "get_db_context", lambda: contextlib.nullcontext(session))

    class _FakeNeo4j:
        async def execute_write(self, query, params=None):
            return True

    monkeypatch.setattr(gt, "Neo4jClient", _FakeNeo4j)

    with pytest.raises(ValueError):
        gt.build_knowledge_graph_task.run("d1")


def test_build_knowledge_graph_task_success(monkeypatch):
    from app.workers import graph_tasks as gt

    doc = SimpleNamespace(
        id="d1",
        title="T",
        authors=["A"],
        publication_date=None,
        journal="J",
        status=None,
    )
    element = SimpleNamespace(
        metadata={
            "entities": [{"type": "Material", "text": "Steel"}],
            "relations": [
                {
                    "source": "Steel",
                    "target": "Iron",
                    "relation_type": "CONTAINS",
                    "confidence": 0.8,
                    "context": "ctx",
                }
            ],
        }
    )
    page = SimpleNamespace(id="p1")
    session = _FakeSession(
        [
            _FakeResult(one=doc),  # document 查询
            _FakeResult(all_=[page]),  # pages 查询
            _FakeResult(all_=[element]),  # elements 查询
        ]
    )
    monkeypatch.setattr(gt, "get_db_context", lambda: contextlib.nullcontext(session))

    class _FakeNeo4j:
        async def execute_write(self, query, params=None):
            return True

    monkeypatch.setattr(gt, "Neo4jClient", _FakeNeo4j)

    r = gt.build_knowledge_graph_task.run("d1")
    assert r["status"] == "success"
    assert r["nodes_created"] == 1
    assert r["relations_created"] == 1
    assert r["unique_entities"] == 1
    assert r["total_relations"] == 1


# ---------- extract_and_build_graph_task ----------


def test_extract_and_build_graph_task(monkeypatch):
    from app.workers import graph_tasks as gt

    monkeypatch.setattr(
        "app.workers.extraction_tasks.extract_entities_task",
        lambda doc_id: {"status": "success", "document_id": doc_id},
    )
    monkeypatch.setattr(
        gt,
        "build_knowledge_graph_task",
        lambda doc_id: {"status": "success", "document_id": doc_id},
    )

    r = gt.extract_and_build_graph_task.run("d1")
    assert r["status"] == "success"
    assert r["extraction_result"]["status"] == "success"
    assert r["graph_result"]["status"] == "success"
