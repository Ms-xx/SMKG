# -*- coding: utf-8 -*-
"""10.2 六方向新模块 API 冒烟测试：鉴权、基本请求/响应结构。"""
import pytest

from conftest import API_PREFIX

pytestmark = pytest.mark.asyncio


async def test_deduplication_detect(client, token):
    resp = await client.post(
        f"{API_PREFIX}/deduplication/detect",
        json={
            "documents": [
                {"id": "d1", "title": "Attention is all you need"},
                {"id": "d2", "title": "Attention is all you need"},
            ]
        },
        headers=token(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["backend"] == "simhash"


async def test_source_anchor_anchors(client, token):
    resp = await client.post(
        f"{API_PREFIX}/source-anchor/anchors",
        json={"chunks": [{"document_id": "doc1", "page_number": 2, "snippet": "x", "score": 0.8}]},
        headers=token(),
    )
    assert resp.status_code == 200
    assert resp.json()["anchors"][0]["document_id"] == "doc1"


async def test_citation_link_map(client, token):
    resp = await client.post(
        f"{API_PREFIX}/citation-link/map",
        json={"pages_text": ["see [1] and [2]"], "references": [{"index": 1}, {"index": 2}]},
        headers=token(),
    )
    assert resp.status_code == 200
    assert resp.json()["references_count"] == 2


async def test_citation_graph_network(client, token):
    resp = await client.post(
        f"{API_PREFIX}/citation-graph/network",
        json={"references": [{"index": 1, "title": "A paper", "doi": "10.1/a"}]},
        headers=token(),
    )
    assert resp.status_code == 200
    assert resp.json()["node_count"] == 1


async def test_writing_assistant_outline(client, token):
    resp = await client.post(
        f"{API_PREFIX}/writing-assistant/outline",
        json={"idea": "graph", "references": [{"index": 1, "raw": "A. Real."}]},
        headers=token(),
    )
    assert resp.status_code == 200
    assert resp.json()["reference_count"] == 1


async def test_module_requires_auth(client):
    resp = await client.post(f"{API_PREFIX}/deduplication/detect", json={"documents": []})
    assert resp.status_code == 401