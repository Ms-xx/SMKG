# -*- coding: utf-8 -*-
"""
graph_snapshot_service 门面（插件化架构迁移：实现已迁至 `app/plugins/graph_snapshot_service/service.py`）。
兼容再导出：既有 `from app.services.<源> import ...` 不受影响。
"""

from __future__ import annotations

from app.plugins.graph_snapshot_service.service import (
    get_full_graph_snapshot,
    invalidate_graph_snapshot,
)

__all__ = [
    "get_full_graph_snapshot",
    "invalidate_graph_snapshot",
]
