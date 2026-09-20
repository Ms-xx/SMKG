# -*- coding: utf-8 -*-
"""
vector_store 单元测试
覆盖：实体/关系/文档 chunk 的向量写入与相似度检索（含类型过滤、排序）。
在无 sentence-transformers / faiss 的环境下自动走哈希向量 + numpy 降级路径。
"""
import os
import sys

GRAPHRAG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "GraphRAGTest"))
if GRAPHRAG_DIR not in sys.path:
    sys.path.insert(0, GRAPHRAG_DIR)

from vector_store import VectorStore  # noqa: E402


def test_add_and_search_entities():
    vs = VectorStore()
    vs.clear()
    vs.add_entity("钙钛矿", "Material")
    vs.add_entity("高效率", "Property")
    vs.add_entity("太阳能电池", "Device")

    hits = vs.search("钙钛矿太阳能电池", top_k=3)
    assert len(hits) >= 1
    assert all(h["type"] == "entity" for h in hits)
    # 元数据应完整回传
    assert hits[0]["metadata"]["label"] in {"Material", "Property", "Device"}


def test_relation_and_chunk_roundtrip():
    vs = VectorStore()
    vs.clear()
    vs.add_relation("钙钛矿", "HAS_PROPERTY", "高效率")
    vs.add_chunk("钙钛矿太阳能电池具有高光电转换效率", {"doc_id": "d1"})

    hits = vs.search("钙钛矿 高效率", top_k=5)
    assert any(h["type"] == "relation" for h in hits)

    chunk_hits = vs.search("光电转换效率", top_k=5, record_type="chunk")
    assert chunk_hits, "应能检索到 chunk"
    assert all(h["type"] == "chunk" for h in chunk_hits)
    assert chunk_hits[0]["metadata"]["doc_id"] == "d1"


def test_record_type_filter_and_score_order():
    vs = VectorStore()
    vs.clear()
    vs.add_entity("钙钛矿", "Material")
    vs.add_entity("钙钛矿材料", "Material")

    hits = vs.search("钙钛矿", top_k=2, record_type="entity")
    assert len(hits) == 2
    # 相似度按降序排列
    assert hits[0]["score"] >= hits[1]["score"]


def test_size_and_clear():
    vs = VectorStore()
    vs.clear()
    assert vs.size == 0
    vs.add_entity("钙钛矿", "Material")
    assert vs.size == 1
    vs.clear()
    assert vs.size == 0
    assert vs.search("钙钛矿") == []