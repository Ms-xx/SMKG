# -*- coding: utf-8 -*-
"""
REBEL 关系抽取服务门面（插件化架构迁移：实现已迁至 `app/plugins/rebel/service.py`）。

- 兼容再导出：既有 `from app.services.rebel_service import RebelService / rebel_service`
  不受影响。
- 重型模型服务：运行期仅冷替换/重启；消费者经 `registry.get("rebel")` 动态寻址。
"""

from __future__ import annotations

from app.plugins.rebel.service import (
    RebelService,
    normalize_relation_type,
    parse_rebel_output,
    rebel_service,
)

__all__ = ["RebelService", "rebel_service", "parse_rebel_output", "normalize_relation_type"]
