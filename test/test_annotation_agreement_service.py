# -*- coding: utf-8 -*-
"""标注一致性评估服务单元测试：Cohen's / Fleiss' / Krippendorff。均纯内存、零依赖。"""
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.annotation_agreement_service import (
    AnnotationAgreementService,
    cohens_kappa,
    fleiss_kappa,
    krippendorff_alpha,
)


def test_cohens_kappa_perfect():
    assert abs(cohens_kappa(["A", "A", "B"], ["A", "A", "B"]) - 1.0) < 1e-9


def test_cohens_kappa_no_agreement():
    assert abs(cohens_kappa(["A", "A", "B", "B"], ["A", "B", "A", "B"]) - 0.0) < 1e-9


def test_cohens_kappa_skips_missing():
    assert abs(cohens_kappa(["A", None, "B"], ["A", "A", "B"]) - 1.0) < 1e-9


def test_fleiss_kappa_perfect():
    assert abs(fleiss_kappa([["A", "A", "A"], ["B", "B", "B"]]) - 1.0) < 1e-9


def test_fleiss_kappa_known_value():
    # 3 标注员、2 样本、2 类别：手算结果 -1/3
    assert abs(fleiss_kappa([["A", "A", "B"], ["A", "B", "B"]]) - (-1.0 / 3.0)) < 1e-6


def test_fleiss_kappa_single_category():
    assert abs(fleiss_kappa([["A", "A"], ["A", "A"]]) - 1.0) < 1e-9


def test_krippendorff_nominal_perfect():
    assert abs(krippendorff_alpha([["A", "A"], ["B", "B"]]) - 1.0) < 1e-9


def test_krippendorff_nominal_known_value():
    assert abs(krippendorff_alpha([["A", "B"], ["B", "A"]], "nominal") - (-0.5)) < 1e-6


def test_krippendorff_interval_known_value():
    assert abs(krippendorff_alpha([[0, 0], [1, 1], [0, 2]], "interval") - 0.0) < 1e-9


def test_evaluate_all_metrics():
    out = AnnotationAgreementService().evaluate([["A", "A"], ["A", "B"]])
    assert out["n_subjects"] == 2
    assert out["n_raters"] == 2
    assert "cohens_kappa" in out
    assert "fleiss_kappa" in out
    assert "krippendorff_alpha" in out
    assert out["krippendorff_metric"] == "nominal"


def test_evaluate_metric_filter():
    out = AnnotationAgreementService().evaluate([["A", "A"], ["A", "B"]], metrics=["fleiss"])
    assert "fleiss_kappa" in out
    assert "cohens_kappa" not in out
    assert "krippendorff_alpha" not in out