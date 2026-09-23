from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.services.deduplication_service import deduplication_service

router = APIRouter()


class DocumentItem(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    abstract: Optional[str] = None
    text: Optional[str] = None


class DedupDetectRequest(BaseModel):
    documents: list[DocumentItem] = []
    threshold: Optional[float] = Field(None, ge=0.0, le=1.0)


class AffiliationRequest(BaseModel):
    text: str = ""


@router.post("/detect")
async def detect(body: DedupDetectRequest, current_user: dict = Depends(get_current_user)):
    """语义去重：对文档集合做 SimHash 相似分组，输出保留最新版本建议。"""
    docs = [d.model_dump() for d in body.documents]
    return deduplication_service.detect(docs, threshold=body.threshold)


@router.post("/affiliations")
async def affiliations(body: AffiliationRequest, current_user: dict = Depends(get_current_user)):
    """作者机构抽取：从文本中启发式抽取机构名/邮箱域名。"""
    return deduplication_service.affiliations(body.text)
