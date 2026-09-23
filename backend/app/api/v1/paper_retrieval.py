from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import DOCUMENT_WRITE, require_permission
from app.core.security import get_current_user
from app.services.document_service import DocumentService
from app.services.paper_retrieval_service import paper_retrieval_service

router = APIRouter()
doc_service = DocumentService()


class SearchRequest(BaseModel):
    query: str = ""
    source: str = Field("arxiv", description="arxiv | pubmed")
    max_results: Optional[int] = Field(None, ge=1, le=50)


class RecommendRequest(BaseModel):
    local_references: list[dict] = []
    candidates: list[dict] = []


class DownloadRequest(BaseModel):
    result: dict = Field(..., description="单条检索结果（含 source / arxiv_id / pubmed_id）")


class TrackingRequest(BaseModel):
    query: str = ""
    source: str = Field("arxiv", description="arxiv | pubmed")
    interval_days: int = Field(7, ge=1, le=365)


@router.post("/search")
async def search(body: SearchRequest, current_user: dict = Depends(get_current_user)):
    """论文检索：调用 arXiv/PubMed 公开 API（网络失败降级返回空 + error）。"""
    return paper_retrieval_service.search(body.query, body.source, body.max_results)


@router.post("/recommend")
async def recommend(body: RecommendRequest, current_user: dict = Depends(get_current_user)):
    """论文推荐：本地文献库 vs 候选论文相关性打分。"""
    return paper_retrieval_service.recommend(body.local_references, body.candidates)


@router.post("/download")
async def download_pdf(body: DownloadRequest, current_user: dict = Depends(get_current_user)):
    """下载检索结果 PDF：返回下载元数据（文件大小/地址），网络失败降级不报错。"""
    return paper_retrieval_service.download_pdf(body.result)


@router.post("/tracking")
async def register_tracking(body: TrackingRequest, current_user: dict = Depends(get_current_user)):
    """注册领域论文定时追踪（内存态）。"""
    return paper_retrieval_service.register_tracking(body.query, body.source, body.interval_days)


@router.post("/download-and-ingest")
async def download_and_ingest(
    body: DownloadRequest,
    current_user: dict = Depends(require_permission(DOCUMENT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    """论文下载入库闭环：下载 PDF → 上传 MinIO → 创建文档 → 触发解析。

    对应 XiangMu 步骤 8.3。网络/存储失败时降级返回 downloaded=False，不抛异常。
    """
    meta, data = paper_retrieval_service.download_bytes(body.result)
    if not data:
        return {"ingested": False, "download": meta}

    filename = meta["filename"]
    title = body.result.get("title") or filename
    document = await doc_service.create_document_from_bytes(
        db, filename, data, "application/pdf", title, current_user["user_id"]
    )
    parsing = await doc_service.trigger_parsing(
        db, document.id, current_user["user_id"], scope_all=True
    )
    return {
        "ingested": True,
        "document_id": document.id,
        "download": meta,
        "parsing": parsing,
    }


@router.get("/tracking")
async def list_tracking(current_user: dict = Depends(get_current_user)):
    """列出当前进程内的论文追踪注册表。"""
    return paper_retrieval_service.list_tracking()
