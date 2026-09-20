# -*- coding: utf-8 -*-
"""
索引管线单元测试
覆盖：文档解析/抽取完成后，将实体 / 关系 / chunk 向量化入向量库，
      并可通过混合检索命中（实体 + chunk）。
无 neo4j 依赖，纯测试 `hybrid_retrieval.index_document_vectors`。
"""
import os
import sys

GRAPHRAG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "GraphRAGTest"))
if GRAPHRAG_DIR not in sys.path:
    sys.path.insert(0, GRAPHRAG_DIR)

from hybrid_retrieval import HybridRetriever, index_document_vectors  # noqa: E402


def test_index_document_vectors_writes_and_searchable():
    hr = HybridRetriever()

    entities = [
        {"text": "钙钛矿", "entity_type": "Material"},
        {"text": "高效率", "entity_type": "Property"},
    ]
    relations = [
        {
            "source": "钙钛矿", "source_type": "Material",
            "target": "高效率", "target_type": "Property",
            "relation_type": "HAS_PROPERTY",
        }
    ]
    chunks = [
        "钙钛矿太阳能电池具有高光电转换效率",
        "perovskite solar cells achieve high power conversion efficiency",
    ]

    result = index_document_vectors("doc-1", entities, relations, chunks, retriever=hr)

    assert result["doc_id"] == "doc-1"
    assert result["entities_indexed"] == 2
    assert result["relations_indexed"] == 1
    assert result["chunks_indexed"] == 2

    # 混合检索能命中写入的实体与 chunk，且携带 doc_id 元数据
    res = hr.search("钙钛矿 光电转换效率", top_k=10)
    assert len(res["results"]) >= 1

    types = {r["type"] for r in res["results"]}
    assert "chunk" in types, "应能检索到 chunk"
    assert "entity" in types, "应能检索到实体"

    doc_ids = {r["metadata"].get("doc_id") for r in res["results"]}
    assert "doc-1" in doc_ids


def test_index_document_vectors_skips_invalid_and_empty():
    hr = HybridRetriever()

    # 空输入不应报错，且计数为 0
    empty = index_document_vectors("doc-empty", [], [], [], retriever=hr)
    assert empty == {
        "doc_id": "doc-empty",
        "entities_indexed": 0,
        "relations_indexed": 0,
        "chunks_indexed": 0,
    }

    # 缺失必填字段的实体 / 关系应被跳过，不崩溃
    result = index_document_vectors(
        "doc-2",
        entities=[{"entity_type": "Material"}],  # 无 text/name
        relations=[{"source": "孤立"}],           # 无 target
        chunks=None,
        retriever=hr,
    )
    assert result["entities_indexed"] == 0
    assert result["relations_indexed"] == 0
    assert result["chunks_indexed"] == 0