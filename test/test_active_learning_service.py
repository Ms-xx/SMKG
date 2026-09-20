# -*- coding: utf-8 -*-
"""主动学习采样服务单元测试：不确定性 / 多样性 / QBC / 混合。均纯内存、零依赖。"""
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.active_learning_service import (
    ActiveLearningService,
    entropy,
    least_confidence,
    margin,
    vote_entropy,
    disagreement,
    core_set_indices,
    kmeans_pp_indices,
)

SAMPLES = [
    {"id": "a", "probs": [0.9, 0.1]},
    {"id": "b", "probs": [0.5, 0.5]},
    {"id": "c", "probs": [0.33, 0.33, 0.34]},
]

FEAT_SAMPLES = [
    {"id": "p1", "features": [0.0, 0.0]},
    {"id": "p2", "features": [0.1, 0.1]},
    {"id": "p3", "features": [1.0, 1.0]},
]

QBC_SAMPLES = [
    {"id": "q1", "predictions": [[0.9, 0.1], [0.9, 0.1], [0.9, 0.1]]},
    {"id": "q2", "predictions": [[0.9, 0.1], [0.1, 0.9], [0.9, 0.1]]},
    {"id": "q3", "predictions": [[0.9, 0.1], [0.1, 0.9], [0.2, 0.8]]},
]


def test_entropy_uniform_is_max():
    assert abs(entropy([0.5, 0.5]) - 1.0) < 1e-9
    assert abs(entropy([1.0, 0.0]) - 0.0) < 1e-9


def test_least_confidence():
    assert abs(least_confidence([0.9, 0.1]) - 0.1) < 1e-9


def test_margin():
    assert abs(margin([0.9, 0.1]) - 0.2) < 1e-9
    assert abs(margin([0.5, 0.5]) - 1.0) < 1e-9


def test_select_uncertainty_entropy_top():
    out = ActiveLearningService().select(SAMPLES, strategy="uncertainty", top_k=1)
    assert out["results"][0]["id"] == "c"


def test_select_uncertainty_margin_top():
    out = ActiveLearningService().select(
        SAMPLES, strategy="uncertainty", top_k=1, uncertainty_method="margin"
    )
    assert out["results"][0]["id"] == "b"


def test_core_set_picks_farthest():
    assert core_set_indices([[0, 0], [0.1, 0.1], [1, 1]], 2) == [0, 2]


def test_kmeans_pp_deterministic():
    idx = kmeans_pp_indices([[0, 0], [0.1, 0.1], [1, 1]], 3, seed=42)
    assert idx[0] == 0 and len(idx) == 3 and len(set(idx)) == 3


def test_select_diversity():
    out = ActiveLearningService().select(
        FEAT_SAMPLES, strategy="diversity", top_k=2, diversity_method="core_set"
    )
    assert [r["id"] for r in out["results"]] == ["p1", "p3"]


def test_vote_entropy_ranks_disagreement():
    assert vote_entropy(QBC_SAMPLES[2]["predictions"]) > vote_entropy(
        QBC_SAMPLES[0]["predictions"]
    )
    assert disagreement(QBC_SAMPLES[0]["predictions"]) == 0.0
    assert disagreement(QBC_SAMPLES[2]["predictions"]) > 0.0


def test_select_qbc_top():
    out = ActiveLearningService().select(
        QBC_SAMPLES, strategy="qbc", top_k=1, qbc_method="vote_entropy"
    )
    assert out["results"][0]["id"] == "q3"


def test_select_hybrid_returns_selected():
    hybrid = [
        {"id": "h1", "probs": [0.9, 0.1], "features": [0.0, 0.0]},
        {"id": "h2", "probs": [0.5, 0.5], "features": [0.1, 0.1]},
        {"id": "h3", "probs": [0.33, 0.33, 0.34], "features": [1.0, 1.0]},
    ]
    out = ActiveLearningService().select(hybrid, strategy="hybrid", top_k=2)
    assert out["strategy"] == "hybrid"
    assert out["selected"] == 2
    assert len(out["results"]) == 2