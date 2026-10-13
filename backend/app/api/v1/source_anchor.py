import asyncio
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import (
    DOCUMENT_READ,
    DOCUMENT_WRITE,
    has_permission,
    require_permission,
)
from app.core.security import get_current_user
from app.services.document_service import DocumentService
from app.services.multi_paper_compare_service import multi_paper_compare_service
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
        has_permission(current_user, DOCUMENT_WRITE)
        if isinstance(current_user, dict)
        else False
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


class CompareMatrixDoc(BaseModel):
    document_id: Optional[str] = None
    title: Optional[str] = None
    pages: list[str] = []
    param_count: Optional[str] = None
    context_window: Optional[str] = None
    model_type: Optional[str] = None


class CompareMatrixRequest(BaseModel):
    documents: list[CompareMatrixDoc] = []
    dimensions: list[str] = []


async def _load_matrix_docs(
    db: AsyncSession, current_user: dict, docs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """编排：缺省 pages 时按 document_id 从数据库加载页级全文，并推断页码锚点。"""
    user_id = (
        current_user.get("user_id")
        if isinstance(current_user, dict)
        else getattr(current_user, "user_id", None)
    )
    scope_all = (
        has_permission(current_user, DOCUMENT_WRITE)
        if isinstance(current_user, dict)
        else False
    )
    out: list[dict[str, Any]] = []
    for d in docs:
        doc_id = d.get("document_id")
        pages = list(d.get("pages") or [])
        page_pairs: list[dict[str, Any]] = []
        if pages and not isinstance(pages[0], int):
            # 纯文本页列表 → 按页序编号（页码从 1 起）
            page_pairs = [
                {"page_number": i + 1, "text": str(p)} for i, p in enumerate(pages)
            ]
        elif pages:
            page_pairs = [{"page_number": int(p), "text": ""} for p in pages]
        if not page_pairs and doc_id:
            try:
                fulltext = await doc_service.get_fulltext(
                    db, doc_id, user_id, scope_all
                )
                page_pairs = [
                    {
                        "page_number": int(p["page_number"]),
                        "text": str(p.get("text") or ""),
                    }
                    for p in (fulltext.get("pages") or [])
                ]
            except Exception:  # noqa: BLE001 - 文档缺失/无权限等，保留空页
                page_pairs = []
        out.append(
            {
                "document_id": doc_id,
                "title": d.get("title"),
                "param_count": d.get("param_count"),
                "context_window": d.get("context_window"),
                "model_type": d.get("model_type"),
                "pages": page_pairs,
            }
        )
    return out


@router.post("/compare-matrix")
async def compare_matrix(
    body: CompareMatrixRequest,
    current_user: dict = Depends(require_permission(DOCUMENT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """跨文献结构化演进对比矩阵（步骤 19）：维度 ≥5，单元必带出处锚点，无锚点不出结论。

    每个矩阵单元 `anchors[]` 携带 document_id / page / chunk / 原文片段；
    某篇对某维度无锚点时 `anchored=false`、`value=None`，不输出编造结论。
    LLM 易失败时洞察自动降级规则模板，接口不报错。
    """
    docs = await _load_matrix_docs(
        db, current_user, [d.model_dump() for d in body.documents]
    )

    matrix = await asyncio.to_thread(
        multi_paper_compare_service.build_matrix, docs, body.dimensions or None
    )
    insights = await asyncio.to_thread(multi_paper_compare_service.enhance, matrix)
    matrix["insight"] = insights
    return matrix
