import asyncio
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import DOCUMENT_WRITE, has_permission
from app.core.security import get_current_user
from app.services.document_service import DocumentService
from app.services.source_anchor_service import source_anchor_service

router = APIRouter()
doc_service = DocumentService()


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


async def _backfill_anchors(
    db: AsyncSession, current_user: dict, anchors: list[dict[str, Any]]
) -> dict[str, Any]:
    """编排：按涉及的 document_id 去重拉取页级全文（pages_lookup），再回填 page_number。

    get_fulltext 在文档不存在/无权限时会抛 HTTPException，捕获后跳过该文档。
    """
    doc_ids = {str(a["document_id"]) for a in anchors if a.get("document_id")}
    pages_lookup: dict[str, list] = {}
    user_id = (
        current_user.get("user_id")
        if isinstance(current_user, dict)
        else getattr(current_user, "user_id", None)
    )
    scope_all = (
        has_permission(current_user, DOCUMENT_WRITE) if isinstance(current_user, dict) else False
    )
    for doc_id in doc_ids:
        try:
            fulltext = await doc_service.get_fulltext(db, doc_id, user_id, scope_all)
            pages = fulltext.get("pages") or []
        except Exception:  # noqa: BLE001 - 文档缺失/无权限等均跳过该文档
            pages = []
        pages_lookup[doc_id] = pages

    result = source_anchor_service.backfill(anchors, pages_lookup)
    backfilled = int(result.get("backfilled_count") or 0)
    return {
        "anchors": result.get("anchors", anchors),
        "page_backfill": {
            "backfilled_count": backfilled,
            "note": (
                "已按 DocumentPage 文本完成 chunk→page 映射回填"
                if backfilled > 0
                else "无可用页文本，锚点保持原始页码仅 chunk 级"
            ),
        },
    }


@router.post("/anchors")
async def anchors(
    body: AnchorsRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """溯源锚点：从带来源元数据的分块生成可跳转出处列表，并按页级全文回填 page_number。"""
    chunks = [c.model_dump() for c in body.chunks]
    resp = source_anchor_service.anchors(chunks)
    backfilled = await _backfill_anchors(db, current_user, resp.get("anchors") or [])
    resp.update(backfilled)
    return resp


@router.post("/rag-anchors")
async def rag_anchors(
    body: RagAnchorsRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """真实溯源：从 GraphRAGTest(8001) 拉取带来源 chunks 生成出处锚点，并按页级全文回填 page_number。

    `source_anchor_service.rag_anchors` 内部调用同步 `graphrag_integration.rag_query`
    （红线步骤 4：保持同步方法语义不变），用 `asyncio.to_thread` 包裹以避免阻塞事件循环。
    """
    resp = await asyncio.to_thread(source_anchor_service.rag_anchors, body.question)
    backfilled = await _backfill_anchors(db, current_user, resp.get("anchors") or [])
    resp.update(backfilled)
    return resp


@router.post("/compare")
async def compare(body: CompareRequest, current_user: dict = Depends(get_current_user)):
    """多文对比：跨文档聚合候选分块并输出对比结论（配置 LLM 时用真实 LLM 生成）。"""
    docs = [d.model_dump() for d in body.documents]
    return await asyncio.to_thread(
        source_anchor_service.compare,
        docs,
        body.question,
        body.use_llm if body.use_llm is not None else True,
    )
