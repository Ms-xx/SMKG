"""实时协作 WebSocket 通道（标注文档粒度）。

鉴权：浏览器原生 WebSocket 无法携带 Authorization 头，故通过查询参数
`?token=<access_token>` 传递 JWT，连接建立时解码并做 `annotation:read` 权限校验。
"""

import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import (
    ADMIN_ROLE,
    ANNOTATION_READ,
    get_role_permissions,
    has_permission,
)
from app.core.security import decode_token
from app.services.realtime_service import (
    EVENT_PRESENCE_JOINED,
    EVENT_PRESENCE_LEFT,
    connection_manager,
)

logger = logging.getLogger(__name__)

router = APIRouter()


async def _authenticate(websocket: WebSocket) -> dict:
    """解码 token 并返回 {user_id, role}；失败时关闭连接返回 None。"""
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        return None
    try:
        payload = decode_token(token)
    except Exception:
        await websocket.close(code=4401)
        return None
    if payload.get("type") != "access" or not payload.get("sub"):
        await websocket.close(code=4401)
        return None
    return {"user_id": payload["sub"], "role": payload.get("role")}


@router.websocket("/annotations/{document_id}")
async def annotation_collaboration(
    websocket: WebSocket,
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    user = await _authenticate(websocket)
    if user is None:
        return

    # 权限校验：admin 或拥有 annotation:read / all
    if user["role"] != ADMIN_ROLE:
        permissions = await get_role_permissions(db, user["role"])
        if not has_permission({"role": user["role"], "permissions": permissions}, ANNOTATION_READ):
            await websocket.close(code=4403)
            return

    user_id = user["user_id"]
    await connection_manager.connect(document_id, websocket, user_id)

    # 订阅确认 + 在线用户快照
    await websocket.send_json(
        {
            "type": "subscribed",
            "document_id": document_id,
            "online_users": connection_manager.online_users(document_id),
        }
    )
    await connection_manager.broadcast(
        document_id,
        {"type": EVENT_PRESENCE_JOINED, "document_id": document_id, "user_id": user_id},
    )

    try:
        while True:
            # 客户端心跳/上行消息：当前仅接收不处理（协作主流程走 REST + 服务端广播）
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as e:  # pragma: no cover - 异常断开清理
        logger.debug(f"WebSocket 异常断开: {e}")
    finally:
        connection_manager.disconnect(document_id, websocket)
        await connection_manager.broadcast(
            document_id,
            {"type": EVENT_PRESENCE_LEFT, "document_id": document_id, "user_id": user_id},
        )
