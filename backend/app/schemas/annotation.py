from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AnnotationBase(BaseModel):
    document_id: str
    element_id: Optional[str] = None
    annotation_type: str
    content: dict
    confidence: Optional[float] = None


class AnnotationCreate(AnnotationBase):
    pass


class AnnotationUpdate(BaseModel):
    content: Optional[dict] = None
    confidence: Optional[float] = None
    # 乐观锁基数：客户端提交其最后看到该标注的 updated_at；
    # 与库中当前值不一致时判定冲突（409），避免覆盖他人修改。
    base_updated_at: Optional[datetime] = None


class AnnotationResponse(BaseModel):
    id: str
    document_id: str
    element_id: Optional[str] = None
    annotation_type: str
    content: dict
    confidence: Optional[float] = None
    status: str
    annotated_by: str
    first_reviewed_by: Optional[str] = None
    first_review_comment: Optional[str] = None
    first_reviewed_at: Optional[datetime] = None
    final_reviewed_by: Optional[str] = None
    final_review_comment: Optional[str] = None
    final_reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AnnotationVersionResponse(BaseModel):
    id: str
    annotation_id: str
    content: dict
    changed_by: str
    change_type: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewRequest(BaseModel):
    approved: bool
    comment: Optional[str] = None
