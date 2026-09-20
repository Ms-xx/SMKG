# -*- coding: utf-8 -*-
"""
告警渠道格式化与签名（钉钉 / 企业微信 / 通用 webhook），纯 Python 可测试、无网络副作用。

告警转发链路：Alertmanager → 后端 `/api/v1/alerts/webhook` → 记录结构化日志
（进入 Filebeat→Logstash→ES→Kibana 检索），并按配置转发到外部即时通讯机器人。

- 钉钉机器人：URL 含 `oapi.dingtalk.com`，消息体为 markdown，支持加签（URL 拼接 timestamp/sign）。
- 企业微信机器人：URL 含 `qyapi.weixin.qq.com`，消息体为 markdown。
- 通用 webhook：透传 Alertmanager 原始 payload。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time
import urllib.parse
from typing import Any


def _alerts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return payload.get("alerts") or []


def _markdown_lines(payload: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for alert in _alerts(payload):
        status = (alert.get("status") or "unknown").upper()
        labels = alert.get("labels", {}) or {}
        annotations = alert.get("annotations", {}) or {}
        name = labels.get("alertname", "")
        summary = annotations.get("summary") or annotations.get("description") or name or "告警"
        lines.append(f"- **[{status}] {name}** {summary}")
    return lines or ["告警（无详情）"]


def format_dingtalk_markdown(payload: dict[str, Any]) -> dict[str, Any]:
    """把 Alertmanager payload 转成钉钉 markdown 消息。"""
    return {
        "msgtype": "markdown",
        "markdown": {
            "title": "监控告警",
            "text": "\n".join(_markdown_lines(payload)),
        },
    }


def format_wecom_markdown(payload: dict[str, Any]) -> dict[str, Any]:
    """把 Alertmanager payload 转成企业微信 markdown 消息。"""
    return {
        "msgtype": "markdown",
        "markdown": {"content": "\n".join(_markdown_lines(payload))},
    }


def sign_robot(secret: str, timestamp: str | None = None) -> tuple[str, str]:
    """计算钉钉/企业微信机器人加签（HMAC-SHA256 → base64 → urlencode）。"""
    ts = timestamp or str(int(time.time()))
    string_to_sign = f"{ts}\n{secret}"
    digest = hmac.new(
        secret.encode("utf-8"), string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(digest).decode("utf-8"))
    return ts, sign


def build_webhook(
    post_url: str, payload: dict[str, Any], secret: str | None = None
) -> dict[str, Any]:
    """
    根据 URL 判断渠道，构造转发请求。

    Returns:
        {"url", "json", "headers"}，其中 url 已含加签参数（若配置 secret）。
    """
    headers = {"Content-Type": "application/json"}
    url = post_url
    if "oapi.dingtalk.com" in post_url:
        body = format_dingtalk_markdown(payload)
        if secret:
            ts, sign = sign_robot(secret)
            sep = "&" if "?" in post_url else "?"
            url = f"{post_url}{sep}timestamp={ts}&sign={sign}"
    elif "qyapi.weixin.qq.com" in post_url:
        body = format_wecom_markdown(payload)
    else:
        body = payload  # 通用 webhook，透传原 payload
    return {"url": url, "json": body, "headers": headers}
