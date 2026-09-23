# -*- coding: utf-8 -*-
"""
GNN 链路预测（步骤 10）单元测试。

覆盖：GNNLinkPredictor 训练与排序、门面服务 gnn 后端、三元组过少降级 statistical。
均为内存三元组，不触发网络与 Neo4j。
"""
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import pytest  # noqa: E402

from app.services.relation_inference_service import (  # noqa: E402
    GNNLinkPredictor,
    RelationInferenceService,
)

FACTS = [
    {"head": "method_A", "relation": "PRODUCES", "tail": "mat_A"},
    {"head": "method_B", "relation": "PRODUCES", "tail": "mat_B"},
    {"head": "mat_A", "relation": "ACHIEVES", "tail": "prop_A"},
    {"head": "mat_B", "relation": "ACHIEVES", "tail": "prop_B"},
    {"head": "mat_A", "relation": "EXHIBITS", "tail": "prop_C"},
    {"head": "etl_A", "relation": "TRANSPORTS_HOLE", "tail": "mat_A"},
    {"head": "etl_B", "relation": "TRANSPORTS_ELECTRON", "tail": "mat_B"},
    {"head": "prop_A", "relation": "REQUIRES", "tail": "prop_C"},
]


def test_gnn_trains_and_ranks_known_tail():
    """GNN 训练后：正样本打分应高于明显无关的尾实体。"""
    pred = GNNLinkPredictor(dim=20, layers=2, epochs=120).fit(FACTS)
    assert pred.trained is True
    pos = pred.score_triple("method_A", "PRODUCES", "mat_A")
    neg = pred.score_triple("method_A", "PRODUCES", "prop_A")
    assert pos > neg


def test_gnn_predict_links_excludes_existing():
    """GNN 链路预测不返回已存在的事实。"""
    pred = GNNLinkPredictor(dim=20, layers=2, epochs=120).fit(FACTS)
    cands = pred.predict_links(
        "etl_A", "TRANSPORTS_HOLE", top_k=5, exclude={("etl_A", "TRANSPORTS_HOLE", "mat_A")}
    )
    assert "mat_A" not in {c["entity"] for c in cands}


def test_service_backend_gnn(monkeypatch):
    """后端设为 gnn 时，链路预测使用 gnn 后端。"""
    from app.core.config import settings

    monkeypatch.setattr(settings, "RELATION_INFERENCE_BACKEND", "gnn")
    svc = RelationInferenceService()
    result = svc.predict_links("method_A", "PRODUCES", FACTS, top_k=3)
    assert result["backend"] == "gnn"
    assert all("entity" in c and "score" in c for c in result["candidates"])


def test_gnn_degrades_to_statistical_on_few_triples(monkeypatch):
    """三元组过少（<2 且 <3）时，gnn 后端降级到 statistical。"""
    from app.core.config import settings

    monkeypatch.setattr(settings, "RELATION_INFERENCE_BACKEND", "gnn")
    svc = RelationInferenceService()
    result = svc.predict_links("x", "r", [("x", "r", "y")], top_k=3)
    assert result["backend"] == "statistical"