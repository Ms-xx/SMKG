# -*- coding: utf-8 -*-
"""paper_data_switch 运维脚本与存储客户端扩展的单元测试。

- 纯函数（标题派生 / PDF 过滤 / 报告序列化）：无网络，可直接运行。
- mock 隔离网络：MinioClient.list_objects/remove_objects、Neo4jClient.delete_nodes_by_doc。
真实联调（MySQL/Neo4j/MinIO/HTTP）在沙箱禁止 socket，须用户本机终端执行。
"""
import json
import os
import sys

import pytest

# 使 backend/scripts 可导入（conftest 已把 backend 加入 sys.path，此处补 scripts）
_SCRIPTS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "backend", "scripts")
)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import paper_data_switch as pds  # noqa: E402


# ──────────────────────────────────────────────────────────────────────
# 纯函数测试
# ──────────────────────────────────────────────────────────────────────
class TestDeriveTitle:
    def test_strips_three_digit_prefix(self):
        assert pds.derive_title("001_eval_benchmark_survey.pdf") == "eval_benchmark_survey"

    def test_strips_last_prefix(self):
        assert pds.derive_title("197_react_b2.pdf") == "react_b2"

    def test_no_prefix_returns_stem(self):
        assert pds.derive_title("foo.pdf") == "foo"

    def test_keeps_inner_underscores(self):
        assert pds.derive_title("012_llama_firewall_v2.pdf") == "llama_firewall_v2"


class TestFilterPdfs:
    def test_matches_only_three_digit_prefix(self, tmp_path):
        for name in ("001_a.pdf", "002_b.pdf", "abc.pdf", "003c.pdf", "10_short.pdf"):
            (tmp_path / name).write_bytes(b"x")
        assert pds.filter_pdfs(str(tmp_path)) == [
            str(tmp_path / "001_a.pdf"),
            str(tmp_path / "002_b.pdf"),
        ]

    def test_empty_or_missing_dir(self, tmp_path):
        assert pds.filter_pdfs(str(tmp_path)) == []
        assert pds.filter_pdfs(str(tmp_path / "not_exist")) == []


class TestReports:
    def test_inventory_report_serializable(self, tmp_path):
        rep = pds.InventoryReport(
            started_at="2026-01-01T00:00:00",
            user_uuid="u1",
            doc_ids=["d1", "d2"],
            local_files=["a.pdf"],
            mysql_counts={"documents": 2},
            neo4j_total_nodes=10,
        )
        out = pds.write_report(rep, str(tmp_path / "inv.json"))
        assert os.path.isfile(out)
        data = json.load(open(out, encoding="utf-8"))
        assert data["doc_ids"] == ["d1", "d2"]
        assert data["mysql_counts"] == {"documents": 2}

    def test_ingest_report_counts(self):
        rep = pds.IngestReport(total=3, records=[
            pds.IngestRecord(filename="a.pdf", success=True),
            pds.IngestRecord(filename="b.pdf", success=False, error="boom"),
            pds.IngestRecord(filename="c.pdf", success=True, error="dedup(skipped)"),
        ])
        rep.ok_count = sum(1 for r in rep.records if r.success and r.error == "")
        rep.fail_count = sum(1 for r in rep.records if not r.success)
        assert rep.ok_count == 1
        assert rep.fail_count == 1


# ──────────────────────────────────────────────────────────────────────
# MinioClient mock 测试（隔离网络）
# ──────────────────────────────────────────────────────────────────────
def _fresh_minio(monkeypatch):
    pytest.importorskip("minio")
    from app.utils import minio_client as mc
    from app.utils.minio_client import MinioClient

    monkeypatch.setattr(MinioClient, "_instance", None)
    return MinioClient(), mc


def test_minio_list_objects_local_fallback(tmp_path, monkeypatch):
    client, mc = _fresh_minio(monkeypatch)
    from app.utils.minio_client import MinioClient
    monkeypatch.setattr(mc, "LOCAL_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(MinioClient, "_check_available", lambda self: False)
    (tmp_path / "original" / "u1").mkdir(parents=True)
    (tmp_path / "original" / "u1" / "a.pdf").write_bytes(b"x")
    (tmp_path / "original" / "u1" / "b.pdf").write_bytes(b"y")

    assert client.list_objects("original/u1/") == [
        "original/u1/a.pdf",
        "original/u1/b.pdf",
    ]
    assert client.list_objects("images/nope/") == []


def test_minio_remove_objects_local_idempotent(tmp_path, monkeypatch):
    client, mc = _fresh_minio(monkeypatch)
    from app.utils.minio_client import MinioClient
    monkeypatch.setattr(mc, "LOCAL_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(MinioClient, "_check_available", lambda self: False)
    (tmp_path / "original" / "u1").mkdir(parents=True)
    (tmp_path / "original" / "u1" / "a.pdf").write_bytes(b"x")
    (tmp_path / "original" / "u1" / "b.pdf").write_bytes(b"y")

    assert client.remove_objects("original/u1/") == 2
    assert not (tmp_path / "original" / "u1" / "a.pdf").exists()
    # 幂等：重复执行返回 0 且不报错
    assert client.remove_objects("original/u1/") == 0


def test_minio_list_objects_remote(tmp_path, monkeypatch):
    client, _ = _fresh_minio(monkeypatch)
    from app.utils.minio_client import MinioClient
    client._client = type(
        "FakeMinio", (), {
            "list_objects": lambda self, b, prefix, recursive: [
                _Obj(f"{prefix}a.pdf"), _Obj(f"{prefix}b.pdf"),
            ]
        },
    )()
    monkeypatch.setattr(MinioClient, "_check_available", lambda self: True)
    assert client.list_objects("original/u1/") == [
        "original/u1/a.pdf",
        "original/u1/b.pdf",
    ]


# ──────────────────────────────────────────────────────────────────────
# Neo4jClient mock 测试（隔离网络，pytest-asyncio auto 模式）
# ──────────────────────────────────────────────────────────────────────
class _FakeSummary:
    def __init__(self, nodes_deleted=0):
        self.counters = type("C", (), {"nodes_deleted": nodes_deleted})()


class _FakeResult:
    def __init__(self, nodes_deleted=0):
        self._n = nodes_deleted

    async def consume(self):
        return _FakeSummary(self._n)


class _FakeSession:
    def __init__(self):
        self.ran = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def run(self, query, params):
        self.ran.append((query, params))
        return _FakeResult(nodes_deleted=1)


class _FakeDriver:
    def __init__(self):
        self.session_instances = []

    def session(self):
        s = _FakeSession()
        self.session_instances.append(s)
        return s


def test_neo4j_delete_nodes_by_doc_empty(monkeypatch):
    pytest.importorskip("neo4j")
    from app.utils.neo4j_client import Neo4jClient

    monkeypatch.setattr(Neo4jClient, "_instance", None)
    client = Neo4jClient()

    async def _run():
        return await client.delete_nodes_by_doc([])

    import asyncio

    assert asyncio.run(_run()) == 0


def test_neo4j_delete_nodes_by_doc_counts(monkeypatch):
    pytest.importorskip("neo4j")
    import asyncio

    from app.utils.neo4j_client import Neo4jClient

    monkeypatch.setattr(Neo4jClient, "_instance", None)
    client = Neo4jClient()
    driver = _FakeDriver()
    client._driver = driver

    async def _run():
        return await client.delete_nodes_by_doc(["d1", "d2"])

    total = asyncio.run(_run())
    # 2 个实体 id（每次 1）+ Document/Chunk 一次（1）= 3
    assert total == 3
    assert len(driver.session_instances) == 1
    assert len(driver.session_instances[0].ran) == 3