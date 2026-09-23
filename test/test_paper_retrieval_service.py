# -*- coding: utf-8 -*-
"""论文检索与推荐服务测试：arXiv Atom 解析、网络失败降级、相关性推荐。"""
from app.services import paper_retrieval_service as prs


_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/1706.03762v7</id>
    <title>Attention Is All You Need</title>
    <summary>Transformer architecture</summary>
    <published>2017-06-12T00:00:00Z</published>
    <author><name>Ashish Vaswani</name></author>
  </entry>
</feed>"""


def test_search_arxiv_parses_atom(monkeypatch):
    monkeypatch.setattr(prs, "_http_get", lambda url, timeout=10.0: _ATOM)
    result = prs.search_arxiv("attention")
    assert result["count"] == 1
    assert result["results"][0]["arxiv_id"] == "1706.03762v7"
    assert result["results"][0]["source"] == "arxiv"


def test_search_arxiv_degrades_on_network_error(monkeypatch):
    def boom(url, timeout=10.0):
        raise OSError("network down")

    monkeypatch.setattr(prs, "_http_get", boom)
    result = prs.search_arxiv("whatever")
    assert result["count"] == 0
    assert "error" in result


def test_recommend_scores_candidates():
    local = [{"title": "Graph neural networks for materials", "journal": "Nature"}]
    candidates = [
        {"title": "Graph neural networks for materials science", "source": "arxiv", "authors": ["A"], "summary": "..."},
        {"title": "Unrelated genome sequencing", "source": "pubmed", "authors": ["B"], "summary": "..."},
    ]
    result = prs.recommend(local, candidates)
    assert len(result["recommendations"]) == 2
    assert result["recommendations"][0]["title"].startswith("Graph neural")