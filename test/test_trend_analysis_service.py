# -*- coding: utf-8 -*-
"""趋势分析服务测试：时间桶聚合、热点排序、覆盖率。"""
from app.services.trend_analysis_service import TrendAnalysisService, _bucket_key


def _nodes():
    return [
        {"id": "a1", "label": "Material", "properties": {"year": 2019, "id": "a1"}},
        {"id": "a2", "label": "Material", "properties": {"year": "2019", "id": "a2"}},
        {"id": "a3", "label": "Material", "properties": {"year": 2020, "id": "a3"}},
        {
            "id": "b1",
            "label": "Property",
            "properties": {"created_at": "2020-06-01", "id": "b1"},
        },
        {"id": "c1", "label": "Method", "properties": {"id": "c1"}},
    ]


def test_bucket_key_priority():
    assert (
        _bucket_key({"properties": {"year": 2021, "created_at": "2020-01-01"}})
        == "2021"
    )
    assert _bucket_key({"properties": {"created_at": "2020-06-01"}}) == "2020"
    assert _bucket_key({"properties": {}}) == "unknown"


def test_timeline_aggregation_by_year():
    relations = [
        {"source": "a1", "target": "b1", "type": "HAS_PROPERTY"},
        {"source": "a3", "target": "b1", "type": "HAS_PROPERTY"},
    ]
    out = TrendAnalysisService().analyze(_nodes(), relations)
    assert out["backend"] == "trend"
    assert out["time_field"] == "year"

    by_period = {p["period"]: p for p in out["timeline"]}
    # 2019: 2 Material；2020: 1 Material + 1 Property(created_at)；unknown: 1 Method
    assert by_period["2019"]["entity_counts"]["Material"] == 2
    assert by_period["2020"]["entity_counts"]["Property"] == 1
    assert by_period["unknown"]["entity_counts"]["Method"] == 1
    # 关系按 source 节点头归属：a1(2019) 与 a3(2020)
    assert by_period["2019"]["relation_counts"]["HAS_PROPERTY"] == 1
    assert by_period["2020"]["relation_counts"]["HAS_PROPERTY"] == 1


def test_top_entities_sorted_and_total_periods():
    out = TrendAnalysisService().analyze(_nodes(), [])
    tops = out["top_entities"]
    assert [t["count"] for t in tops] == sorted(
        (t["count"] for t in tops), reverse=True
    )
    material = next(t for t in tops if t["label"] == "Material")
    assert material["count"] == 3
    assert material["total_periods"] == 2  # 2019 与 2020 各出现


def test_coverage_counts():
    out = TrendAnalysisService().analyze(_nodes(), [])
    cov = out["coverage"]
    assert cov["total_nodes"] == 5
    assert cov["labeled"] == 4  # a1,a2,a3,b1 有年份；c1 无
    assert cov["unlabeled"] == 1
    assert cov["labeled"] + cov["unlabeled"] == cov["total_nodes"]


def test_empty_graph():
    out = TrendAnalysisService().analyze([], [])
    assert out["timeline"] == []
    assert out["top_entities"] == []
    assert out["coverage"]["total_nodes"] == 0
