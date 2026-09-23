# -*- coding: utf-8 -*-
"""版式联动阅读服务测试：正文引用定位、双向映射、标题树降级。"""
from app.services.citation_link_service import (
    CitationLinkService,
    build_citation_map,
    extract_inline_citations,
    extract_title_tree,
)


def test_extract_inline_citations_numeric():
    text = "Previous work [1,2] showed results [3]. See ［4］."
    cites = extract_inline_citations(text)
    refs = [c["ref_index"] for c in cites if c["kind"] == "numeric"]
    assert 1 in refs and 2 in refs and 3 in refs and 4 in refs


def test_build_citation_map():
    pages = ["This uses method [1] and [2].", "Conclusion references [1] again."]
    references = [
        {"index": 1, "title": "Ref one"},
        {"index": 2, "title": "Ref two"},
    ]
    result = build_citation_map(pages, references)
    assert result["references_count"] == 2
    assert "1" in result["by_reference"]
    assert len(result["by_reference"]["1"]) == 2  # 第1页 + 第2页


def test_title_tree_nonexistent_path_degrades():
    tree = extract_title_tree("/nonexistent/not-a-file.pdf")
    assert tree == []


def test_service_title_tree():
    svc = CitationLinkService()
    out = svc.title_tree("/nonexistent/x.pdf")
    assert out["tree"] == []