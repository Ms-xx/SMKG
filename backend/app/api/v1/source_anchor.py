from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import get_current_user
from app.services.source_anchor_service import source_anchor_service

router = APIRouter()


class AnchorChunk(BaseModel):
    document_id: Optional[str] = None
    page_number: Optional[int] = None
    snippet: Optional[str] = None
    score: Optional[float] = None


class AnchorsRequest(BaseModel):
    chunks: list[AnchorChunk] = []


class CompareDoc(BaseModel):
    document_id: Optional[str] = None
    title: Optional[str] = None
    chunks: list[str] = []


class CompareRequest(BaseModel):
    question: str = ""
    documents: list[CompareDoc] = []
    use_llm: Optional[bool] = True


class RagAnchorsRequest(BaseModel):
    question: str = ""


@router.post("/anchors")
async def anchors(body: AnchorsRequest, current_user: dict = Depends(get_current_user)):
    """溯源锚点：从带来源元数据的分块生成可跳转出处列表。"""
    chunks = [c.model_dump() for c in body.chunks]
    return source_anchor_service.anchors(chunks)


@router.post("/rag-anchors")
async def rag_anchors(body: RagAnchorsRequest, current_user: dict = Depends(get_current_user)):
    """真实溯源：从 GraphRAGTest(8001) 拉取带来源的 chunks 生成出处锚点（backend=rag）。"""
    return source_anchor_service.rag_anchors(body.question)


@router.post("/compare")
async def compare(body: CompareRequest, current_user: dict = Depends(get_current_user)):
    """多文对比：跨文档聚合候选分块并输出对比结论（配置 LLM 时用真实 LLM 生成）。"""
    docs = [d.model_dump() for d in body.documents]
    return source_anchor_service.compare(
        docs, body.question, use_llm=body.use_llm if body.use_llm is not None else True
    )
