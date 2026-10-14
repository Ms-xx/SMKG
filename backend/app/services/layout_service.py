# -*- coding: utf-8 -*-
"""
版面分析服务门面（插件化架构迁移：实现已迁至 `app/plugins/layout/service.py`）。
兼容再导出：既有 `from app.services.layout_service import LayoutAnalysisService` 不受影响。
"""

from __future__ import annotations

from app.plugins.layout.service import (
    DEFAULT_LABEL_MAP,
    ELEMENT_TYPE_ZH,
    LayoutAnalysisService,
    detect_header_footer,
    group_blocks,
    is_page_number,
    layout_service,
    map_label,
    map_token_labels_to_words,
    normalize_boxes,
)

__all__ = [
    "LayoutAnalysisService",
    "DEFAULT_LABEL_MAP",
    "ELEMENT_TYPE_ZH",
    "detect_header_footer",
    "group_blocks",
    "is_page_number",
    "layout_service",
    "map_label",
    "map_token_labels_to_words",
    "normalize_boxes",
]
