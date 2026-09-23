# -*- coding: utf-8 -*-
"""语义去重与版本管理服务测试：指纹相似度、重复分组、版本识别、机构抽取。"""
from app.services.deduplication_service import (
    DeduplicationService,
    extract_affiliations,
    extract_arxiv_version,
    simhash_similarity,
)


def test_simhash_identical_and_distinct():
    """相同文本相似度接近 1，不同文本显著更低。"""
    a = "Attention Is All You Need"
    b = "Attention Is All You Need"
    c = "A completely different topic about chemistry"
    assert simhash_similarity(a, b) > 0.99
    assert simhash_similarity(a, c) < 0.7


def test_extract_arxiv_version():
    info = extract_arxiv_version("Attention Is All You Need (arXiv:1706.03762v7)")
    assert info["arxiv_id"] == "1706.03762"
    assert info["version"] == "v7"
    assert extract_arxiv_version("plain title") is None


def test_detect_groups_duplicates():
    svc = DeduplicationService()
    docs = [
        {"id": "d1", "title": "arXiv:1706.03762v1 Attention is all you need", "abstract": "transformer"},
        {"id": "d2", "title": "arXiv:1706.03762v7 Attention is all you need", "abstract": "transformer"},
        {"id": "d3", "title": "Some unrelated chemistry paper", "abstract": "molecule"},
    ]
    result = svc.detect(docs, threshold=0.80)
    assert result["backend"] == "simhash"
    assert result["cluster_count"] >= 1
    # d1/d2 视为同源，建议保留版本更高者 d2
    sugg = {c["suggestion"]["keep"] for c in result["clusters"]}
    assert "d2" in sugg


def test_extract_affiliations():
    text = "A. Author, Tsinghua University; B. Author, MIT, b@mit.edu"
    aff = extract_affiliations(text)
    assert any("university" in a.lower() for a in aff)
    assert any("mit.edu" in a.lower() for a in aff)