# -*- coding: utf-8 -*-
"""抗幻觉溯源与多文对比服务测试：锚点提取、跨文档对比、真实 RAG 溯源与 LLM 结论。"""
from unittest.mock import patch

import pytest

from app.core.config import settings
from app.services.source_anchor_service import (
    SourceAnchorService,
    anchors_from_rag,
    backfill_page_numbers,
    extract_anchors,
    multi_document_compare,
)

pytestmark = pytest.mark.asyncio


def test_extract_anchors_filters_missing_document_id():
    chunks = [
        {
            "document_id": "doc1",
            "page_number": 3,
            "snippet": "transformer architecture",
            "score": 0.9,
        },
        {"page_number": 2, "snippet": "no doc id here", "score": 0.9},
    ]
    anchors = extract_anchors(chunks)
    assert len(anchors) == 1
    assert anchors[0]["document_id"] == "doc1"
    assert anchors[0]["page_number"] == 3


def test_extract_anchors_sorted_by_score_desc():
    chunks = [
        {"document_id": "a", "snippet": "x", "score": 0.5},
        {"document_id": "b", "snippet": "y", "score": 0.9},
    ]
    anchors = extract_anchors(chunks)
    assert anchors[0]["document_id"] == "b"


def test_multi_document_compare():
    docs = [
        {
            "document_id": "p1",
            "title": "BERT",
            "chunks": ["Bidirectional encoder representations"],
        },
        {
            "document_id": "p2",
            "title": "Transformer",
            "chunks": ["Attention is all you need"],
        },
    ]
    result = multi_document_compare(docs, "attention mechanism", use_llm=False)
    assert result["backend"] == "builtin"
    assert result["candidate_count"] == 2
    assert len(result["perspectives"]) == 2
    assert "attention" in result["conclusion"].lower() or result["conclusion"]


def test_service_compare():
    svc = SourceAnchorService()
    out = svc.compare(
        [{"document_id": "d", "chunks": ["hello world"]}], "hello", use_llm=False
    )
    assert out["candidate_count"] == 1


def test_extract_anchors_includes_chunk_index(monkeypatch):
    chunks = [
        {
            "document_id": "doc1",
            "chunk_index": 3,
            "snippet": "transformer",
            "score": 0.7,
        }
    ]
    anchors = extract_anchors(chunks)
    assert anchors[0]["chunk_index"] == 3
    assert anchors[0]["page_number"] is None


def test_anchors_from_rag_success(monkeypatch):
    """8001 返回真实 sources → backend=rag 且锚点非空。"""
    fake_result = {
        "sources": [
            {
                "document_id": "doc1",
                "chunk_index": 2,
                "snippet": "perovskite solar cell",
                "score": 0.9,
            },
            {
                "document_id": "doc2",
                "chunk_index": 5,
                "snippet": "attention mechanism",
                "score": 0.8,
            },
        ]
    }
    with patch("app.services.graphrag_integration.graphrag_integration") as mock_g:
        mock_g.rag_query.return_value = fake_result
        out = anchors_from_rag("钙钛矿电池")
        assert out["backend"] == "rag"
        assert out["anchor_count"] == 2
        assert out["anchors"][0]["document_id"] == "doc1"
        assert out["anchors"][0]["snippet"] == "perovskite solar cell"


def test_anchors_from_rag_degrade_on_error(monkeypatch):
    """返回 error/空 sources → 降级 backend=builtin、锚点为空、附 note。"""
    with patch("app.services.graphrag_integration.graphrag_integration") as mock_g:
        mock_g.rag_query.return_value = {"error": "GraphRAGTest 连接失败"}
        out = anchors_from_rag("钙钛矿电池")
        assert out["backend"] == "builtin"
        assert out["anchors"] == []
        assert out.get("note")


def test_multi_document_compare_llm(monkeypatch):
    """配置 LLM 时结论由真实 LLM 生成 → backend=llm。"""
    monkeypatch.setattr(settings, "LLM_ENABLED", True)
    monkeypatch.setattr(settings, "LLM_ENDPOINT", "http://127.0.0.1:1234/v1")
    monkeypatch.setattr(settings, "LLM_MODEL", "qwen/qwen3-4b-2507")
    monkeypatch.setattr(settings, "LLM_TIMEOUT", 5.0)
    with patch(
        "app.services.source_anchor_service._llm_chat_completion",
        return_value="A 侧重 X，B 侧重 Y。",
    ):
        out = multi_document_compare(
            [
                {"document_id": "p1", "title": "A", "chunks": ["attention is key"]},
                {"document_id": "p2", "title": "B", "chunks": ["graph neural network"]},
            ],
            "对比",
        )
    assert out["backend"] == "llm"
    assert out["conclusion"] == "A 侧重 X，B 侧重 Y。"


def test_multi_document_compare_llm_degrade(monkeypatch):
    """LLM 未配置 → 降级规则模板 backend=builtin。"""
    monkeypatch.setattr(settings, "LLM_ENABLED", False)
    out = multi_document_compare(
        [{"document_id": "p1", "title": "A", "chunks": ["attention"]}], "对比"
    )
    assert out["backend"] == "builtin"
    assert out["conclusion"]


# ── 步骤15【P2】页级定位回填 backfill_page_numbers ─────────────────────────


def test_backfill_page_numbers_hits_page():
    anchors = [
        {
            "document_id": "doc1",
            "page_number": None,
            "chunk_index": 0,
            "snippet": "钙钛矿太阳电池的效率提升是研究热点",
            "score": 0.9,
        }
    ]
    pages_lookup = {
        "doc1": [
            {"page_number": 1, "text": "综述开头 引言部分"},
            {"page_number": 3, "text": "钙钛矿太阳电池的效率提升是研究热点 本节论述"},
        ]
    }
    result = backfill_page_numbers(anchors, pages_lookup)
    assert result["backfilled_count"] == 1
    assert result["anchors"][0]["page_number"] == 3
    # 其余字段保留（chunk_index / snippet / score）
    anchor = result["anchors"][0]
    assert anchor["chunk_index"] == 0
    assert anchor["snippet"] == "钙钛矿太阳电池的效率提升是研究热点"
    assert anchor["score"] == 0.9


def test_backfill_page_numbers_empty_pages_keeps_none():
    anchors = [
        {
            "document_id": "doc1",
            "page_number": None,
            "snippet": "some text",
            "score": 0.9,
        }
    ]
    result = backfill_page_numbers(anchors, {})  # pages_lookup 缺省为空
    assert result["backfilled_count"] == 0
    assert result["anchors"][0]["page_number"] is None


def test_backfill_page_numbers_does_not_overwrite_pinned():
    anchors = [
        {
            "document_id": "doc1",
            "page_number": 5,
            "snippet": "钙钛矿太阳电池",
            "score": 0.9,
        }
    ]
    pages_lookup = {
        "doc1": [
            {"page_number": 3, "text": "钙钛矿太阳电池的效率提升"},
        ]
    }
    result = backfill_page_numbers(anchors, pages_lookup)
    assert result["backfilled_count"] == 0  # 已写死页码，不覆盖、不计回填
    assert result["anchors"][0]["page_number"] == 5


def test_backfill_page_numbers_multi_doc_lookup():
    anchors = [
        {
            "document_id": "a",
            "page_number": None,
            "snippet": "attention is all you need",
        },
        {"document_id": "b", "page_number": None, "snippet": "graph neural network"},
    ]
    pages_lookup = {
        "a": [{"page_number": 7, "text": "attention is all you need 说明"}],
        "b": [{"page_number": 2, "text": "graph neural network 概述"}],
    }
    result = backfill_page_numbers(anchors, pages_lookup)
    assert result["backfilled_count"] == 2
    by_doc = {a["document_id"]: a for a in result["anchors"]}
    assert by_doc["a"]["page_number"] == 7
    assert by_doc["b"]["page_number"] == 2


def test_source_anchor_service_backfill_method():
    """SourceAnchorService.backfill 直调纯函数供 API 编排。"""
    anchors = [
        {"document_id": "d", "page_number": None, "snippet": "matched fragment here"}
    ]
    pages_lookup = {"d": [{"page_number": 4, "text": "matched fragment here tail"}]}
    out = SourceAnchorService().backfill(anchors, pages_lookup)
    assert out["anchors"][0]["page_number"] == 4
    assert out["backfilled_count"] == 1


async def test_rag_anchors_api_page_backfill_zero(client, token, monkeypatch):
    """GraphRAG 返回空 sources → anchors 空 → page_backfill.backfilled_count=0 不报错。"""
    from conftest import API_PREFIX

    monkeypatch.setattr(
        "app.services.source_anchor_service.anchors_from_rag",
        lambda question: {
            "backend": "builtin",
            "question": question,
            "anchors": [],
            "note": "GraphRAGTest 未检索到带来源的 chunk",
        },
    )
    resp = await client.post(
        f"{API_PREFIX}/source-anchor/rag-anchors",
        json={"question": "钙钛矿"},
        headers=token(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["anchors"] == []
    assert body["page_backfill"]["backfilled_count"] == 0
