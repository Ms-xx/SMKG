# -*- coding: utf-8 -*-
"""
source_anchor_service 门面（插件化架构迁移：实现已迁至 `app/plugins/source_anchor/service.py`）。
兼容再导出：既有 `from app.services.<源> import ...` 不受影响。
"""

from __future__ import annotations

from app.plugins.source_anchor.service import (
    SourceAnchorService,
    _llm_chat_completion,
    anchors_from_rag,
    backfill_page_numbers,
    extract_anchors,
    multi_document_compare,
    source_anchor_service,
)

__all__ = [
    "SourceAnchorService",
    "_llm_chat_completion",
    "anchors_from_rag",
    "backfill_page_numbers",
    "extract_anchors",
    "multi_document_compare",
    "source_anchor_service",
]
