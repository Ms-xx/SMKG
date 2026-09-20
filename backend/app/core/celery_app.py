import platform

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "worker", broker=settings.CELERY_BROKER_URL, backend=settings.CELERY_RESULT_BACKEND
)

# Windows 上使用 solo 池模式以避免兼容性问题
if platform.system() == "Windows":
    celery_app.conf.update(worker_pool="solo")

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_extended=True,
    result_expires=3600,
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    task_soft_time_limit=3000,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_ignore_result=False,
    task_send_sent_event=True,
    worker_send_task_events=True,
    task_routes={
        "app.workers.parsing_tasks.*": {"queue": "parsing"},
        "app.workers.extraction_tasks.*": {"queue": "extraction"},
        "app.workers.graph_tasks.*": {"queue": "graph"},
    },
    # 错误处理配置
    task_throws=(),
    task_reject_on_worker_lost=True,
    worker_disable_rate_limits=True,
)

# Import task modules to register them with the worker
from app.workers import (  # noqa: E402
    extraction_tasks,  # noqa: F401
    graph_tasks,  # noqa: F401
    parsing_tasks,  # noqa: F401
)
