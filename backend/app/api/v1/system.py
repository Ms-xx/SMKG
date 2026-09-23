# -*- coding: utf-8 -*-
"""系统运维 API（步骤 11）：性能基线探测。"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.services.performance_service import performance_service

router = APIRouter()


@router.get("/performance")
async def performance_check(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """探测 MySQL / Redis / Neo4j 的延迟基线（可降级，单后端不可达不影响整体返回）。"""
    if not performance_service.available:
        return {"error": "性能探测已禁用（PERFORMANCE_CHECK_ENABLED=False）"}
    return await performance_service.check(db)
