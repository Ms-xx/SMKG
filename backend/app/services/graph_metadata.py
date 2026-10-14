# -*- coding: utf-8 -*-
"""
graph_metadata 门面（插件化架构迁移：实现已迁至 `app/plugins/graph_metadata/service.py`）。
兼容再导出：既有 `from app.services.<源> import ...` 不受影响。
"""

from __future__ import annotations

from app.plugins.graph_metadata.service import (
    extract_authors,
    extract_venue,
    extract_year,
)

__all__ = [
    "extract_authors",
    "extract_venue",
    "extract_year",
]
