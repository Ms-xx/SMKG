# -*- coding: utf-8 -*-
"""
text_to_cypher_service 门面（插件化架构迁移：实现已迁至 `app/plugins/text_to_cypher/service.py`）。
兼容再导出：既有 `from app.services.<源> import ...` 不受影响。
"""

from __future__ import annotations

from app.plugins.text_to_cypher.service import (
    TextToCypherService,
    text_to_cypher_service,
)

__all__ = [
    "TextToCypherService",
    "text_to_cypher_service",
]
