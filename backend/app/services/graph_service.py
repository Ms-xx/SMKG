"""
图谱服务门面（插件化架构迁移：实现已迁至 `app/plugins/graph/service.py`）。

- 兼容再导出：既有 `from app.services.graph_service import GraphService` 不受影响。
- 运行期消费者应经 `registry.get("graph")` 动态寻址。
"""

from __future__ import annotations

from app.plugins.graph.service import GraphService

__all__ = ["GraphService"]
