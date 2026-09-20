# -*- coding: utf-8 -*-
"""graph_service 与 neo4j_client 测试：通过 fake driver / fake client 覆盖查询与统计逻辑。"""
import pytest

from app.services.graph_service import GraphService
from app.utils.neo4j_client import Neo4jClient


# ── fake neo4j 客户端（供 GraphService 使用）─────────────────────────────
class _FakeNeo4jService:
    def __init__(self, records=None):
        self.records = records or []
        self.calls = []

    async def execute_query(self, query, params=None):
        self.calls.append((query, params))
        return self.records


@pytest.mark.asyncio
async def test_graph_search_with_entity_type():
    svc = GraphService()
    fake = _FakeNeo4jService([{"name": "Perov"}])
    svc.neo4j_client = fake

    res = await svc.search("perov", entity_type="Material", limit=5)
    assert res == [{"name": "Perov"}]
    assert "Material" in fake.calls[0][0]


@pytest.mark.asyncio
async def test_graph_search_all():
    svc = GraphService()
    fake = _FakeNeo4jService([{"name": "X"}])
    svc.neo4j_client = fake

    res = await svc.search("x")
    assert res == [{"name": "X"}]
    assert "MATCH (n)" in fake.calls[0][0]


@pytest.mark.asyncio
async def test_graph_get_entity_hit_and_miss():
    svc = GraphService()
    svc.neo4j_client = _FakeNeo4jService([{"id": "1", "name": "X"}])
    assert await svc.get_entity("1") == {"id": "1", "name": "X"}
    assert await svc.get_entity_relations("1", depth=2) == [{"id": "1", "name": "X"}]
    assert await svc.execute_cypher("MATCH (n) RETURN n", {"x": 1}) == [{"id": "1", "name": "X"}]

    svc.neo4j_client = _FakeNeo4jService([])
    assert await svc.get_entity("missing") is None


@pytest.mark.asyncio
async def test_graph_statistics():
    svc = GraphService()
    svc.neo4j_client = _FakeNeo4jService([{"labels": ["Material"], "count": 3}])
    stats = await svc.get_statistics()
    assert stats["node_stats"] == [{"labels": ["Material"], "count": 3}]
    assert stats["relation_stats"] == [{"labels": ["Material"], "count": 3}]


# ── neo4j_client 单例测试 ────────────────────────────────────────────────
class _FakeSession:
    def __init__(self, records):
        self._records = records

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def run(self, query, params):
        return _FakeResult(self._records)


class _FakeResult:
    def __init__(self, records):
        self._records = records

    async def fetch(self):
        return [_FakeRecord(r) for r in self._records]

    async def consume(self):
        return None


class _FakeRecord:
    def __init__(self, data):
        self._data = data

    def data(self):
        return self._data


class _FakeDriver:
    def __init__(self):
        self.closed = False
        self.connected = False

    def session(self):
        return _FakeSession([{"k": "v"}])

    async def verify_connectivity(self):
        self.connected = True

    async def close(self):
        self.closed = True


@pytest.fixture
def neo():
    Neo4jClient._instance = None
    yield Neo4jClient()
    Neo4jClient._instance = None


@pytest.mark.asyncio
async def test_neo4j_execute_query(neo):
    neo._driver = _FakeDriver()
    records = await neo.execute_query("MATCH (n) RETURN n", {"x": 1})
    assert records == [{"k": "v"}]


@pytest.mark.asyncio
async def test_neo4j_execute_write(neo):
    neo._driver = _FakeDriver()
    assert await neo.execute_write("CREATE (n)") is True


@pytest.mark.asyncio
async def test_neo4j_verify_and_close(neo):
    d = _FakeDriver()
    neo._driver = d
    await neo.verify_connectivity()
    assert d.connected is True

    await neo.close()
    assert d.closed is True
    assert neo._driver is None

    # 无 driver 时再次 close 不报错
    await neo.close()