from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import DOCUMENT_READ, require_permission
from app.core.security import get_current_user
from app.models.document import Document
from app.services.citation_graph_service import citation_graph_service
from app.services.document_service import DocumentService
from app.services.future_work_service import future_work_service

router = APIRouter()
doc_service = DocumentService()


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
async def key_papers(
    body: KeyPapersRequest, current_user: dict = Depends(get_current_user)
):
    """基石节点挖掘：PageRank + 介数中心性。"""
    return citation_graph_service.key_papers(body.graph)


@router.post("/survey")
async def survey(body: SurveyRequest, current_user: dict = Depends(get_current_user)):
    """自动综述 + Future Work 去重：规则模板（LLM 预留）。"""
    return citation_graph_service.survey(body.references, body.top_papers)


@router.get("/future-work")
async def future_work(
    domain: Optional[str] = Query(None, description="按标题/摘要/关键词领域过滤"),
    min_year: Optional[int] = Query(None, description="时间窗起始年份"),
    max_year: Optional[int] = Query(None, description="时间窗结束年份"),
    current_user: dict = Depends(require_permission(DOCUMENT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Future Work 前沿探索（步骤 22）：提取 Future Work，排除已被后续论文解决的旧 idea。

    支持按领域/时间窗过滤；无 year / 无 CITES 边的数据上降级并标注低置信度。
    判定均带原文 snippet 与 document_id 溯源。
    """
    result = await db.execute(select(Document))
    docs = result.scalars().all()
    records: list[dict] = []
    for d in docs:
        if domain:
            hay = " ".join(
                [d.title or "", d.abstract or "", " ".join(d.keywords or [])]
            ).lower()
            if domain.lower() not in hay:
                continue
        year = d.publication_date.year if d.publication_date else None
        if year is not None:
            if min_year is not None and year < min_year:
                continue
            if max_year is not None and year > max_year:
                continue
        # 加载每篇正文（页级文本），供后文信号判定
        try:
            fulltext = await doc_service.get_fulltext(db, d.id, None, True)
            pages = [p.get("text") or "" for p in (fulltext.get("pages") or [])]
        except Exception:  # noqa: BLE001
            pages = []
        records.append(
            {
                "document_id": d.id,
                "title": d.title,
                "year": year,
                "authors": d.authors or [],
                "references": d.references or [],
                "pages": pages,
            }
        )
    scan = future_work_service.scan(records)
    scan["filtered"] = {
        "domain": domain,
        "min_year": min_year,
        "max_year": max_year,
        "applied_document_count": len(records),
    }
    return scan
