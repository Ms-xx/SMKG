# -*- coding: utf-8 -*-
"""数据/模型版本管理服务单元测试：数据版本 / 实验追踪 / 模型注册 / 自动重训。均纯内存、零依赖。"""
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.version_management_service import (
    VersionManagementService,
    dataset_hash,
    data_quality,
    evaluate_retrain_trigger,
    compare_metrics,
)


def test_dataset_hash_deterministic():
    assert dataset_hash([{"a": 1}, {"b": 2}]) == dataset_hash([{"a": 1}, {"b": 2}])


def test_dataset_hash_order_insensitive():
    assert dataset_hash({"x": 1, "y": 2}) == dataset_hash({"y": 2, "x": 1})


def test_dataset_hash_differs():
    assert dataset_hash([1, 2, 3]) != dataset_hash([1, 2, 4])


def test_data_quality_distribution():
    out = data_quality([{"label": "A"}, {"label": "A"}, {"label": "B"}, {"label": None}])
    assert out["n_records"] == 4
    assert out["n_labeled"] == 3
    assert out["n_missing"] == 1
    assert out["n_categories"] == 2
    assert out["distribution"]["A"] == 2
    assert out["distribution"]["B"] == 1


def test_evaluate_retrain_trigger_manual():
    assert evaluate_retrain_trigger(force=True) == {"trigger": True, "reasons": ["manual"]}


def test_evaluate_retrain_trigger_threshold():
    out = evaluate_retrain_trigger(new_annotated=150, last_train_count=50, threshold=100)
    assert out["trigger"] is True and "threshold" in out["reasons"]


def test_evaluate_retrain_trigger_periodic():
    out = evaluate_retrain_trigger(last_train_age_days=10, periodic_days=7)
    assert out["trigger"] is True and "periodic" in out["reasons"]


def test_evaluate_retrain_trigger_none():
    assert evaluate_retrain_trigger(new_annotated=10, last_train_count=0, threshold=100) == {"trigger": False, "reasons": []}


def test_compare_metrics_best():
    exps = [
        {"id": "e1", "metrics": {"f1": 0.8, "acc": 0.9}},
        {"id": "e2", "metrics": {"f1": 0.9, "acc": 0.85}},
    ]
    out = compare_metrics(exps)
    assert out["best"]["f1"] == "e2"
    assert out["best"]["acc"] == "e1"


def test_record_dataset_versions_increment():
    svc = VersionManagementService()
    svc.record_dataset("ds", data=[{"label": "A"}])
    svc.record_dataset("ds", data=[{"label": "B"}])
    assert [v["version"] for v in svc.list_datasets()["ds"]] == [1, 2]


def test_log_and_list_experiments():
    svc = VersionManagementService()
    svc.log_experiment("exp", params={"lr": 0.01}, metrics={"f1": 0.8})
    svc.log_experiment("other", metrics={"f1": 0.9})
    assert len(svc.list_experiments()) == 2
    assert len(svc.list_experiments(name="exp")) == 1


def test_compare_experiments_via_service():
    svc = VersionManagementService()
    svc.log_experiment("exp", metrics={"f1": 0.7})
    svc.log_experiment("exp", metrics={"f1": 0.9})
    out = svc.compare_experiments()
    assert out["n_experiments"] == 2
    assert list(out["best"].values())[0] == "exp-0002"


def test_register_model_and_stage_transition():
    svc = VersionManagementService()
    svc.register_model("ner", metrics={"f1": 0.8})
    svc.register_model("ner", metrics={"f1": 0.9})
    # v1 → production
    r = svc.transition_stage("ner", 1, "production")
    assert r["ok"] is True
    # v2 → production：归档 v1
    r2 = svc.transition_stage("ner", 2, "production")
    assert r2["ok"] is True and r2["archived_previous"] == 1
    models = svc.list_models()["ner"]
    stages = {m["version"]: m["stage"] for m in models}
    assert stages[1] == "archived" and stages[2] == "production"


def test_transition_stage_invalid():
    svc = VersionManagementService()
    svc.register_model("m")
    r = svc.transition_stage("m", 1, "production")
    r = svc.transition_stage("m", 1, "staging")  # production → staging 非法
    assert r["ok"] is False


def test_check_retrain_via_service():
    svc = VersionManagementService()
    out = svc.check_retrain(new_annotated=150, last_train_count=0, force=False)
    assert out["trigger"] is True and "threshold" in out["reasons"]


def test_run_pipeline_completes():
    svc = VersionManagementService()
    run = svc.run_pipeline("ner", trigger_reason="manual")
    assert run["status"] == "completed"
    assert [s["step"] for s in run["steps"]] == ["data_prep", "training", "evaluation", "registration", "deployment"]
    assert svc.pipeline_status(run["id"])["status"] == "completed"