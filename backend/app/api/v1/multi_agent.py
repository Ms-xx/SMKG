# -*- coding: utf-8 -*-
"""多 Agent 协作 API（步骤 9）：智能体列表 / 任务编排 / 冲突解决 / 会话查询。"""
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.services.multi_agent_service import (
    multi_agent_service,
    resolve_conflicts,
)

router = APIRouter()


class RunRequest(BaseModel):
    query: str = Field(..., description="用户任务/问题")
    context: Optional[str] = Field(None, description="上下文文本（文献段落等），缺省用 query")
    agents: Optional[list[str]] = Field(None, description="参与智能体列表，缺省全部")
    mode: str = Field("merge", description="冲突解决模式：vote | merge | arbitrate")


class ProposalItem(BaseModel):
    agent: str = Field(..., description="产出该结果的智能体标识")
    content: Optional[str] = Field(None, description="文本类答案")
    items: Optional[list[dict[str, Any]]] = Field(None, description="列表类（实体）产出")
    confidence: float = Field(0.5, description="置信度")


class ResolveRequest(BaseModel):
    proposals: list[ProposalItem] = Field(..., description="多个 Agent 的产出")
    mode: str = Field("merge", description="冲突解决模式：vote | merge | arbitrate")


@router.get("/agents")
async def list_agents(current_user: dict = Depends(get_current_user)):
    """列出可用的专用智能体。"""
    return {"agents": multi_agent_service.list_agents(), "modes": ["vote", "merge", "arbitrate"]}


@router.post("/run")
async def run(body: RunRequest, current_user: dict = Depends(get_current_user)):
    """协调器编排：分派任务给多智能体并做冲突解决（返回最终结论 + 冲突明细）。"""
    if not multi_agent_service.available:
        return {"error": "多 Agent 协作已禁用（MULTI_AGENT_ENABLED=False）"}
    return multi_agent_service.run(
        query=body.query,
        context=body.context or "",
        agents=body.agents,
        mode=body.mode,
    )


@router.post("/resolve")
async def resolve(body: ResolveRequest, current_user: dict = Depends(get_current_user)):
    """独立冲突解决：对给定多智能体产出做投票/合并/仲裁。"""
    proposals = [p.model_dump() for p in body.proposals]
    return resolve_conflicts(proposals, body.mode)


@router.get("/sessions")
async def list_sessions(current_user: dict = Depends(get_current_user)):
    """列出历史编排会话。"""
    return {"items": multi_agent_service.list_sessions()}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """查询单个编排会话。"""
    return multi_agent_service.get_session(session_id)
