"""
A/B 测试服务门面（插件化架构迁移：实现已迁至 `app/plugins/ab_test/service.py`）。

- 兼容再导出：既有 `from app.services.ab_test_service import ABTestService,
  proportion_z_test, ...` 不受影响。
- 运行期消费者应经 `registry.get("ab_test")` 动态寻址。
"""

from __future__ import annotations

from app.plugins.ab_test.service import (
    METRIC_BINARY,
    METRIC_CONTINUOUS,
    METRIC_LATENCY,
    METRIC_QUALITY,
    ABTestService,
    _ibeta,
    _normal_cdf,
    _t_cdf,
    ab_test_service,
    make_variant,
    parse_variant,
    proportion_z_test,
    welch_ttest,
)

__all__ = [
    "ABTestService",
    "ab_test_service",
    "METRIC_BINARY",
    "METRIC_CONTINUOUS",
    "METRIC_LATENCY",
    "METRIC_QUALITY",
    "make_variant",
    "parse_variant",
    "proportion_z_test",
    "welch_ttest",
    "_normal_cdf",
    "_ibeta",
    "_t_cdf",
]
