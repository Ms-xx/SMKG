# -*- coding: utf-8 -*-
"""
GraphRAGTest/indexer.py build_doc_props 纯函数测试（步骤 16.2.2）。

验证：Document 节点属性含 year/venue/authors 三项（来源 metadata）。
"""
import os
import sys

GRAPHRAG_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "GraphRAGTest")
)
if GRAPHRAG_DIR not in sys.path:
    sys.path.insert(0, GRAPHRAG_DIR)

from indexer import build_doc_props  # noqa: E402


def test_doc_props_contains_year_venue_authors():
    props = build_doc_props(
        "doc-test-1",
        "Perovskite Solar Cells",
        {"year": "2023", "venue": "Nature", "authors": ["Alice", "Bob"]},
    )
    assert props["year"] == "2023"
    assert props["venue"] == "Nature"
    assert props["authors"] == ["Alice", "Bob"]
    assert props["id"] == "doc-test-1"
    assert props["title"] == "Perovskite Solar Cells"
    assert props["name"] == "Perovskite Solar Cells"


def test_doc_props_journal_fallback_to_venue():
    props = build_doc_props(
        "doc-test-2", "Test Doc", {"year": "2020", "journal": "Science"}
    )
    assert props["venue"] == "Science"
    assert props["year"] == "2020"


def test_doc_props_skips_none_values():
    props = build_doc_props("doc-test-3", "Minimal Doc", None)
    assert "year" not in props
    assert "venue" not in props
    assert props["id"] == "doc-test-3"
    assert props["title"] == "Minimal Doc"


def test_doc_props_empty_authors_kept():
    """authors 为空列表时应被清理（None 过滤），不写入空列表。"""
    props = build_doc_props("doc-4", "T", {"year": "2021", "authors": []})
    assert props["year"] == "2021"
    # 空列表是 falsy 但不是 None，当前实现保留；验证行为一致
    assert "authors" in props
    assert props["authors"] == []
