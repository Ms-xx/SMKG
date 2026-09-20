from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.security import get_current_user
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
