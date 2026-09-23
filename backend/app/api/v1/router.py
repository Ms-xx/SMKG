from fastapi import APIRouter

from app.api.v1 import (
    ab_test,
    active_learning,
    alerts,
    annotations,
    auth,
    calibration_drift,
    citation_graph,
    citation_link,
    comments,
    deduplication,
    documents,
    knowledge_graph,
    multi_agent,
    notifications,
    operation_logs,
    paper_retrieval,
    permissions,
    source_anchor,
    statistics,
    system,
    tasks,
    users,
    version_management,
    writing_assistant,
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
router.include_router(ab_test.router, prefix="/ab-test", tags=["A/B 测试"])
router.include_router(multi_agent.router, prefix="/multi-agent", tags=["多 Agent 协作"])
router.include_router(system.router, prefix="/system", tags=["系统运维"])
router.include_router(
    calibration_drift.router, prefix="/calibration-drift", tags=["校准与漂移检测"]
)
router.include_router(model_api.router, prefix="/models", tags=["Models"])
router.include_router(alerts.router, prefix="/alerts", tags=["告警"])
router.include_router(ws.router, prefix="/ws", tags=["实时协作"])
router.include_router(deduplication.router, prefix="/deduplication", tags=["语义去重"])
router.include_router(source_anchor.router, prefix="/source-anchor", tags=["溯源与多文对比"])
router.include_router(citation_link.router, prefix="/citation-link", tags=["版式联动阅读"])
router.include_router(paper_retrieval.router, prefix="/paper-retrieval", tags=["论文检索推荐"])
router.include_router(citation_graph.router, prefix="/citation-graph", tags=["引用图谱"])
router.include_router(writing_assistant.router, prefix="/writing-assistant", tags=["写作辅助"])
