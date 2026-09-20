# -*- coding: utf-8 -*-
"""置信度校准与漂移检测服务单元测试：Temperature/Platt、ECE、PSI/KS/卡方。均纯内存、零依赖。"""
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.calibration_drift_service import (
    CalibrationDriftService,
    softmax,
    sigmoid,
    fit_temperature,
    fit_platt,
    platt_calibrate,
    expected_calibration_error,
    reliability_curve,
    psi,
    ks_statistic,
    chi_square_drift,
    classify_psi,
)


def test_softmax_sums_to_one():
    probs = softmax([1.0, 2.0, 3.0])
    assert abs(sum(probs) - 1.0) < 1e-9


def test_softmax_temperature_flattens():
    sharp = softmax([1.0, 0.0], 1.0)
    flat = softmax([1.0, 0.0], 10.0)
    assert max(sharp) > max(flat)
    assert min(flat) > 0.4


def test_sigmoid_bounds_and_monotonic():
    assert 0.0 < sigmoid(-5.0) < 0.01
    assert 0.99 < sigmoid(5.0) < 1.0
    assert sigmoid(0.0) == 0.5


def test_fit_temperature_valid():
    logits = [[2.0, 1.0], [1.0, 2.0], [0.0, 3.0]]
    labels = [0, 1, 1]
    t, nll = fit_temperature(logits, labels)
    assert t >= 0.2
    assert nll >= 0.0


def test_platt_separable_positive_slope():
    scores = [0.1, 0.2, 0.3, 0.9, 0.95]
    labels = [0, 0, 0, 1, 1]
    a, b = fit_platt(scores, labels)
    assert a > 0.0
    probs = platt_calibrate(scores, a, b)
    assert probs[0] < 0.5 < probs[-1]


def test_ece_perfect_known_value():
    # 2 箱：conf [0.1,0.1] acc 0、conf[0.9,0.9] acc 1 → ECE = 0.5*0.1 + 0.5*0.1 = 0.1
    ece = expected_calibration_error([0.9, 0.9, 0.1, 0.1], [1, 1, 0, 0], n_bins=2)
    assert abs(ece - 0.1) < 1e-9


def test_ece_well_calibrated_low():
    ece = expected_calibration_error([1.0, 0.0], [1, 0], n_bins=2)
    assert ece < 0.05


def test_reliability_curve_shape():
    curve = reliability_curve([0.9, 0.1], [1, 0], n_bins=2)
    assert len(curve) == 2
    assert curve[0]["range"] == [0.0, 0.5]


def test_psi_identical_zero():
    assert abs(psi(list(range(1, 11)), list(range(1, 11)))) < 1e-9


def test_psi_drift_positive():
    value = psi([0.1, 0.2, 0.3], [0.8, 0.9, 1.0])
    assert value > 0.1


def test_ks_identical_zero():
    assert ks_statistic([1, 2, 3], [1, 2, 3]) == 0.0


def test_ks_separated_one():
    assert ks_statistic([1, 1, 1], [2, 2, 2]) == 1.0


def test_chi_square_identical_zero():
    assert chi_square_drift({"A": 10, "B": 10}, {"A": 10, "B": 10}) == 0.0


def test_chi_square_drift_positive():
    assert chi_square_drift({"A": 10, "B": 10}, {"A": 5, "B": 15}) > 0.0


def test_classify_psi_thresholds():
    assert classify_psi(0.05) == "stable"
    assert classify_psi(0.15) == "warning"
    assert classify_psi(0.3) == "drift"


def test_service_calibrate_temperature():
    svc = CalibrationDriftService()
    out = svc.calibrate(method="temperature", logits=[[1.0, 0.0]], temperature=1.0)
    assert out["ok"] is True
    assert abs(sum(out["probs"][0]) - 1.0) < 1e-9


def test_service_detect_drift_stable_vs_drift():
    svc = CalibrationDriftService()
    ref = [float(i) / 10 for i in range(10)]
    assert svc.detect_drift(ref, ref.copy(), method="psi")["status"] == "stable"
    drift = svc.detect_drift(ref, [x + 2.0 for x in ref], method="psi")
    assert drift["status"] == "drift"