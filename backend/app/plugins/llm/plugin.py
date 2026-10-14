# -*- coding: utf-8 -*-
"""官方插件：llm —— 通用 LLM 对话 provider（OpenAI 兼容端点）。

- 独立配置空间：`LLM_` 前缀（LLM_ENABLED / LLM_ENDPOINT / LLM_MODEL / LLM_TIMEOUT ...）。
- 无状态、轻量 → 支持运行期热替换（/system/plugins/llm/reload）。
- 运行时消费者经 `registry.get("llm")` 动态寻址，不持具体类。
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.core.plugin.base import Plugin

logger = logging.getLogger(__name__)


class LLMSettings(BaseModel):
    enabled: bool = True
    endpoint: str = "http://127.0.0.1:1234/v1"
    model: str = "qwen/qwen3-4b-2507"
    timeout: float = Field(default=60.0)
    temperature: float = 0.7
    max_tokens: int = 4096


class LLMService:
    """LLM 对话实现（同步构造、异步调用）。health() 供 /system/plugins/{name}/health。"""

    def __init__(self, cfg: LLMSettings) -> None:
        self.cfg = cfg

    async def on_start(self) -> None:
        logger.info("llm plugin started (endpoint=%s model=%s)", self.cfg.endpoint, self.cfg.model)

    async def on_stop(self) -> None:
        logger.info("llm plugin stopped")

    def health(self) -> dict[str, Any]:
        return {
            "enabled": self.cfg.enabled,
            "endpoint": self.cfg.endpoint,
            "model": self.cfg.model,
        }

    async def chat(self, messages: list[dict], *, temperature: float | None = None) -> str:
        """调用 OpenAI 兼容 /chat/completions。端点不可用或未启用时降级为占位文本。"""
        if not self.cfg.enabled:
            return "[llm: 未启用]"
        payload = {
            "model": self.cfg.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.cfg.temperature,
            "max_tokens": self.cfg.max_tokens,
        }
        try:
            async with httpx.AsyncClient(timeout=self.cfg.timeout) as client:
                r = await client.post(
                    f"{self.cfg.endpoint.rstrip('/')}/chat/completions", json=payload
                )
                r.raise_for_status()
                data = r.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:  # 端到端降级，不阻断业务
            logger.warning("llm chat failed, fallback: %s", e)
            return f"[llm: 端点不可用，降级占位] error={e}"


class LLMPlugin(Plugin):
    name = "llm"
    version = "1.0.0"
    config_prefix = "LLM_"
    requires: list[str] = []
    type = "service"
    settings_cls = LLMSettings

    def create(self, registry, settings) -> LLMService:
        cfg: LLMSettings = settings or LLMSettings()
        return LLMService(cfg)


plugin = LLMPlugin()
