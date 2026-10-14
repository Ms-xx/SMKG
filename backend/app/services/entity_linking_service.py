# -*- coding: utf-8 -*-
"""
entity_linking_service 门面（插件化架构迁移：实现已迁至 `app/plugins/entity_linking/service.py`）。
兼容再导出：既有 `from app.services.<源> import ...` 不受影响。
"""

from __future__ import annotations

from app.plugins.entity_linking.service import (
    DBPEDIA_LOOKUP_URL,
    WIKIDATA_SEARCH_URL,
    EntityLinkingService,
    entity_linking_service,
    jaccard_similarity,
    levenshtein_ratio,
    normalize_text,
    string_similarity,
)

__all__ = [
    "DBPEDIA_LOOKUP_URL",
    "EntityLinkingService",
    "WIKIDATA_SEARCH_URL",
    "entity_linking_service",
    "jaccard_similarity",
    "levenshtein_ratio",
    "normalize_text",
    "string_similarity",
]
