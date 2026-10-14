# -*- coding: utf-8 -*-
"""
writing_assistant_service 门面（插件化架构迁移：实现已迁至 `app/plugins/writing_assistant/service.py`）。
兼容再导出：既有 `from app.services.<源> import ...` 不受影响。
"""

from __future__ import annotations

from app.plugins.writing_assistant.service import (
    WritingAssistantService,
    csv_to_chart,
    figure_caption,
    generate_diagram_script,
    generate_outline,
    llm_generate,
    logger,
    parse_csv,
    translate_text,
    writing_assistant_service,
)

__all__ = [
    "WritingAssistantService",
    "csv_to_chart",
    "figure_caption",
    "generate_diagram_script",
    "generate_outline",
    "llm_generate",
    "logger",
    "parse_csv",
    "translate_text",
    "writing_assistant_service",
]
