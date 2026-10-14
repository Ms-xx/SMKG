"""
标注服务门面（插件化架构迁移：实现已迁至 `app/plugins/annotation/service.py`）。

- 兼容再导出：既有 `from app.services.annotation_service import AnnotationService`
  等不受影响。
- 运行期消费者应经 `registry.get("annotation")` 动态寻址。
"""

from __future__ import annotations

from app.plugins.annotation.service import AnnotationConflict, AnnotationService, _normalize_dt

__all__ = ["AnnotationService", "AnnotationConflict", "_normalize_dt"]
