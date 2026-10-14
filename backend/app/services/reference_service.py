# -*- coding: utf-8 -*-
"""
reference_service 门面（插件化架构迁移：实现已迁至 `app/plugins/reference/service.py`）。
兼容再导出：既有 `from app.services.<源> import ...` 不受影响。
"""

from __future__ import annotations

from app.plugins.reference.service import (
    ReferenceExtractionService,
    _is_section_header,
    enhance_references_with_grobid,
    grobid_available,
    reference_service,
    references_to_bibtex,
    references_to_csl_json,
    references_to_jats,
)

__all__ = [
    "ReferenceExtractionService",
    "_is_section_header",
    "enhance_references_with_grobid",
    "grobid_available",
    "reference_service",
    "references_to_bibtex",
    "references_to_csl_json",
    "references_to_jats",
]
