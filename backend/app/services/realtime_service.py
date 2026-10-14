"""
实时协作服务门面（插件化架构迁移：实现已迁至 `app/plugins/realtime/service.py`）。

- 兼容再导出：既有 `from app.services.realtime_service import ...` 不受影响。
- 运行期消费者应经 `registry.get("realtime")` 动态寻址。
"""

from __future__ import annotations

from app.plugins.realtime.service import (
    DEFAULT_LOCK_TTL,
    EVENT_ANNOTATION_CREATED,
    EVENT_ANNOTATION_DELETED,
    EVENT_ANNOTATION_LOCKED,
    EVENT_ANNOTATION_REVIEWED,
    EVENT_ANNOTATION_SUBMITTED,
    EVENT_ANNOTATION_UNLOCKED,
    EVENT_ANNOTATION_UPDATED,
    EVENT_PRESENCE_JOINED,
    EVENT_PRESENCE_LEFT,
    AnnotationLockManager,
    ConnectionManager,
    broadcast_annotation_event,
    connection_manager,
    lock_manager,
    serialize_annotation,
)
from app.utils.redis_client import get_redis_client

__all__ = [
    "DEFAULT_LOCK_TTL",
    "EVENT_ANNOTATION_CREATED",
    "EVENT_ANNOTATION_UPDATED",
    "EVENT_ANNOTATION_DELETED",
    "EVENT_ANNOTATION_SUBMITTED",
    "EVENT_ANNOTATION_REVIEWED",
    "EVENT_ANNOTATION_LOCKED",
    "EVENT_ANNOTATION_UNLOCKED",
    "EVENT_PRESENCE_JOINED",
    "EVENT_PRESENCE_LEFT",
    "serialize_annotation",
    "ConnectionManager",
    "AnnotationLockManager",
    "connection_manager",
    "lock_manager",
    "broadcast_annotation_event",
    "get_redis_client",
]
