from fastapi import APIRouter

from app.api.v1 import (
    active_learning,
    alerts,
    annotations,
    auth,
    calibration_drift,
    comments,
    documents,
    knowledge_graph,
    notifications,
    operation_logs,
    permissions,
    statistics,
    tasks,
    users,
    version_management,
    ws,
)
from app.api.v1 import models as model_api

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["Auth"])
router.include_router(users.router, prefix="/users", tags=["Users"])
router.include_router(documents.router, prefix="/documents", tags=["Documents"])
router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
router.include_router(annotations.router, prefix="/annotations", tags=["Annotations"])
router.include_router(operation_logs.router, prefix="/operation-logs", tags=["操作日志"])
router.include_router(statistics.router, prefix="/statistics", tags=["工作量统计"])
router.include_router(comments.router, prefix="/comments", tags=["评论讨论"])
router.include_router(notifications.router, prefix="/notifications", tags=["通知"])
router.include_router(permissions.router, prefix="/permissions", tags=["权限管理"])
router.include_router(knowledge_graph.router, prefix="/knowledge-graph", tags=["Knowledge Graph"])
router.include_router(active_learning.router, prefix="/active-learning", tags=["主动学习"])
router.include_router(version_management.router, prefix="/version-management", tags=["版本管理"])
router.include_router(
    calibration_drift.router, prefix="/calibration-drift", tags=["校准与漂移检测"]
)
router.include_router(model_api.router, prefix="/models", tags=["Models"])
router.include_router(alerts.router, prefix="/alerts", tags=["告警"])
router.include_router(ws.router, prefix="/ws", tags=["实时协作"])
