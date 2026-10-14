# -*- coding: utf-8 -*-
"""
跨文献结构化演进对比服务门面（插件化架构迁移：实现已迁至 `app/plugins/multi_paper_compare/service.py`）。

- 兼容再导出：既有 `from app.services.multi_paper_compare_service import MultiPaperCompareService /
  DEFAULT_DIMENSIONS / build_compare_matrix / enhance_insights` 不受影响。
- 测试经本门面对模块级辅助函数 `_llm_chat_completion` 打补丁，插件实现 `enhance_insights`
  运行期经 `_core()` 动态寻址门面读取补丁，保证打补丁生效。
"""

from __future__ import annotations

from app.plugins.multi_paper_compare.service import (
    DEFAULT_DIMENSIONS,
    MultiPaperCompareService,
    _llm_chat_completion,
    build_compare_matrix,
    enhance_insights,
    multi_paper_compare_service,
)

__all__ = [
    "MultiPaperCompareService",
    "multi_paper_compare_service",
    "DEFAULT_DIMENSIONS",
    "build_compare_matrix",
    "enhance_insights",
    "_llm_chat_completion",
]
