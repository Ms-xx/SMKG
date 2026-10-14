# -*- coding: utf-8 -*-
"""
multi_agent_service 门面（插件化架构迁移：实现已迁至 `app/plugins/multi_agent/service.py`）。
兼容再导出：既有 `from app.services.<源> import ...` 不受影响。
"""

from __future__ import annotations

from app.plugins.multi_agent.service import (
    AGENT_EXTRACT,
    AGENT_PARSE,
    AGENT_QA,
    AGENT_REGISTRY,
    AGENT_SUMMARIZE,
    RESOLUTION_MODES,
    MultiAgentService,
    _build_relations_from_cooccurrence,
    _entities_to_graph_format,
    _extract_fallback,
    multi_agent_service,
    resolve_conflicts,
    set_llm_backend,
)

__all__ = [
    "AGENT_EXTRACT",
    "AGENT_PARSE",
    "AGENT_QA",
    "AGENT_REGISTRY",
    "AGENT_SUMMARIZE",
    "MultiAgentService",
    "RESOLUTION_MODES",
    "_build_relations_from_cooccurrence",
    "_entities_to_graph_format",
    "_extract_fallback",
    "multi_agent_service",
    "resolve_conflicts",
    "set_llm_backend",
]
