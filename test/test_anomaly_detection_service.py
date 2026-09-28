# -*- coding: utf-8 -*-
"""异常检测服务测试：孤立/超连通/低连通命中、密度、除零保护。"""
from app.services.anomaly_detection_service import AnomalyDetectionService, _density


def _star_with_isolated():
    """中心节点连接多个叶子，另加一个孤立节点。"""
    nodes = [
        {"id": "hub", "label": "Hub", "properties": {"year": 2020, "id": "hub"}},
    ]
    nodes += [
        {
            "id": f"leaf{i}",
            "label": "Leaf",
            "properties": {"year": 2020, "id": f"leaf{i}"},
        }
        for i in range(10)
    ]
    nodes += [
        {"id": "iso", "label": "Isolated", "properties": {"year": 2021, "id": "iso"}},
    ]
    relations = [
        {"source": "hub", "target": f"leaf{i}", "type": "LINKS"} for i in range(10)
    ]
    return nodes, relations


def test_isolated_hit():
    nodes, relations = _star_with_isolated()
    out = AnomalyDetectionService().detect(nodes, relations)
    assert out["backend"] == "anomaly"
    iso_ids = {nd["id"] for nd in out["isolated"]["nodes"]}
    assert "iso" in iso_ids
    assert out["isolated"]["count"] == 1


def test_high_connectivity_hit():
    nodes, relations = _star_with_isolated()
    out = AnomalyDetectionService().detect(nodes, relations)
    high_ids = {nd["id"] for nd in out["high_connectivity"]["nodes"]}
    assert "hub" in high_ids  # 度=10，显著高于均值
    assert out["anomalies"]
    kinds = {a["kind"] for a in out["anomalies"]}
    assert "high_connectivity" in kinds and "isolated" in kinds


def test_density_positive_and_no_isolated_degree_bug():
    nodes, relations = _star_with_isolated()
    out = AnomalyDetectionService().detect(nodes, relations)
    assert out["density"]["overall"] > 0
    # 孤立节点不应进入 high/low 列表
    low_high = list(out["high_connectivity"]["nodes"]) + list(
        out["low_connectivity"]["nodes"]
    )
    assert all(nd["id"] != "iso" for nd in low_high)


def test_empty_graph_no_error():
    out = AnomalyDetectionService().detect([], [])
    assert out["isolated"]["count"] == 0
    assert out["anomalies"] == []
    assert out["density"]["overall"] == 0.0
    assert out["density"]["per_period"] == []


def test_single_node_no_division_error():
    out = AnomalyDetectionService().detect(
        [{"id": "x", "label": "X", "properties": {}}], []
    )
    assert out["isolated"]["count"] == 1
    assert out["density"]["overall"] == 0.0


def test_density_helper():
    assert _density(0, 0) == 0.0
    assert _density(0, 1) == 0.0  # 单节点防除零
    assert _density(1, 2) == 1.0  # 单边两节点密度 1
    assert abs(_density(1, 3) - (1 / 3)) < 1e-9
