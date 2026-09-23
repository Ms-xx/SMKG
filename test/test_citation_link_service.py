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
    assert "2" in result["by_reference"]
    assert len(result["by_reference"]["2"]) == 1


def test_build_citation_map_char_offsets_and_page():
    text = "Intro [1] body [2,3] end."
    pages = [text, "final [1] wrap."]
    result = build_citation_map(pages, [{"index": 1}, {"index": 2}, {"index": 3}])

    # [1] 出现在第 1 页和第 2 页
    p1_hits = [
        c for c in result["citations"] if c["page_index"] == 0 and c["ref_index"] == 1
    ]
    assert p1_hits and p1_hits[0]["start"] == text.index("[1]")
    assert p1_hits[0]["page_number"] == 1

    # [2,3] 同一起点、ref_index 分别为 2 与 3
    multi = [
        c
        for c in result["citations"]
        if c["page_index"] == 0 and c["start"] == text.index("[2,3]")
    ]
    assert {c["ref_index"] for c in multi} == {2, 3}
    assert result["by_reference"]["3"][0]["page_index"] == 0


def test_author_year_citation_kept_no_ref_index():
    text = "As shown (Vaswani et al., 2017), attention works[1]."
    cites = extract_inline_citations(text)
    author_year = [c for c in cites if c["kind"] == "author_year"]
    numeric = [c for c in cites if c["kind"] == "numeric"]
    assert author_year and author_year[0]["ref_index"] is None
    assert 1 in [c["ref_index"] for c in numeric]


def test_title_tree_nonexistent_path_degrades():
    tree = extract_title_tree("/nonexistent/not-a-file.pdf")
    assert tree == []


def test_service_title_tree():
    svc = CitationLinkService()
    out = svc.title_tree("/nonexistent/x.pdf")
    assert out["tree"] == []
