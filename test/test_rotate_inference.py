# -*- coding: utf-8 -*-
"""RotatE 关系推理单测（步骤 17.3）。"""
from app.services.relation_inference_service import (
    RotatELinkPredictor,
    StatisticalLinkPredictor,
    _NUMPY_AVAILABLE,
)


TRIPLES = [
    ("钙钛矿", "PRODUCES", "高效率"),
    ("钙钛矿", "EXHIBITS", "稳定性"),
    ("GNN", "PRODUCES", "高效率"),
    ("GNN", "EXHIBITS", "可解释性"),
    ("TransE", "PRODUCES", "高效率"),
    ("TransE", "EXHIBITS", "稳定性"),
]


def test_rotate_score_monotonicity():
    """训练后已知三元组得分应高于未知三元组。"""
    if not _NUMPY_AVAILABLE:
        return
    pred = RotatELinkPredictor(dim=16, epochs=50, seed=42).fit(TRIPLES)
    assert pred.trained
    known = pred.score_triple("钙钛矿", "PRODUCES", "高效率")
    # 未知实体返回 -inf
    unknown = pred.score_triple("UnknownEntity", "PRODUCES", "高效率")
    assert known > unknown


def test_rotate_training_convergence():
    """训练应能完成并标记 trained=True。"""
    if not _NUMPY_AVAILABLE:
        return
    pred = RotatELinkPredictor(dim=16, epochs=30, seed=42).fit(TRIPLES)
    assert pred.trained is True
    # predict_links 应返回 top-k 候选
    cands = pred.predict_links("钙钛矿", "PRODUCES", top_k=3)
    assert isinstance(cands, list)
    assert len(cands) <= 3


def test_rotate_degradation_insufficient_triples():
    """三元组不足（< 3）时应降级为未训练态。"""
    pred = RotatELinkPredictor(dim=16, epochs=10).fit([("a", "r", "b")])
    assert pred.trained is False
    assert pred.score_triple("a", "r", "b") == float("-inf")


def test_rotate_predict_links_unknown_head():
    """未知头实体应返回空列表。"""
    if not _NUMPY_AVAILABLE:
        return
    pred = RotatELinkPredictor(dim=16, epochs=20, seed=42).fit(TRIPLES)
    assert pred.predict_links("UnknownHead", "PRODUCES", top_k=5) == []


def test_rotate_interface_alignment_with_transe():
    """RotatE 应与 TransE 接口对齐（fit/score_triple/predict_links 三方法）。"""
    pred = RotatELinkPredictor()
    assert hasattr(pred, "fit")
    assert hasattr(pred, "score_triple")
    assert hasattr(pred, "predict_links")
    assert hasattr(pred, "trained")


def test_statistical_fallback_still_works():
    """统计基线应仍可工作（降级链终点）。"""
    pred = StatisticalLinkPredictor().fit(TRIPLES)
    s = pred.score_triple("钙钛矿", "PRODUCES", "高效率")
    assert s == 1.0  # 已知事实
