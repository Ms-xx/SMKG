# -*- coding: utf-8 -*-
"""
业务指标（模型推理延迟 + Celery 队列长度），可插件化、可降级。

- 模型推理延迟：Histogram `model_inference_duration_seconds{model}`，
  由各 AI 服务经 `observe_model_inference` 记录。
- Celery 队列长度：Gauge `celery_queue_length{queue}`，从 Redis `LLEN` 读取，
  经 `/metrics/business` 端点在抓取时按需刷新（自定义 exporter 模式）。

两者都注册在独立 Registry，统一由 `/metrics/business` 暴露；Prometheus 以独立
job「backend-business」抓取。未安装 `prometheus_client` 或 Redis 不可达时优雅降级
（指标为空 / 队列长度记 0），服务照常运行。
"""
from __future__ import annotations

import logging
from typing import Mapping

logger = logging.getLogger(__name__)

try:
    import prometheus_client

    _HAS_METRICS = True
except Exception:  # pragma: no cover - 未安装监控依赖
    prometheus_client = None  # type: ignore[assignment]
    _HAS_METRICS = False

# Celery 任务队列（与 celery_app.py 的 task_routes 对应，外加默认队列）
CELERY_QUEUES = ("celery", "parsing", "extraction", "graph")

_REGISTRY = None
_MODEL_INFERENCE = None
_CELERY_QUEUE_LENGTH = None


def _get_registry():
    global _REGISTRY
    if _REGISTRY is None and _HAS_METRICS:
        _REGISTRY = prometheus_client.CollectorRegistry()
    return _REGISTRY


def get_model_inference_histogram():
    global _MODEL_INFERENCE
    if _MODEL_INFERENCE is None and _get_registry() is not None:
        _MODEL_INFERENCE = prometheus_client.Histogram(
            "model_inference_duration_seconds",
            "模型单次推理耗时（秒）",
            labelnames=["model"],
            buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0),
            registry=_get_registry(),
        )
    return _MODEL_INFERENCE


def get_celery_queue_gauge():
    global _CELERY_QUEUE_LENGTH
    if _CELERY_QUEUE_LENGTH is None and _get_registry() is not None:
        _CELERY_QUEUE_LENGTH = prometheus_client.Gauge(
            "celery_queue_length",
            "Celery 队列待处理任务数",
            labelnames=["queue"],
            registry=_get_registry(),
        )
    return _CELERY_QUEUE_LENGTH


def observe_model_inference(model: str, seconds: float) -> None:
    """记录一次模型推理耗时；依赖缺失时 no-op。"""
    histogram = get_model_inference_histogram()
    if histogram is not None:
        histogram.labels(model=model).observe(max(0.0, seconds))


def set_celery_queue_length(queue: str, length: int) -> None:
    """写入指定队列长度；依赖缺失时 no-op。"""
    gauge = get_celery_queue_gauge()
    if gauge is not None:
        gauge.labels(queue=queue).set(max(0, int(length)))


async def refresh_celery_queue_lengths() -> Mapping[str, int]:
    """从 Redis 读取各队列长度并写入 gauge；Redis 不可达时记 0。"""
    lengths: dict[str, int] = dict.fromkeys(CELERY_QUEUES, 0)
    try:
        from app.utils.redis_client import get_redis_client

        client = await get_redis_client()
        for queue in CELERY_QUEUES:
            try:
                lengths[queue] = int(await client.llen(queue))
            except Exception:  # pragma: no cover - 单队列读取失败
                lengths[queue] = 0
    except Exception:  # pragma: no cover - Redis 整体不可用
        logger.warning("Redis 不可达，Celery 队列长度记 0")
    for queue, length in lengths.items():
        set_celery_queue_length(queue, length)
    return lengths


def render_business_metrics() -> str:
    """导出业务指标的 Prometheus 文本格式；未安装依赖时返回空串。"""
    if not _HAS_METRICS or _get_registry() is None:
        return ""
    return prometheus_client.generate_latest(_get_registry()).decode("utf-8")


def setup_business_metrics(app) -> None:
    """在根部挂载 `/metrics/business` 端点；依赖缺失时跳过。"""
    if not _HAS_METRICS:
        logger.warning("prometheus_client 未安装，跳过 /metrics/business")
        return

    from fastapi.responses import Response

    @app.get("/metrics/business", include_in_schema=False)
    async def business_metrics():
        await refresh_celery_queue_lengths()
        return Response(
            content=render_business_metrics(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    logger.info("业务指标已暴露于 /metrics/business")
