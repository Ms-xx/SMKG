# -*- coding: utf-8 -*-
"""
graph_snapshot 门面（插件化架构迁移：实现已迁至 `app/plugins/graph_snapshot/service.py`）。
兼容再导出：既有 `from app.services.<源> import ...` 不受影响。
"""

from __future__ import annotations

from app.plugins.graph_snapshot.service import (
    GraphSnapshot,
    is_empty_snapshot,
    normalize_export_payload,
    snapshot_cache_key,
)

__all__ = [
    "GraphSnapshot",
    "is_empty_snapshot",
    "normalize_export_payload",
    "snapshot_cache_key",
]
