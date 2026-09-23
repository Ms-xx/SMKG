from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import get_current_user
from app.services.citation_graph_service import citation_graph_service

router = APIRouter()


class NetworkRequest(BaseModel):
    references: list[dict] = []


class KeyPapersRequest(BaseModel):
    graph: dict = {}


class SurveyRequest(BaseModel):
    references: list[dict] = []
    top_papers: Optional[list[dict]] = None


@router.post("/network")
async def network(body: NetworkRequest, current_user: dict = Depends(get_current_user)):
    """引用网络建图：参考文献 → 节点 + CITES/TOPIC 边。"""
    return citation_graph_service.network(body.references)


@router.post("/key-papers")
async def key_papers(body: KeyPapersRequest, current_user: dict = Depends(get_current_user)):
    """基石节点挖掘：PageRank + 介数中心性。"""
    return citation_graph_service.key_papers(body.graph)


@router.post("/survey")
async def survey(body: SurveyRequest, current_user: dict = Depends(get_current_user)):
    """自动综述 + Future Work 去重：规则模板（LLM 预留）。"""
    return citation_graph_service.survey(body.references, body.top_papers)
