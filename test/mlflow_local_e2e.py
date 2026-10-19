# -*- coding: utf-8 -*-
"""步骤 14.3 验证：MLflow 本地 tracking server 接入端到端验证。

覆盖验证项：
1. 本地 tracking server 可达（GET /health）；
2. 后端 version_management 服务按配置把全部 MLflow 追踪请求指向本地 server
   （mlflow_status().effective_backend == "dvc_mlflow"）；
3. 记录一次实验（params/metrics/tags）→ 返回 mlflow_run_id；
4. 经 MLflow 客户端回读该 run，参数/指标与写入一致；
5. 记录一次工件（artifact）→ 落盘到独立存储目录 <MLFLOW_STORE_DIR>/artifacts；
6. 后端存储（SQLite）落盘到 <MLFLOW_STORE_DIR>/backend/mlflow.db；
7. 经 MLflow 客户端与 UI 端点可检索到该实验。

仅本机可运行（需先执行 deploy/mlflow/start_mlflow_server.ps1 启动 server）。
结果写入 outputs/mlflow_local_e2e.json。

用法：
    python test/mlflow_local_e2e.py
"""
import json
import os
import sys
import tempfile
import urllib.request
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

OUT_DIR = os.path.join(ROOT, "outputs")

# 追踪地址/存储目录/实验名（无硬编码：允许环境变量覆盖，缺省按仓库位置推导）
TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI") or "http://127.0.0.1:5000"
STORE_DIR = os.environ.get("MLFLOW_STORE_DIR") or os.path.join(ROOT, "mlflow")
EXPERIMENT = os.environ.get("MLFLOW_EXPERIMENT_NAME") or "sdp-version-management"
ARTIFACT_DIR = os.path.join(STORE_DIR, "artifacts")
BACKEND_DB = os.path.join(STORE_DIR, "backend", "mlflow.db")

# 显式启用 MLflow 外部后端并统一指向本地 server（环境变量优先级高于 config/*.env）
os.environ["MLFLOW_TRACKING_URI"] = TRACKING_URI
os.environ["MLFLOW_STORE_DIR"] = STORE_DIR
os.environ["MLFLOW_EXPERIMENT_NAME"] = EXPERIMENT
os.environ["MLFLOW_ENABLED"] = "true"
os.environ["VERSION_MGMT_BACKEND"] = "dvc_mlflow"


def _get(url: str, timeout: float = 5.0) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read()


def main() -> int:
    checks: dict = {}
    detail: dict = {
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tracking_uri": TRACKING_URI,
    }

    # 1. server 可达（/health 返回纯文本，非 JSON）
    with urllib.request.urlopen(
        TRACKING_URI.rstrip("/") + "/health", timeout=5.0
    ) as resp:
        health_text = resp.read().decode("utf-8", errors="ignore")
        checks["server_reachable"] = resp.status == 200 and len(health_text) > 0
    detail["server_health"] = health_text

    # 2. 经后端服务：全部 MLflow 追踪请求统一走本地 server
    from app.services.version_management_service import version_management_service

    status = version_management_service.mlflow_status(refresh=True)
    detail["mlflow_status"] = status
    checks["effective_backend_is_mlflow"] = status["effective_backend"] == "dvc_mlflow"

    # 3. 记录一次实验（务必返回 mlflow_run_id，证明写入了真实 MLflow）
    exp = version_management_service.log_experiment(
        name="step14.3-e2e",
        params={"model": "scibert-ner", "lr": 0.0002, "epochs": 3},
        metrics={"f1": 0.9123, "precision": 0.9, "recall": 0.88},
        tags={"source": "step14.3-verification", "deploy_mode": "local"},
    )
    run_id = exp.get("mlflow_run_id")
    detail["experiment_record"] = exp
    checks["mlflow_run_id_returned"] = bool(run_id)

    # 4. 客户端回读：参数/指标一致
    import mlflow

    mlflow.set_tracking_uri(TRACKING_URI)
    client = mlflow.MlflowClient()
    fetched = client.get_run(run_id)
    detail["fetched_run"] = {
        "run_id": fetched.info.run_id,
        "experiment_id": fetched.info.experiment_id,
        "params": dict(fetched.data.params),
        "metrics": dict(fetched.data.metrics),
        "tags": dict(fetched.data.tags),
    }
    checks["params_and_metrics_match"] = (
        fetched.data.params.get("model") == "scibert-ner"
        and abs(fetched.data.metrics.get("f1", 0.0) - 0.9123) < 1e-9
    )

    # 5. 工件落盘到独立存储目录
    with tempfile.TemporaryDirectory() as td:
        artifact_path = os.path.join(td, "summary.txt")
        with open(artifact_path, "w", encoding="utf-8") as fh:
            fh.write("step14.3 mlflow artifact e2e\n")
        client.log_artifact(run_id, artifact_path)
    artifact_files = [
        os.path.join(dirpath, f)
        for dirpath, _, files in os.walk(ARTIFACT_DIR)
        for f in files
    ]
    detail["artifact_dir"] = ARTIFACT_DIR
    detail["artifact_files"] = artifact_files
    checks["artifact_written"] = len(artifact_files) > 0

    # 6. 后端存储（SQLite）落盘
    checks["backend_db_exists"] = os.path.isfile(BACKEND_DB)
    checks["backend_db_size_bytes"] = (
        os.path.getsize(BACKEND_DB) if os.path.isfile(BACKEND_DB) else 0
    )

    # 7. 经 MLflow 客户端 + UI 端点可检索
    names = [e.name for e in client.search_experiments()]
    detail["experiment_names"] = names
    checks["experiment_visible_via_client"] = EXPERIMENT in names
    ui_html = _get(TRACKING_URI.rstrip("/") + "/").decode("utf-8", errors="ignore")
    checks["ui_endpoint_ok"] = "<!doctype html" in ui_html.lower() or len(ui_html) > 0

    expected = [
        "server_reachable",
        "effective_backend_is_mlflow",
        "mlflow_run_id_returned",
        "params_and_metrics_match",
        "artifact_written",
        "backend_db_exists",
        "experiment_visible_via_client",
        "ui_endpoint_ok",
    ]
    detail["checks"] = checks
    detail["ok"] = (
        all(bool(checks.get(k)) for k in expected)
        and checks.get("backend_db_size_bytes", 0) > 0
    )

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "mlflow_local_e2e.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(detail, fh, ensure_ascii=False, indent=2)

    print(json.dumps(detail, ensure_ascii=False, indent=2))
    print(f"\n结果已写入 {out_path}")
    return 0 if detail["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
