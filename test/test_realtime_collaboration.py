# -*- coding: utf-8 -*-
"""实时协作（步骤 6）单元测试。

覆盖：
- ConnectionManager 连接/广播/断开/在线用户
- AnnotationLockManager 内存降级（acquire/release/owner 及互斥语义）
- serialize_annotation 复用响应 schema
- 乐观锁（base_updated_at）冲突与成功
- _normalize_dt 纳秒/时区归一化
- broadcast_annotation_event 事件组装与广播
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.schemas.annotation import AnnotationCreate, AnnotationUpdate  # noqa: E402
from app.services.annotation_service import (  # noqa: E402
    AnnotationConflict,
    AnnotationService,
    _normalize_dt,
)
from app.services import realtime_service  # noqa: E402
from app.services.realtime_service import (  # noqa: E402
    AnnotationLockManager,
    ConnectionManager,
    broadcast_annotation_event,
    serialize_annotation,
)


class FakeWebSocket:
    """最小 WebSocket 替身，用于验证 ConnectionManager 的收发与清理。"""

    def __init__(self) -> None:
        self.sent = []
        self.accepted = False

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict) -> None:
        self.sent.append(message)


def _create_data(document_id="doc1"):
    return AnnotationCreate(
        document_id=document_id,
        annotation_type="entity",
        content={"text": "material"},
        confidence=0.9,
    )


def _fail_redis():
    """让 redis 客户端创建抛错，迫使 AnnotationLockManager 走内存降级。"""

    async def _raise(*_args, **_kwargs):
        raise RuntimeError("redis unavailable (forced for test)")

    return _raise


# ── ConnectionManager ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_connection_manager_connect_broadcast_disconnect(monkeypatch):
    mgr = ConnectionManager()
    ws_a, ws_b = FakeWebSocket(), FakeWebSocket()

    await mgr.connect("doc1", ws_a, "u1")
    await mgr.connect("doc1", ws_b, "u2")
    assert ws_a.accepted and ws_b.accepted
    assert mgr.online_users("doc1") == ["u1", "u2"]

    await mgr.broadcast("doc1", {"type": "annotation.created"})
    assert len(ws_a.sent) == 1
    assert ws_a.sent[0]["type"] == "annotation.created"
    assert len(ws_b.sent) == 1

    # 断开后不再收到广播，且在线列表正确收缩
    mgr.disconnect("doc1", ws_a)
    assert mgr.online_users("doc1") == ["u2"]
    await mgr.broadcast("doc1", {"type": "annotation.updated"})
    assert len(ws_a.sent) == 1  # 已断开的连接不再接收
    assert len(ws_b.sent) == 2


@pytest.mark.asyncio
async def test_connection_manager_broadcast_cleans_broken_socket():
    mgr = ConnectionManager()

    class BrokenWebSocket(FakeWebSocket):
        async def send_json(self, message: dict) -> None:
            raise OSError("connection lost")

    broken, ok = BrokenWebSocket(), FakeWebSocket()
    await mgr.connect("doc1", broken, "u1")
    await mgr.connect("doc1", ok, "u2")

    await mgr.broadcast("doc1", {"type": "x"})
    # 广播不抛异常，断开的连接被清理，健康连接仍收到消息
    assert ok.sent == [{"type": "x"}]
    assert mgr.online_users("doc1") == ["u2"]


# ── AnnotationLockManager（内存降级） ──────────────────────────────


@pytest.mark.asyncio
async def test_lock_manager_local_acquire_release_owner(monkeypatch):
    monkeypatch.setattr(realtime_service, "get_redis_client", _fail_redis())
    lm = AnnotationLockManager()

    assert await lm.acquire("ann1", "u1") is True
    assert await lm.owner("ann1") == "u1"

    # 其他用户抢锁失败，同一用户可重复持有
    assert await lm.acquire("ann1", "u2") is False
    assert await lm.acquire("ann1", "u1") is True

    # 非持有者无法释放
    await lm.release("ann1", "u2")
    assert await lm.owner("ann1") == "u1"

    # 持有者释放后为空
    await lm.release("ann1", "u1")
    assert await lm.owner("ann1") is None


@pytest.mark.asyncio
async def test_lock_manager_local_expiry(monkeypatch):
    monkeypatch.setattr(realtime_service, "get_redis_client", _fail_redis())
    lm = AnnotationLockManager()

    assert await lm.acquire("ann1", "u1", ttl=0) is True
    # ttl=0 立即过期，owner 读取时应已被剪枝为空
    assert await lm.owner("ann1") is None
    # 过期后可被其他用户再次获取
    assert await lm.acquire("ann1", "u2") is True
    assert await lm.owner("ann1") == "u2"


# ── serialize_annotation ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_serialize_annotation(db):
    svc = AnnotationService()
    ann = await svc.create_annotation(db, _create_data(), user_id="u1")
    payload = serialize_annotation(ann)
    assert payload["id"] == ann.id
    assert payload["document_id"] == "doc1"
    assert payload["status"] == "draft"
    assert payload["content"] == {"text": "material"}
    # 时间字段已序列化为 ISO 字符串
    assert isinstance(payload["created_at"], str)


# ── 乐观锁 ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_optimistic_lock_success_and_conflict(db):
    svc = AnnotationService()
    ann = await svc.create_annotation(db, _create_data(), user_id="u1")

    # 显式设定 updated_at，规避 SQLite CURRENT_TIMESTAMP 秒级精度导致同秒不变
    t0 = datetime(2026, 1, 1, 0, 0, 0)
    ann.updated_at = t0
    await db.flush()

    # 基数匹配 → 成功
    updated = await svc.update_annotation(
        db, ann.id, AnnotationUpdate(base_updated_at=t0, content={"v": 1}), "u1"
    )
    assert updated.content == {"v": 1}

    # 手动推进 updated_at，模拟他人已修改
    updated.updated_at = datetime(2026, 1, 1, 0, 0, 5)
    await db.flush()

    # 基数过期 → 冲突，不会覆盖
    with pytest.raises(AnnotationConflict) as exc:
        await svc.update_annotation(
            db, ann.id, AnnotationUpdate(base_updated_at=t0, content={"v": 2}), "u1"
        )
    assert exc.value.annotation_id == ann.id


@pytest.mark.asyncio
async def test_optimistic_lock_without_base_is_backward_compatible(db):
    svc = AnnotationService()
    ann = await svc.create_annotation(db, _create_data(), user_id="u1")
    # 不携带 base_updated_at → 不参与冲突检测（向后兼容）
    updated = await svc.update_annotation(db, ann.id, AnnotationUpdate(content={"v": 3}), "u1")
    assert updated.content == {"v": 3}


# ── _normalize_dt ──────────────────────────────────────────────────


def test_normalize_dt():
    aware = datetime(2026, 1, 1, 0, 0, 0, 500000, tzinfo=timezone.utc)
    assert _normalize_dt(aware) == datetime(2026, 1, 1, 0, 0, 0)
    assert _normalize_dt(aware).tzinfo is None
    assert _normalize_dt(datetime(2026, 1, 1, 12, 34, 56, 999999)) == datetime(2026, 1, 1, 12, 34, 56)
    assert _normalize_dt(None) is None


# ── broadcast_annotation_event ─────────────────────────────────────


@pytest.mark.asyncio
async def test_broadcast_annotation_event_assembles_message(monkeypatch, db):
    mgr = realtime_service.connection_manager
    # 清理单例状态，避免跨用例污染
    mgr._connections.clear()
    mgr._presence.clear()

    svc = AnnotationService()
    ann = await svc.create_annotation(db, _create_data(), user_id="u1")

    ws = FakeWebSocket()
    await mgr.connect("doc1", ws, "u2")

    await broadcast_annotation_event(
        "doc1",
        "annotation.created",
        annotation=ann,
        user_id="u1",
    )
    assert len(ws.sent) == 1
    msg = ws.sent[0]
    assert msg["type"] == "annotation.created"
    assert msg["user_id"] == "u1"
    assert msg["annotation"]["id"] == ann.id

    # 仅传 annotation_id（删除场景）
    await broadcast_annotation_event("doc1", "annotation.deleted", annotation_id=ann.id, user_id="u1")
    assert ws.sent[-1]["type"] == "annotation.deleted"
    assert ws.sent[-1]["annotation_id"] == ann.id
    assert "annotation" not in ws.sent[-1]