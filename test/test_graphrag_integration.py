# -*- coding: utf-8 -*-
"""graphrag_integration 代理服务测试：覆盖成功返回与异常降级（mock httpx.Client）。"""
import httpx
import pytest

from app.services.graphrag_integration import GraphRAGIntegration


class _FakeResponse:
    def __init__(self, data=None, *, raise_http_error=False, status_code=200, text="boom"):
        self._data = data if data is not None else {"ok": True}
        self._raise_http_error = raise_http_error
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._data

    def raise_for_status(self):
        if self._raise_http_error:
            req = httpx.Request("POST", "http://test/query")
            resp = httpx.Response(self.status_code, request=req, text=self.text)
            raise httpx.HTTPStatusError("server error", request=req, response=resp)


class _FakeClient:
    def __init__(self, response=None, *, raise_exc=False):
        self.response = response or _FakeResponse()
        self.raise_exc = raise_exc

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def _maybe_raise(self):
        if self.raise_exc:
            raise RuntimeError("down")

    def get(self, url, **kw):
        self._maybe_raise()
        return self.response

    def post(self, url, **kw):
        self._maybe_raise()
        return self.response

    def delete(self, url, **kw):
        self._maybe_raise()
        return self.response


@pytest.fixture
def gr():
    return GraphRAGIntegration()


def _install(monkeypatch, gr, client):
    monkeypatch.setattr(gr, "_client", lambda: client)


def test_health_check(gr, monkeypatch):
    _install(monkeypatch, gr, _FakeClient(_FakeResponse({"status": "up"})))
    assert gr.health_check() == {"status": "connected", "service": {"status": "up"}}
    _install(monkeypatch, gr, _FakeClient(raise_exc=True))
    r = gr.health_check()
    assert r["status"] == "disconnected" and "error" in r


def test_llm_status(gr, monkeypatch):
    _install(monkeypatch, gr, _FakeClient(_FakeResponse({"status": "ok"})))
    assert gr.llm_status() == {"status": "ok"}
    _install(monkeypatch, gr, _FakeClient(raise_exc=True))
    assert gr.llm_status() == {"status": "error", "error": "down"}


def test_list_models(gr, monkeypatch):
    _install(monkeypatch, gr, _FakeClient(_FakeResponse({"models": []})))
    assert gr.list_models() == {"models": []}
    _install(monkeypatch, gr, _FakeClient(raise_exc=True))
    assert gr.list_models() == {"error": "down"}


def test_load_model(gr, monkeypatch):
    _install(monkeypatch, gr, _FakeClient(_FakeResponse({"loaded": True})))
    assert gr.load_model("m") == {"loaded": True}
    _install(monkeypatch, gr, _FakeClient(raise_exc=True))
    assert gr.load_model("m") == {"error": "down"}


def test_rag_query(gr, monkeypatch):
    _install(monkeypatch, gr, _FakeClient(_FakeResponse({"answer": "A"})))
    assert gr.rag_query("q") == {"answer": "A"}
    # HTTPStatusError 分支
    _install(monkeypatch, gr, _FakeClient(_FakeResponse(raise_http_error=True, status_code=500)))
    r = gr.rag_query("q")
    assert "500" in r["error"] and r["details"] == "boom"
    # 通用异常
    _install(monkeypatch, gr, _FakeClient(raise_exc=True))
    assert gr.rag_query("q") == {"error": "down"}


def test_graph_stats(gr, monkeypatch):
    _install(monkeypatch, gr, _FakeClient(_FakeResponse({"nodes": 1})))
    assert gr.graph_stats() == {"nodes": 1}
    _install(monkeypatch, gr, _FakeClient(raise_exc=True))
    assert gr.graph_stats() == {"error": "down"}


def test_search_nodes(gr, monkeypatch):
    _install(monkeypatch, gr, _FakeClient(_FakeResponse({"hits": []})))
    assert gr.search_nodes("perov") == {"hits": []}
    _install(monkeypatch, gr, _FakeClient(raise_exc=True))
    assert gr.search_nodes("perov") == {"error": "down"}


def test_get_relations_by_type(gr, monkeypatch):
    _install(monkeypatch, gr, _FakeClient(_FakeResponse({"rels": []})))
    assert gr.get_relations_by_type("HAS_PROPERTY") == {"rels": []}
    _install(monkeypatch, gr, _FakeClient(raise_exc=True))
    assert gr.get_relations_by_type("HAS_PROPERTY") == {"error": "down"}


def test_get_nodes_by_label(gr, monkeypatch):
    _install(monkeypatch, gr, _FakeClient(_FakeResponse({"nodes": []})))
    assert gr.get_nodes_by_label("Material") == {"nodes": []}
    _install(monkeypatch, gr, _FakeClient(raise_exc=True))
    assert gr.get_nodes_by_label("Material") == {"error": "down"}


def test_index_document(gr, monkeypatch):
    _install(monkeypatch, gr, _FakeClient(_FakeResponse({"indexed": True})))
    assert gr.index_document("d1", "T", [], []) == {"indexed": True}
    _install(monkeypatch, gr, _FakeClient(raise_exc=True))
    assert gr.index_document("d1", "T", [], []) == {"error": "down"}


def test_add_node(gr, monkeypatch):
    _install(monkeypatch, gr, _FakeClient(_FakeResponse({"node": True})))
    assert gr.add_node("Material", "n1") == {"node": True}
    _install(monkeypatch, gr, _FakeClient(raise_exc=True))
    assert gr.add_node("Material", "n1") == {"error": "down"}


def test_add_relation(gr, monkeypatch):
    _install(monkeypatch, gr, _FakeClient(_FakeResponse({"rel": True})))
    assert gr.add_relation("A", "a", "B", "b", "HAS") == {"rel": True}
    _install(monkeypatch, gr, _FakeClient(raise_exc=True))
    assert gr.add_relation("A", "a", "B", "b", "HAS") == {"error": "down"}


def test_clear_graph(gr, monkeypatch):
    _install(monkeypatch, gr, _FakeClient(_FakeResponse({"cleared": True})))
    assert gr.clear_graph() == {"cleared": True}
    _install(monkeypatch, gr, _FakeClient(raise_exc=True))
    assert gr.clear_graph() == {"error": "down"}


def test_seed_demo_data(gr, monkeypatch):
    _install(monkeypatch, gr, _FakeClient(_FakeResponse({"seeded": True})))
    assert gr.seed_demo_data() == {"seeded": True}
    _install(monkeypatch, gr, _FakeClient(raise_exc=True))
    assert gr.seed_demo_data() == {"error": "down"}