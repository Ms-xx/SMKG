"""
统计服务门面（插件化架构迁移：实现已迁至 `app/plugins/statistics/service.py`）。

- 兼容再导出：既有 `from app.services.statistics_service import StatisticsService`
  不受影响。
- 运行期消费者应经 `registry.get("statistics")` 动态寻址。
"""

from __future__ import annotations

from app.plugins.statistics.service import StatisticsService

__all__ = ["StatisticsService"]
