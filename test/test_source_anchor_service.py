# -*- coding: utf-8 -*-
"""抗幻觉溯源与多文对比服务测试：锚点提取、跨文档对比。"""
from app.services.source_anchor_service import (
    SourceAnchorService,
    extract_anchors,
    multi_document_compare,
)


def test_extract_anchors_filters_missing_document_id():
    chunks = [
        {"document_id": "doc1", "page_number": 3, "snippet": "transformer architecture", "score": 0.9},
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
        {"document_id": "p1", "title": "BERT", "chunks": ["Bidirectional encoder representations"]},
        {"document_id": "p2", "title": "Transformer", "chunks": ["Attention is all you need"]},
    ]
    result = multi_document_compare(docs, "attention mechanism")
    assert result["backend"] == "builtin"
    assert result["candidate_count"] == 2
    assert len(result["perspectives"]) == 2
    assert "attention" in result["conclusion"].lower() or result["conclusion"]


def test_service_compare():
    svc = SourceAnchorService()
    out = svc.compare([{"document_id": "d", "chunks": ["hello world"]}], "hello")
    assert out["candidate_count"] == 1