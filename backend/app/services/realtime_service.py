"""实时协作：WebSocket 连接管理、文档级广播、标注级互斥锁。

设计约定（本项目核心原则「可插拔、可降级」）：
- 连接与广播基于进程内存（单机部署）；多副本部署可替换为 Redis Pub/Sub 或消息队列。
- 标注锁优先走 Redis（SET NX + TTL），Redis 不可用时自动降级为进程内内存锁。
- 所有方法均为异步、幂等、不抛异常（网络/Redis 故障静默降级）。
"""

import time
from typing import Any, Optional

from fastapi import WebSocket

from app.utils.redis_client import get_redis_client

# 标注锁默认持有时长（秒），避免用户离开后锁永占
DEFAULT_LOCK_TTL = 120

# 告警/协作事件类型（与前端约定保持一致）
EVENT_ANNOTATION_CREATED = "annotation.created"
EVENT_ANNOTATION_UPDATED = "annotation.updated"
EVENT_ANNOTATION_DELETED = "annotation.deleted"
EVENT_ANNOTATION_SUBMITTED = "annotation.submitted"
EVENT_ANNOTATION_REVIEWED = "annotation.reviewed"
EVENT_ANNOTATION_LOCKED = "annotation.locked"
EVENT_ANNOTATION_UNLOCKED = "annotation.unlocked"
EVENT_PRESENCE_JOINED = "presence.joined"
EVENT_PRESENCE_LEFT = "presence.left"


def serialize_annotation(annotation: Any) -> dict:
    """把 Annotation ORM 对象序列化为可 JSON 广播的字典（复用响应 schema）。"""
    from app.schemas.annotation import AnnotationResponse

    return AnnotationResponse.model_validate(annotation).model_dump(mode="json")


class ConnectionManager:
    """进程内 WebSocket 连接注册表，按文档（document_id）划分频道。"""

    def __init__(self) -> None:
        # document_id -> {websocket: user_id}
        self._connections: dict[str, dict[WebSocket, str]] = {}
        # document_id -> set[user_id]（在线 Presence）
        self._presence: dict[str, set[str]] = {}

    async def connect(self, document_id: str, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        self._connections.setdefault(document_id, {})[websocket] = user_id
        self._presence.setdefault(document_id, set()).add(user_id)

    def disconnect(self, document_id: str, websocket: WebSocket) -> None:
        conns = self._connections.get(document_id)
        if conns is not None and websocket in conns:
            user_id = conns.pop(websocket)
            presence = self._presence.get(document_id)
            if presence is not None:
                presence.discard(user_id)
                if not presence:
                    self._presence.pop(document_id, None)
            if not conns:
                self._connections.pop(document_id, None)

    def online_users(self, document_id: str) -> list[str]:
        return sorted(self._presence.get(document_id, set()))

    async def broadcast(self, document_id: str, message: dict) -> None:
        """向某文档频道的所有连接广播消息；断开的连接就地清理，不抛异常。"""
        conns = list(self._connections.get(document_id, {}).items())
        for ws, _ in conns:
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(document_id, ws)


class AnnotationLockManager:
    """标注级互斥锁：Redis SET NX + TTL，故障时降级内存锁。"""

    def __init__(self) -> None:
        # annotation_id -> (user_id, expire_monotonic)
        self._local: dict[str, tuple[str, float]] = {}

    def _key(self, annotation_id: str) -> str:
        return f"annotation_lock:{annotation_id}"

    async def acquire(self, annotation_id: str, user_id: str, ttl: int = DEFAULT_LOCK_TTL) -> bool:
        """尝试加锁；成功或已被同一用户持有返回 True。"""
        try:
            rc = await get_redis_client()
            key = self._key(annotation_id)
            acquired = await rc.set(key, user_id, nx=True, ex=ttl)
            if acquired is True:
                return True
            owner = await rc.get(key)
            return owner == user_id
        except Exception:
            return self._acquire_local(annotation_id, user_id, ttl)

    async def release(self, annotation_id: str, user_id: str) -> None:
        """释放锁（仅锁持有者可释放）。"""
        try:
            rc = await get_redis_client()
            key = self._key(annotation_id)
            owner = await rc.get(key)
            if owner == user_id:
                await rc.delete(key)
        except Exception:
            self._release_local(annotation_id, user_id)

    async def owner(self, annotation_id: str) -> Optional[str]:
        """返回当前锁持有者 user_id；未锁定返回 None。"""
        try:
            rc = await get_redis_client()
            return await rc.get(self._key(annotation_id))
        except Exception:
            return self._owner_local(annotation_id)

    # ── 内存降级实现 ──────────────────────────────────────
    def _prune(self) -> None:
        now = time.monotonic()
        expired = [k for k, (_u, exp) in self._local.items() if exp <= now]
        for k in expired:
            self._local.pop(k, None)

    def _acquire_local(self, annotation_id: str, user_id: str, ttl: int) -> bool:
        self._prune()
        entry = self._local.get(annotation_id)
        if entry is None or entry[0] == user_id:
            self._local[annotation_id] = (user_id, time.monotonic() + ttl)
            return True
        return False

    def _release_local(self, annotation_id: str, user_id: str) -> None:
        entry = self._local.get(annotation_id)
        if entry is not None and entry[0] == user_id:
            self._local.pop(annotation_id, None)

    def _owner_local(self, annotation_id: str) -> Optional[str]:
        self._prune()
        entry = self._local.get(annotation_id)
        return entry[0] if entry else None


# 模块级单例（进程内共享）
connection_manager = ConnectionManager()
lock_manager = AnnotationLockManager()


async def broadcast_annotation_event(
    document_id: str,
    event_type: str,
    annotation: Any = None,
    annotation_id: Optional[str] = None,
    user_id: Optional[str] = None,
    extra: Optional[dict] = None,
) -> None:
    """组装并广播一次标注变更事件。"""
    message: dict[str, Any] = {
        "type": event_type,
        "document_id": document_id,
        "user_id": user_id,
    }
    if annotation is not None:
        message["annotation"] = serialize_annotation(annotation)
    if annotation_id is not None:
        message["annotation_id"] = annotation_id
    if extra:
        message.update(extra)
    await connection_manager.broadcast(document_id, message)
