"""
信息抽取服务门面（插件化架构迁移：实现已迁至 `app/plugins/extraction/service.py`）。

- 兼容再导出：既有 `from app.services.extraction_service import ExtractionService`
  不受影响。
- 运行期消费者应经 `registry.get("extraction")` 动态寻址。
"""

from __future__ import annotations

from app.plugins.extraction.service import ExtractionService, extraction_service

__all__ = ["ExtractionService", "extraction_service"]
