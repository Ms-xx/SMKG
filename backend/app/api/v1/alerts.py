# -*- coding: utf-8 -*-
"""告警接收端点（Alertmanager webhook）。

Alertmanager 将告警 POST 到 `/api/v1/alerts/webhook`，这里：
1) 以结构化 JSON 记录每条告警（进入 Filebeat→Logstash→ES→Kibana 日志链路）；
2) 若配置了 `ALERT_WEBHOOK_URL`（钉钉/企业微信/通用），异步转发到外部渠道。
"""
import json
import logging
from typing import Any

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.alert_service import build_webhook

logger = logging.getLogger(__name__)

router = APIRouter()


class AlertWebhookBody(BaseModel):
    receiver: str = Field("", description="接收器名称")
    status: str = Field("", description="overall 状态：firing | resolved")
    alerts: list[dict[str, Any]] = Field(default_factory=list, description="告警列表")

    model_config = {"extra": "ignore"}  # 容忍 Alertmanager 的 groupLabels/commonLabels 等附加字段


def _log_alert(alert: dict[str, Any]) -> None:
    """以结构化 JSON 记录单条告警（便于 Kibana 检索）。"""
    labels = alert.get("labels", {}) or {}
    annotations = alert.get("annotations", {}) or {}
    logger.warning(
        json.dumps(
            {
                "event": "alert",
                "status": alert.get("status"),
                "alertname": labels.get("alertname"),
                "severity": labels.get("severity"),
                "summary": annotations.get("summary"),
                "description": annotations.get("description"),
                "startsAt": alert.get("startsAt"),
                "endsAt": alert.get("endsAt"),
            },
            ensure_ascii=False,
        )
    )


@router.post("/webhook")
async def alert_webhook(body: AlertWebhookBody):
    """接收 Alertmanager 告警并（可选）转发外部渠道。"""
    payload = {
        "receiver": body.receiver,
        "status": body.status,
        "alerts": body.alerts,
    }
    for alert in body.alerts:
        _log_alert(alert)

    if not settings.ALERT_WEBHOOK_URL:
        return {"status": "ok", "forwarded": False}

    request = build_webhook(settings.ALERT_WEBHOOK_URL, payload, settings.ALERT_WEBHOOK_SECRET)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                request["url"], json=request["json"], headers=request["headers"]
            )
            resp.raise_for_status()
        return {"status": "ok", "forwarded": True}
    except Exception as e:  # pragma: no cover - 渠道不可达不阻断告警记录
        logger.error("告警转发失败：%s", e)
        return {"status": "ok", "forwarded": False, "error": str(e)}
