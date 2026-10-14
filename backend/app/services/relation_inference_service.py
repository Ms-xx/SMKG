# -*- coding: utf-8 -*-
"""
relation_inference_service 门面（插件化架构迁移：实现已迁至 `app/plugins/relation_inference/service.py`）。
兼容再导出：既有 `from app.services.<源> import ...` 不受影响。
"""

from __future__ import annotations

from app.plugins.relation_inference.service import (
    _NUMPY_AVAILABLE,
    GNNLinkPredictor,
    RelationInferenceService,
    RotatELinkPredictor,
    StatisticalLinkPredictor,
    TransELinkPredictor,
    infer_triples,
    relation_inference_service,
)

__all__ = [
    "GNNLinkPredictor",
    "RelationInferenceService",
    "RotatELinkPredictor",
    "StatisticalLinkPredictor",
    "TransELinkPredictor",
    "_NUMPY_AVAILABLE",
    "infer_triples",
    "relation_inference_service",
]
