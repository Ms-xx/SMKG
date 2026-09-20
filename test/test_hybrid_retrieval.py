# -*- coding: utf-8 -*-
"""
hybrid_retrieval 单元测试
覆盖：向量 + BM25 混合检索、RRF 融合排序、top-k、空库、降级路径（无 cross-encoder）。
"""
import os
import sys

GRAPHRAG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "GraphRAGTest"))
if GRAPHRAG_DIR not in sys.path:
    sys.path.insert(0, GRAPHRAG_DIR)

from hybrid_retrieval import HybridRetriever  # noqa: E402


def _build() -> HybridRetriever:
    hr = HybridRetriever()
    hr.add_entity("钙钛矿", "Material")
    hr.add_entity("高效率", "Property")
    hr.add_relation("钙钛矿", "HAS_PROPERTY", "高效率")
    hr.add_chunk("钙钛矿太阳能电池具有高光电转换效率", {"doc_id": "d1"})
    hr.add_chunk("perovskite solar cells achieve high efficiency", {"doc_id": "d2"})
    return hr


def test_search_returns_fused_results():
    hr = _build()
    res = hr.search("钙钛矿 光电转换效率", top_k=5)

    assert res["query"] == "钙钛矿 光电转换效率"
    assert res["rerank_backend"] in {"none", "cross-encoder"}  # 有无 sentence-transformers 均可用
    assert len(res["results"]) >= 1

    for r in res["results"]:
        assert {"id", "type", "text", "metadata", "score", "vector_score", "bm25_score", "rerank_score"} <= set(
            r.keys()
        )

    # 融合分数按降序排列
    scores = [r["score"] for r in res["results"]]
    assert scores == sorted(scores, reverse=True)


def test_top_k_truncation():
    hr = _build()
    res = hr.search("钙钛矿", top_k=2)
    assert len(res["results"]) <= 2


def test_bm25_keyword_match():
    hr = HybridRetriever()
    hr.add_chunk("the genome of arabidopsis thaliana", {"tag": "biology"})
    hr.add_chunk("钙钛矿 材料", {"tag": "material"})

    res = hr.search("arabidopsis thaliana", top_k=3)
    texts = [r["text"] for r in res["results"]]
    assert any("arabidopsis" in t for t in texts)


def test_empty_store():
    hr = HybridRetriever()
    res = hr.search("anything")
    assert res["results"] == []