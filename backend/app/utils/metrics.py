# -*- coding: utf-8 -*-
"""Prometheus 指标暴露（可插拔，缺失依赖时优雅降级）。

- 依赖 `prometheus-fastapi-instrumentator`（内置 prometheus_client）。
- 未安装时 `setup_metrics` 为 no-op，服务照常启动，仅不暴露 `/metrics`。
- 默认指标：请求计数、请求耗时（histogram）、在途请求数，以及
  prometheus_client 自带的进程/GC 等运行时指标。
"""
import logging

logger = logging.getLogger(__name__)

try:
    from prometheus_fastapi_instrumentator import Instrumentator

    _INSTRUMENTATOR = Instrumentator()
    _HAS_METRICS = True
except Exception:  # pragma: no cover - 环境未安装监控依赖
    _INSTRUMENTATOR = None
    _HAS_METRICS = False


def setup_metrics(app) -> None:
    """注册指标中间件并暴露 `/metrics` 端点；依赖缺失时跳过。"""
    if _INSTRUMENTATOR is None:
        logger.warning(
            "prometheus-fastapi-instrumentator 未安装，跳过 /metrics 暴露（监控能力降级）"
        )
        return
    _INSTRUMENTATOR.instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
    logger.info("Prometheus 指标已暴露于 /metrics")
