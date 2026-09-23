from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import ANNOTATION_READ, require_permission
from app.core.security import get_current_user
from app.models.annotation import Annotation
from app.models.document import Document, DocumentElement, DocumentPage
from app.services.active_learning_service import active_learning_service

router = APIRouter()


class Sample(BaseModel):
    id: Optional[str] = None
    text: Optional[str] = None
    probs: Optional[list[float]] = None
    features: Optional[list[float]] = None
    predictions: Optional[list[list[float]]] = None


class ActiveLearningSelectRequest(BaseModel):
    samples: list[Sample] = []
    strategy: Optional[str] = Field(
        None, description="uncertainty | diversity | qbc | hybrid（不填使用默认 hybrid）"
    )
    top_k: int = Field(10, ge=1, le=200)
    uncertainty_method: Optional[str] = Field(
        None, description="entropy | least_confidence | margin"
    )
    diversity_method: Optional[str] = Field(None, description="core_set | kmeans")
    qbc_method: Optional[str] = Field(None, description="vote_entropy | disagreement")


@router.post("/select")
async def select_samples(
    body: ActiveLearningSelectRequest,
    current_user: dict = Depends(get_current_user),
):
    """主动学习采样：从样本池中挑选优先标注样本（不确定性/多样性/QBC/混合）。"""
    return active_learning_service.select(
        samples=body.samples,
        strategy=body.strategy,
        top_k=body.top_k,
        uncertainty_method=body.uncertainty_method,
        diversity_method=body.diversity_method,
        qbc_method=body.qbc_method,
    )


@router.get("/suggest")
async def suggest_samples(
    document_id: Optional[str] = Query(None, description="仅推送指定文档下的未标注元素"),
    top_k: int = Query(20, ge=1, le=200),
    current_user: dict = Depends(require_permission(ANNOTATION_READ)),
    db: AsyncSession = Depends(get_db),
):
    """低置信度样本推送（7.1/7.2）：返回未标注且置信度最低的元素，供标注者优先处理。

    置信度越低越不确定，越应优先标注；已存在标注的元素从队列中排除（7.3 回写训练集的前置），
    标注完成后该元素自动退出推送队列。
    """
    annotated_subq = select(Annotation.element_id).where(Annotation.element_id.is_not(None))

    stmt = (
        select(
            DocumentElement,
            DocumentPage.page_number,
            DocumentPage.document_id,
            Document.title,
        )
        .join(DocumentPage, DocumentElement.page_id == DocumentPage.id)
        .join(Document, DocumentPage.document_id == Document.id)
        .where(~DocumentElement.id.in_(annotated_subq))
    )
    if document_id:
        stmt = stmt.where(DocumentPage.document_id == document_id)

    rows = (await db.execute(stmt)).all()

    items = []
    for element, page_number, doc_id, title in rows:
        confidence = element.confidence if element.confidence is not None else 0.5
        items.append(
            {
                "element_id": element.id,
                "document_id": doc_id,
                "document_title": title,
                "element_type": element.element_type,
                "page_number": page_number,
                "confidence": round(float(confidence), 4),
                "uncertainty": round(1.0 - float(confidence), 4),
                "text": (element.content or "")[:120],
            }
        )

    # 置信度升序（不确定度降序），同置信度按 element_id 保证确定性
    items.sort(key=lambda x: (x["confidence"], x["element_id"]))

    results = []
    for rank, item in enumerate(items[:top_k], start=1):
        results.append(
            {
                "rank": rank,
                "element_id": item["element_id"],
                "document_id": item["document_id"],
                "document_title": item["document_title"],
                "element_type": item["element_type"],
                "page_number": item["page_number"],
                "confidence": item["confidence"],
                "score": item["uncertainty"],
                "method": "least_confidence",
                "text": item["text"],
            }
        )

    return {
        "strategy": "uncertainty",
        "backend": "builtin",
        "top_k": top_k,
        "total": len(items),
        "selected": len(results),
        "results": results,
    }
