# -*- coding: utf-8 -*-
"""第三方示例插件：sample_stats —— 统计词频的纯服务插件。

演示如何**不改核心/不重启**就把第三方插件接入系统：
1. 放置到 `third_party_plugins/<name>/plugin.py`
2. 重启一次（或后端已运行则 core 读取到 `PLUGIN_EXTRA_DIR`）
3. `POST /api/v1/system/plugins/rescan` → `POST /api/v1/system/plugins/sample_stats/load`

更进一步的"已加载实例热替换/卸载"经 `/system/plugins/{name}/reload|unload` 完成。
本插件无外部依赖、自包含，可随时删除。
"""
from __future__ import annotations

import logging
import re
import unicodedata
from collections import Counter
from typing import Any

from app.core.plugin.base import Plugin

logger = logging.getLogger(__name__)


class SampleStatsSettings:
    def __init__(self, enabled: bool = True, top_k: int = 10) -> None:
        if isinstance(enabled, str):
            enabled = enabled.strip().lower() in ("true", "1")
        self.enabled = enabled
        self.top_k = int(top_k if top_k else 10)


class SampleStatsService:
    def __init__(self, cfg: SampleStatsSettings) -> None:
        self.cfg = cfg

    async def on_start(self) -> None:
        logger.info("sample_stats plugin started")

    async def on_stop(self) -> None:
        logger.info("sample_stats plugin stopped")

    def health(self) -> dict[str, Any]:
        return {"enabled": self.cfg.enabled, "top_k": self.cfg.top_k}

    def top_words(self, text: str) -> dict[str, Any]:
        tokens = re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", text or ""), flags=re.UNICODE)
        counter: Counter[str] = Counter(t.lower() for t in tokens)
        return {
            "top_k": self.cfg.top_k,
            "total_tokens": len(tokens),
            "unique_tokens": len(counter),
            "top": counter.most_common(self.cfg.top_k),
        }


class SampleStatsPlugin(Plugin):
    name = "sample_stats"
    version = "1.0.0"
    config_prefix = ""
    type = "service"
    settings_cls = SampleStatsSettings

    def create(self, registry, settings) -> SampleStatsService:
        return SampleStatsService(settings or SampleStatsSettings())


plugin = SampleStatsPlugin()