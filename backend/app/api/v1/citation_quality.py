from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import DOCUMENT_READ, require_permission
from app.models.document import Document
from app.services.citation_quality_service import (
    _short_key,
    citation_quality_service,
)
from app.services.document_service import DocumentService

router = APIRouter()
doc_service = DocumentService()


class CitationScoreRequest(BaseModel):
    document_ids: list[str] = Field(default_factory=list, description="待打分的文档 id 列表")


def _build_cite_edges(docs: list[Document]) -> dict[str, dict]:
    """构建 (doc_id -> {ref_title_key: has_edge})：引用若指向语料内真实文档标题则视为存在 CITES 边。"""
    edges: dict[str, dict] = {d.id: {} for d in docs}
    corpus_keys = {_short_key(d.title or "") for d in docs}
    for other in docs:
        for r in other.references or []:
            rkey = _short_key(r.get("title") or r.get("raw") or "")
            if rkey and rkey in corpus_keys:
                edges[other.id].setdefault(rkey, True)
    return edges


@router.post("/score")
async def score(
    body: CitationScoreRequest,
    current_user: dict = Depends(require_permission(DOCUMENT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """引用含金量评分（步骤 20）：对指定文档的每条参考文献打分并给出信号明细。

    信号：①位置权重 ②正文出现次数 ③数值/结论表述 ④共享主题/作者 ⑤CITES 边。
    返回 core/supporting/perfunctory 三档与可解释 signals；只打标不删数据。
    """
    ids = [i for i in (body.document_ids or []) if i]
    if not ids:
        return citation_quality_service.batch([])
    result = await db.execute(select(Document).where(Document.id.in_(ids)))
    row_docs = result.scalars().all()

    records: list[dict] = []
    for d in row_docs:
        try:
            fulltext = await doc_service.get_fulltext(db, d.id, None, True)
            pages = [p.get("text") or "" for p in (fulltext.get("pages") or [])]
        except Exception:  # noqa: BLE001
            pages = []
        records.append(
            {
                "document_id": d.id,
                "title": d.title,
                "authors": d.authors or [],
                "references": d.references or [],
                "pages": pages,
            }
        )

    edges = _build_cite_edges(row_docs)
    scored = []
    for rec in records:
        scored.append(citation_quality_service.analyze(rec, edges.get(rec["document_id"])))
    # 汇总
    agg = {
        "backend": "builtin",
        "document_count": len(scored),
        "total_refs": sum(r["total"] for r in scored),
        "perfunctory_count": sum(r["perfunctory_count"] for r in scored),
        "core_count": sum(r["core_count"] for r in scored),
        "documents": scored,
    }
    return agg
