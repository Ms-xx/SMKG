"""
文档服务门面（插件化架构迁移：实现已迁至 `app/plugins/document/service.py`）。

- 兼容再导出：既有 `from app.services.document_service import DocumentService`
  不受影响。
- 运行期消费者应经 `registry.get("document")` 动态寻址。
"""

from __future__ import annotations

from app.plugins.document.service import DocumentService

__all__ = ["DocumentService"]
