# -*- coding: utf-8 -*-
"""A/B 测试服务单元测试：流量分流 / 指标采集 / 统计显著性判定。纯内存零依赖。"""
import os
import sys

import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.ab_test_service import (
    ABTestService,
    _ibeta,
    _normal_cdf,
    _t_cdf,
    proportion_z_test,
    welch_ttest,
)


def _svc() -> ABTestService:
    """每个测试独立实例，隔离内存状态。"""
    return ABTestService()


# ── 统计工具正确性 ────────────────────────────────────────────────
def test_normal_cdf():
    assert _normal_cdf(0.0) == pytest.approx(0.5, abs=1e-12)
    assert _normal_cdf(1.96) == pytest.approx(0.975002, abs=1e-4)


def test_ibeta_symmetric():
    assert _ibeta(1.0, 1.0, 0.5) == pytest.approx(0.5, abs=1e-9)


def test_t_cdf_center_is_half():
    assert _t_cdf(0.0, 10) == pytest.approx(0.5, abs=1e-12)
    # 大自由度下逼近正态
    assert _t_cdf(1.96, 1000) == pytest.approx(0.975, abs=1e-3)


def test_proportion_z_test_equal_rates_not_significant():
    r = proportion_z_test(10, 20, 10, 20)
    assert r["z"] == pytest.approx(0.0, abs=1e-12)
    assert r["p_value"] == pytest.approx(1.0, abs=1e-9)


def test_welch_ttest_identical_distributions():
    a = [1.0, 2.0, 3.0, 4.0, 5.0]
    b = [1.0, 2.0, 3.0, 4.0, 5.0]
    r = welch_ttest(3.0, 2.5, 5, 3.0, 2.5, 5)
    assert r["t"] == pytest.approx(0.0, abs=1e-12)
    assert r["p_value"] == pytest.approx(1.0, abs=1e-9)


# ── 流量分流 ─────────────────────────────────────────────────────
def test_assign_is_deterministic():
    svc = _svc()
    svc.create_experiment("e1", ["A", "B"], weights=[1, 1])
    first = svc.assign("ab-0001", "user-7")["variant"]
    for _ in range(3):
        assert svc.assign("ab-0001", "user-7")["variant"] == first


def test_assign_defaults_to_control_when_experiment_id_missing():
    svc = _svc()
    with pytest.raises(KeyError):
        svc.assign("nope", "user-1")


def test_assign_weighted_split_monotonic():
    svc = _svc()
    svc.create_experiment("e2", ["low", "mid", "high"], weights=[1, 2, 3])
    counts = {"low": 0, "mid": 0, "high": 0}
    for i in range(3000):
        v = svc.assign("ab-0001", f"subject-{i}")["variant"]
        counts[v] += 1
    assert counts["high"] > counts["mid"] > counts["low"]
    assert sum(counts.values()) == 3000


# ── 实验创建与校验 ───────────────────────────────────────────────
def test_create_experiment_requires_two_variants():
    svc = _svc()
    with pytest.raises(ValueError):
        svc.create_experiment("e", ["only-one"])


def test_create_experiment_rejects_duplicate_variants():
    svc = _svc()
    with pytest.raises(ValueError):
        svc.create_experiment("e", ["A", "A"])


def test_create_experiment_rejects_weight_mismatch():
    svc = _svc()
    with pytest.raises(ValueError):
        svc.create_experiment("e", ["A", "B"], weights=[1])


def test_record_rejects_unknown_variant():
    svc = _svc()
    svc.create_experiment("e", ["A", "B"])
    with pytest.raises(ValueError):
        svc.record("ab-0001", "C", 1)


# ── 统计显著性判定 ───────────────────────────────────────────────
def test_evaluate_binary_significant_winner():
    svc = _svc()
    svc.create_experiment("ctr", ["control", "treatment"], metric_type="binary")
    for i in range(50):
        svc.record("ab-0001", "control", 1 if i < 20 else 0)  # 成功率 40%
        svc.record("ab-0001", "treatment", 1 if i < 40 else 0)  # 成功率 80%
    r = svc.evaluate("ab-0001")
    assert r["min_samples_met"] is True
    assert r["significant"] is True
    assert r["winner"] == "treatment"
    assert r["p_value"] < 0.05
    assert r["effect_size"] > 0


def test_evaluate_continuous_minimize_latency_winner():
    svc = _svc()
    svc.create_experiment("latency", ["v1", "v2"], metric_type="continuous", minimize=True)
    for i in range(40):
        svc.record("ab-0001", "v1", 100.0 + (i % 5) * 1.0)  # ~102ms
        svc.record("ab-0001", "v2", 80.0 + (i % 5) * 1.0)  # ~82ms
    r = svc.evaluate("ab-0001")
    assert r["min_samples_met"] is True
    assert r["significant"] is True
    assert r["winner"] == "v2"
    assert r["effect_size"] < 0  # 延迟越低越好


def test_evaluate_sample_insufficient():
    svc = _svc()
    svc.create_experiment("few", ["A", "B"], metric_type="binary")
    for _ in range(5):
        svc.record("ab-0001", "A", 1)
        svc.record("ab-0001", "B", 1)
    r = svc.evaluate("ab-0001")
    assert r["min_samples_met"] is False
    assert r["winner"] is None
    assert "样本量不足" in r["conclusion"]


def test_evaluate_not_significant_when_equal():
    svc = _svc()
    svc.create_experiment("eq", ["A", "B"], metric_type="binary")
    for i in range(50):
        svc.record("ab-0001", "A", 1 if i < 25 else 0)
        svc.record("ab-0001", "B", 1 if i < 25 else 0)
    r = svc.evaluate("ab-0001")
    assert r["significant"] is False
    assert r["winner"] is None
    assert r["p_value"] >= r["alpha"]
