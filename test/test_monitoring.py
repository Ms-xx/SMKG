# -*- coding: utf-8 -*-
"""
监控告警单元测试
覆盖：业务指标（模型推理延迟 / Celery 队列长度 exporter）、告警渠道格式化与签名、
以及告警 webhook 端点（无外部渠道配置时仅本地日志）。
"""
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi.testclient import TestClient  # noqa: E402

from app.api.v1.alerts import router as alerts_router  # noqa: E402
from app.services.alert_service import (  # noqa: E402
    build_webhook,
    format_dingtalk_markdown,
    format_wecom_markdown,
    sign_robot,
)
from app.utils import business_metrics  # noqa: E402


def _fake_alert(status="firing", name="BackendDown", summary="后端服务不可用"):
    return {
        "status": status,
        "labels": {"alertname": name, "severity": "critical"},
        "annotations": {"summary": summary},
        "startsAt": "2026-01-01T00:00:00Z",
    }


def _payload():
    return {"receiver": "backend-webhook", "status": "firing", "alerts": [_fake_alert()]}


# ── 业务指标 ──────────────────────────────────────────────
def test_observe_model_inference_renders_metric():
    business_metrics.observe_model_inference("ner", 0.123)
    text = business_metrics.render_business_metrics()
    assert "model_inference_duration_seconds" in text


def test_set_celery_queue_length_renders_metric():
    business_metrics.set_celery_queue_length("parsing", 42)
    text = business_metrics.render_business_metrics()
    assert "celery_queue_length" in text
    assert 'queue="parsing"' in text


def test_refresh_celery_queue_lengths_degrades_without_redis(monkeypatch):
    async def _boom():
        raise ConnectionError("redis down")

    monkeypatch.setattr("app.utils.redis_client.get_redis_client", _boom)

    async def _run():
        return await business_metrics.refresh_celery_queue_lengths()

    import asyncio

    lengths = asyncio.new_event_loop().run_until_complete(_run())
    assert lengths == {"celery": 0, "parsing": 0, "extraction": 0, "graph": 0}


# ── 告警渠道格式化 ────────────────────────────────────────
def test_format_dingtalk_markdown():
    body = format_dingtalk_markdown(_payload())
    assert body["msgtype"] == "markdown"
    assert "BackendDown" in body["markdown"]["text"]
    assert "后端服务不可用" in body["markdown"]["text"]


def test_format_wecom_markdown():
    body = format_wecom_markdown(_payload())
    assert body["msgtype"] == "markdown"
    assert "BackendDown" in body["markdown"]["content"]


def test_sign_robot_is_stable():
    ts1, sign1 = sign_robot("s3cret", timestamp="1700000000")
    ts2, sign2 = sign_robot("s3cret", timestamp="1700000000")
    assert ts1 == ts2 == "1700000000"
    assert sign1 == sign2
    assert "%3D" in sign1 or sign1.isalnum() or "%" in sign1


def test_build_webhook_dingtalk_with_secret():
    req = build_webhook("https://oapi.dingtalk.com/robot/send?access_token=t", _payload(), "s3cret")
    assert "timestamp=" in req["url"] and "sign=" in req["url"]
    assert req["json"]["msgtype"] == "markdown"


def test_build_webhook_wecom():
    req = build_webhook("https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=k", _payload())
    assert req["json"]["msgtype"] == "markdown"


def test_build_webhook_generic_passthrough():
    req = build_webhook("https://example.com/hook", _payload())
    assert req["json"] == _payload()


# ── 告警 webhook 端点 ─────────────────────────────────────
def test_alert_webhook_endpoint_no_forward():
    app = __import__("fastapi").FastAPI()
    app.include_router(alerts_router, prefix="/api/v1/alerts")
    client = TestClient(app)
    resp = client.post(
        "/api/v1/alerts/webhook",
        json=_payload() | {"groupLabels": {}, "version": "4", "truncatedAlerts": 0},
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "forwarded": False}