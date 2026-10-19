# -*- coding: utf-8 -*-
"""A/B 测试与模型版本路由测试（步骤 14.4 / 14.5）。

覆盖：变体命名解析、分流一致性、模型版本解析（命中/各类降级）、推理延迟与 F1 采集回读、
样本不足提示、显著性结论与延迟方向覆盖。
"""
from app.core.config import settings
from app.services.ab_test_service import ABTestService, make_variant, parse_variant
from app.services.version_management_service import version_management_service


def _new_experiment(
    model_name: str, variants: list[str] | None = None, metric_type: str = "binary"
):
    """构造一个隔离的 A/B 服务实例与实验（变体缺省为 `<model>-v1` / `<model>-v2`）。"""
    svc = ABTestService()
    variants = variants or [make_variant(model_name, 1), make_variant(model_name, 2)]
    exp = svc.create_experiment(f"{model_name}-ab", variants=variants, metric_type=metric_type)
    return svc, exp


def _subject_for_variant(svc: ABTestService, experiment_id: str, variant: str) -> str | None:
    """探测一个能稳定路由到目标变体的 subject（最多 500 次）。"""
    for i in range(500):
        subject = f"probe-{i}"
        if svc.assign(experiment_id, subject)["variant"] == variant:
            return subject
    return None


# ── 命名约定 ──────────────────────────────────────────────────────────
def test_parse_and_make_variant():
    """变体标识 `<model>-v<int>` 可解析且可构造。"""
    assert make_variant("ner", 2) == "ner-v2"
    assert parse_variant("ner-v2") == ("ner", 2)
    assert parse_variant("ner") is None
    assert parse_variant("") is None


def test_ab_test_service_importable():
    """A/B 服务可导入且可实例化。"""
    assert ABTestService() is not None


# ── 分流 ──────────────────────────────────────────────────────────────
def test_assign_returns_valid_variant():
    """分流应返回实验中的有效变体。"""
    svc, exp = _new_experiment("assign-check")
    result = svc.assign(exp["id"], "user-1")
    assert result["variant"] in exp["variants"]


def test_assign_is_deterministic_per_subject():
    """同一 subject 重复分流必须稳定到同一变体。"""
    svc, exp = _new_experiment("assign-stable")
    first = svc.assign(exp["id"], "subject-1")["variant"]
    for _ in range(5):
        assert svc.assign(exp["id"], "subject-1")["variant"] == first


# ── 模型版本解析 ──────────────────────────────────────────────────────
def test_resolve_model_version_hits_registered_version():
    """分流命中的变体版本已注册时应返回对应版本产物。"""
    model = "route-registered"
    version_management_service.register_model(model, artifacts={"path": "v1"})
    version_management_service.register_model(model, artifacts={"path": "v2"})
    svc, exp = _new_experiment(model)

    res = svc.resolve_model_version(model, "subject-x", exp["id"])

    assert res["degraded"] is False
    assert res["reason"] == "ab_test"
    assert res["model_version"] in (1, 2)
    assert res["variant"] == make_variant(model, res["model_version"])
    assert res["artifacts"]["path"] == f"v{res['model_version']}"


def test_resolve_model_version_auto_matches_experiment():
    """未指定 experiment_id 时应自动匹配该模型的实验。"""
    model = "route-automatch"
    version_management_service.register_model(model, artifacts={"path": "v1"})
    version_management_service.register_model(model, artifacts={"path": "v2"})
    svc, exp = _new_experiment(model)

    res = svc.resolve_model_version(model, "subject-x")

    assert res["experiment_id"] == exp["id"]
    assert res["degraded"] is False


def test_resolve_model_version_degrades_when_version_missing():
    """命中的变体版本未注册时应降级回退 Production/最新版本。"""
    model = "route-missing-version"
    version_management_service.register_model(model, artifacts={"path": "only"})
    svc, exp = _new_experiment(model, variants=[make_variant(model, 1), make_variant(model, 99)])
    subject = _subject_for_variant(svc, exp["id"], make_variant(model, 99))
    assert subject is not None

    res = svc.resolve_model_version(model, subject, exp["id"])

    assert res["degraded"] is True
    assert res["reason"] == "model_version_not_registered"
    assert res["model_version"] == 1  # 回退到唯一注册版本


def test_resolve_model_version_degrades_when_model_absent():
    """模型无任何注册版本时降级且版本为空。"""
    model = "route-absent"
    svc, exp = _new_experiment(model)

    res = svc.resolve_model_version(model, "subject-x", exp["id"])

    assert res["degraded"] is True
    assert res["reason"] == "model_not_registered"
    assert res["model_version"] is None
    assert res["artifacts"] == {}


def test_resolve_model_version_degrades_when_experiment_missing():
    """实验不存在时降级。"""
    res = ABTestService().resolve_model_version("route-no-exp", "subject-x", "ab-not-exist")
    assert res["degraded"] is True
    assert res["reason"] == "experiment_not_found"


def test_resolve_model_version_degrades_when_ab_disabled(monkeypatch):
    """A/B 服务禁用时降级（不抛错）。"""
    monkeypatch.setattr(settings, "AB_TEST_ENABLED", False)
    svc, exp = _new_experiment("route-disabled")

    res = svc.resolve_model_version("route-disabled", "subject-x", exp["id"])

    assert res["degraded"] is True
    assert res["reason"] == "ab_test_disabled"


def test_resolve_model_version_degrades_on_variant_mismatch():
    """变体与请求模型不匹配时降级。"""
    svc = ABTestService()
    exp = svc.create_experiment("route-mismatch-ab", variants=["other-v1", "other-v2"])

    res = svc.resolve_model_version("route-mismatch", "subject-x", exp["id"])

    assert res["degraded"] is True
    assert res["reason"] == "variant_model_mismatch"


# ── 推理观测采集 ──────────────────────────────────────────────────────
def test_record_inference_observation_roundtrip():
    """延迟与 F1 两类观测应分别落入对应指标序列。"""
    svc, exp = _new_experiment("route-obs")

    out = svc.record_inference_observation(exp["id"], "route-obs-v1", latency_ms=12.5, f1=0.9)

    assert len(out["recorded"]) == 2
    obs = svc.get_experiment(exp["id"])["observations"]["route-obs-v1"]
    assert obs["latency_ms"] == [12.5]
    assert obs["f1"] == [0.9]


# ── 显著性判定 ────────────────────────────────────────────────────────
def test_min_samples_threshold_config():
    """配置项默认样本量门槛为 30。"""
    assert settings.AB_TEST_MIN_SAMPLES == 30


def test_evaluate_hints_when_samples_insufficient():
    """样本不足时应返回提示而非结论。"""
    svc, exp = _new_experiment("route-small")
    svc.record(exp["id"], "route-small-v1", 1)
    svc.record(exp["id"], "route-small-v2", 0)

    res = svc.evaluate(exp["id"])

    assert res["min_samples_met"] is False
    assert res["winner"] is None
    assert "样本" in res["conclusion"]


def test_evaluate_gives_significant_conclusion():
    """样本充足且差异显著时给出胜者与 p 值。"""
    svc, exp = _new_experiment("route-sig", variants=["route-sig-v1", "route-sig-v2"])
    for _ in range(40):
        svc.record(exp["id"], "route-sig-v1", 1)
        svc.record(exp["id"], "route-sig-v2", 0)

    res = svc.evaluate(exp["id"])

    assert res["min_samples_met"] is True
    assert res["significant"] is True
    assert res["winner"] == "route-sig-v1"
    assert res["p_value"] < 0.05


def test_evaluate_latency_minimize_override():
    """延迟指标以 minimize=True 判定，延迟更小者胜。"""
    svc, exp = _new_experiment("route-latency", metric_type="continuous")
    for i in range(40):
        svc.record_inference_observation(exp["id"], "route-latency-v1", latency_ms=100.0 + (i % 2))
        svc.record_inference_observation(exp["id"], "route-latency-v2", latency_ms=50.0 + (i % 2))

    res = svc.evaluate(exp["id"], metric_name="latency_ms", minimize=True)

    assert res["minimize"] is True
    assert res["significant"] is True
    assert res["winner"] == "route-latency-v2"
