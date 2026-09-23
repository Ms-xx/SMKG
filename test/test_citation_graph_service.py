# -*- coding: utf-8 -*-
"""引用图谱挖掘与综述服务测试：网络建图、PageRank、介数中心性、Future Work 去重。"""
from app.services.citation_graph_service import (
    CitationGraphService,
    betweenness_centrality,
    build_citation_network,
    deduplicate_future_work,
    page_rank,
)

REFERENCES = [
    {"index": 1, "title": "Attention Is All You Need", "year": "2017", "doi": "10.1/attn"},
    {"index": 2, "title": "BERT: Pre-training", "year": "2018", "doi": "10.1/bert"},
    {"index": 3, "title": "Attention Is All You Need", "year": "2017", "doi": "10.1/attn"},  # 重复
]


def test_build_citation_network_dedups():
    net = build_citation_network(REFERENCES)
    assert net["node_count"] == 2  # 重复 doi 去重


def test_page_rank_sums_close_to_one():
    refs = [
        {"index": 1, "title": "alpha paper", "year": "2017"},
        {"index": 2, "title": "beta paper", "year": "2018"},
    ]
    net = build_citation_network(refs)
    ranks = page_rank(net)
    assert abs(sum(ranks.values()) - 1.0) < 1e-6


def test_betweenness_centrality_returns_all_nodes():
    refs = [
        {"index": 1, "title": "alpha paper", "year": "2017"},
        {"index": 2, "title": "beta paper", "year": "2018"},
        {"index": 3, "title": "gamma paper", "year": "2019"},
    ]
    net = build_citation_network(refs)
    bc = betweenness_centrality(net)
    assert set(bc.keys()) == {n["id"] for n in net["nodes"]}


def test_deduplicate_future_work():
    chunks = ["We will explore X in future", "We will explore X in future work", "Different future direction"]
    result = deduplicate_future_work(chunks)
    assert result["unique_count"] < result["input_count"]


def test_service_survey():
    svc = CitationGraphService()
    out = svc.survey(REFERENCES)
    assert out["backend"] == "rule"
    assert out["reference_count"] == 3