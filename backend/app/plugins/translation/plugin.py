# -*- coding: utf-8 -*-
"""官方插件：translation —— 双语（中英）翻译 provider。

- 独立配置空间：`TRANSLATION_` 前缀。
- 依赖可选的 llm 插件不在必选 requires 中，避免 chained 强依赖：translate 自含端点。
- 无状态轻量 → 支持运行期热替换。
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.core.plugin.base import Plugin

logger = logging.getLogger(__name__)


class TranslationSettings(BaseModel):
    enabled: bool = True
    endpoint: str = "http://127.0.0.1:1234/v1"
    model: str = "qwen/qwen3-4b-2507"
    timeout: float = Field(default=60.0)


class TranslationService:
    def __init__(self, cfg: TranslationSettings) -> None:
        self.cfg = cfg

    async def on_start(self) -> None:
        logger.info("translation plugin started (endpoint=%s)", self.cfg.endpoint)

    async def on_stop(self) -> None:
        logger.info("translation plugin stopped")

    def health(self) -> dict[str, Any]:
        return {"enabled": self.cfg.enabled, "endpoint": self.cfg.endpoint}

    async def translate(self, text: str, source: str = "auto", target: str = "zh") -> str:
        """通过 OpenAI 兼容端点做指令式翻译，端点不可用/未启用时降级占位。"""
        if not self.cfg.enabled:
            return f"[translation: 未启用原文] {text}"
        prompt = (
            f"Translate the following from {source} to {target}. "
            "Keep terminology and formatting unchanged. Output only the translation.\n\n"
            f"{text}"
        )
        payload = {
            "model": self.cfg.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max(64, int(len(text) * 2.5)) if text else 64,
        }
        try:
            async with httpx.AsyncClient(timeout=self.cfg.timeout) as client:
                r = await client.post(
                    f"{self.cfg.endpoint.rstrip('/')}/chat/completions", json=payload
                )
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:  # 端到端降级，不阻断业务
            logger.warning("translation failed, fallback: %s", e)
            return f"[translation: 端点不可用，降级原文] {text}"


class TranslationPlugin(Plugin):
    name = "translation"
    version = "1.0.0"
    config_prefix = "TRANSLATION_"
    requires: list[str] = []
    type = "service"
    settings_cls = TranslationSettings

    def create(self, registry, settings) -> TranslationService:
        cfg: TranslationSettings = settings or TranslationSettings()
        return TranslationService(cfg)


plugin = TranslationPlugin()
