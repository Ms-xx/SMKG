"""
性能服务门面（插件化架构迁移：实现已迁至 `app/plugins/performance/service.py`）。

- 兼容再导出：既有 `from app.services.performance_service import performance_service`
  不受影响。
- 运行期消费者应经 `registry.get("performance")` 动态寻址。
"""

from __future__ import annotations

from app.plugins.performance.service import PerformanceService, performance_service

__all__ = ["PerformanceService", "performance_service"]
