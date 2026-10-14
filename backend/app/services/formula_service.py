# -*- coding: utf-8 -*-
"""
公式识别服务门面（插件化架构迁移：实现已迁至 `app/plugins/formula/service.py`）。
兼容再导出：既有 `from app.services.formula_service import FormulaRecognitionService` 不受影响。
"""

from __future__ import annotations

from app.plugins.formula.service import FormulaRecognitionService, formula_service

__all__ = ["FormulaRecognitionService", "formula_service"]
