# -*- coding: utf-8 -*-
"""
graphrag_integration 门面（插件化架构迁移：实现已迁至 `app/plugins/graphrag_integration/service.py`）。
兼容再导出：既有 `from app.services.<源> import ...` 不受影响。
"""

from __future__ import annotations

from app.plugins.graphrag_integration.service import (
    GRAPHRAG_BASE_URL,
    GraphRAGIntegration,
    _close_async_client,
    graphrag_integration,
)

__all__ = [
    "GRAPHRAG_BASE_URL",
    "GraphRAGIntegration",
    "_close_async_client",
    "graphrag_integration",
]
