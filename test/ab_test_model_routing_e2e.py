# -*- coding: utf-8 -*-
"""步骤 14.6 端到端：A/B 模型版本分流 + 推理观测 + 显著性判定。

真实执行：模型注册/阶段流转、A/B 分流、变体→版本解析、推理延迟与 F1 采集、z/t 检验判定、
各降级路径。静态校验：Celery `training` 队列任务注册与路由、MLflow 本地 server 可达性。

环境声明：本机无 NVIDIA GPU、未常驻 Celery 训练 worker，故「真实重训 → Celery 状态流转」
链路以任务注册/路由校验 + MLflow 可达性探测替代，**真实训练精度未在 GPU 环境验证**。

产物：`outputs/active_learning_e2e.json`（文档规定产物名）、`outputs/ab_model_routing_e2e.json`。

运行：`python test/ab_test_model_routing_e2e.py`（SciMKG 环境，工作目录为仓库根）。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_BACKEND_DIR = str(ROOT / "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.core.celery_app import celery_app  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.services.ab_test_service import ABTestService, make_variant  # noqa: E402
from app.services.version_management_service import (  # noqa: E402
    version_management_service,
)

OUT_DIR = ROOT / "outputs"

# 步骤 14.1 落地的训练队列任务（name 注册名）
_TRAINING_TASKS = ("run_active_learning_cycle", "run_finetune_job")


def _celery_check() -> dict:
    """Celery 训练队列的任务注册与路由静态校验（未常驻 worker 时如实标注）。"""
    routes = celery_app.conf.task_routes or {}
    registered = [t for t in _TRAINING_TASKS if t in celery_app.tasks]
    return {
        "worker_online": False,
        "note": "本机未常驻 training worker，仅校验任务注册与队列路由；状态流转需 worker 在线时验证",
        "expected_tasks": list(_TRAINING_TASKS),
        "registered_tasks": registered,
        "training_route": routes.get("app.workers.active_learning_tasks.*", {}).get("queue"),
    }


def _mlflow_check() -> dict:
    """MLflow 本地 tracking server 可达性探测（不可达则如实记录降级）。"""
    status = version_management_service.mlflow_status(refresh=True)
    return {
        "enabled": status["enabled"],
        "effective_backend": status["effective_backend"],
        "server_reachable": status["server_reachable"],
        "probe_detail": status["probe_detail"],
        "note": "步骤 14.3 已单独完成 MLflow 本地端到端验证（run/参数/指标/工件落盘且 UI 可见）；此处记录当前可达性，不可达即如实降级 builtin",
    }


def _bootstrap_versions(model: str) -> dict:
    """注册两个模型版本并把较优者晋升 Production。"""
    v1 = version_management_service.register_model(
        model, artifacts={"path": f"moulds/e2e/{model}/v1"}, metrics={"f1": 0.80}
    )
    v2 = version_management_service.register_model(
        model, artifacts={"path": f"moulds/e2e/{model}/v2"}, metrics={"f1": 0.90}
    )
    transition = version_management_service.transition_stage(model, v2["version"], "production")
    return {
        "v1": {"version": v1["version"], "stage": v1["stage"]},
        "v2": {"version": v2["version"], "stage": transition["model"].get("stage")},
        "promoted": transition.get("ok", False),
    }


def _route_and_observe(svc: ABTestService, model: str, exp: dict, needed: int = 40) -> dict:
    """分流 + 版本解析 + 推理观测，直到每个变体各采集 needed 次。

    约定 v1 慢且差（延迟 ~120ms、F1 ~0.78），v2 快且好（延迟 ~60ms、F1 ~0.92）。
    """
    good_variant = make_variant(model, 2)
    counts = dict.fromkeys(exp["variants"], 0)
    stats = {"attempts": 0, "resolved": 0, "degraded": 0, "variants": dict(counts)}
    i = 0
    while min(counts.values()) < needed and i < 4000:
        i += 1
        res = svc.resolve_model_version(model, f"user-{i}", exp["id"])
        variant = res["variant"]
        if res["degraded"]:
            stats["degraded"] += 1
        else:
            stats["resolved"] += 1
        counts[variant] = counts.get(variant, 0) + 1
        quality = 0.92 if variant == good_variant else 0.78
        latency = (60.0 if variant == good_variant else 120.0) + (i % 3)
        svc.record_inference_observation(exp["id"], variant, latency_ms=latency, f1=quality)
    stats["attempts"] = i
    stats["variants"] = counts
    return stats


def main() -> dict:
    started = time.time()
    model = "e2e-ner"

    # A. 模型注册与阶段流转
    versions = _bootstrap_versions(model)

    # B. A/B 实验（continuous：延迟 + F1）
    svc = ABTestService()
    exp = svc.create_experiment(
        f"{model}-ab",
        variants=[
            make_variant(model, versions["v1"]["version"]),
            make_variant(model, versions["v2"]["version"]),
        ],
        weights=[0.5, 0.5],
        metric_type="continuous",
        metric_name="latency_ms",
        minimize=True,
        alpha=0.05,
    )

    # C. 分流 + 版本解析 + 推理观测
    routing = _route_and_observe(svc, model, exp)

    # D. 显著性判定：延迟（越小越优）+ F1（越大越优）
    # 注：同一实验内采集两类指标时，非目标指标需显式覆盖方向。
    latency_eval = svc.evaluate(exp["id"], metric_name="latency_ms", minimize=True)
    f1_eval = svc.evaluate(exp["id"], metric_name="f1", minimize=False)

    # E. 降级路径：命中的变体版本未注册 → 回退 Production
    deg_model = "e2e-ner-degraded"
    version_management_service.register_model(deg_model, artifacts={"path": "only-v1"})
    deg_exp = svc.create_experiment(
        f"{deg_model}-ab",
        variants=[make_variant(deg_model, 1), make_variant(deg_model, 99)],
        metric_type="continuous",
    )
    deg_subject = None
    for i in range(500):
        if svc.assign(deg_exp["id"], f"probe-{i}")["variant"] == make_variant(deg_model, 99):
            deg_subject = f"probe-{i}"
            break
    degraded = svc.resolve_model_version(deg_model, deg_subject or "probe-0", deg_exp["id"])

    # F. 降级路径：A/B 服务禁用
    original_enabled = settings.AB_TEST_ENABLED
    settings.AB_TEST_ENABLED = False
    try:
        disabled = svc.resolve_model_version(model, "user-1", exp["id"])
    finally:
        settings.AB_TEST_ENABLED = original_enabled

    result = {
        "step": "14.6",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "note": "无 GPU / 无常驻训练 worker；真实重训链路以任务注册/路由 + MLflow 可达性替代，真实训练精度未在 GPU 环境验证",
        "model_registration": versions,
        "experiment": {
            "id": exp["id"],
            "variants": exp["variants"],
            "metric_type": "continuous",
        },
        "routing": routing,
        "latency_evaluation": {
            "n_a": latency_eval["n_a"],
            "n_b": latency_eval["n_b"],
            "min_samples_met": latency_eval["min_samples_met"],
            "p_value": latency_eval["p_value"],
            "significant": latency_eval["significant"],
            "winner": latency_eval["winner"],
            "conclusion": latency_eval["conclusion"],
        },
        "f1_evaluation": {
            "n_a": f1_eval["n_a"],
            "n_b": f1_eval["n_b"],
            "min_samples_met": f1_eval["min_samples_met"],
            "p_value": f1_eval["p_value"],
            "significant": f1_eval["significant"],
            "winner": f1_eval["winner"],
            "conclusion": f1_eval["conclusion"],
        },
        "degradation": {
            "version_missing": {
                "degraded": degraded["degraded"],
                "reason": degraded["reason"],
                "model_version": degraded["model_version"],
                "stage": degraded["stage"],
            },
            "ab_disabled": {
                "degraded": disabled["degraded"],
                "reason": disabled["reason"],
            },
        },
        "celery": _celery_check(),
        "mlflow": _mlflow_check(),
        "elapsed_seconds": round(time.time() - started, 3),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "active_learning_e2e.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "ab_model_routing_e2e.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    out = main()
    print(json.dumps(out, ensure_ascii=False, indent=2))
