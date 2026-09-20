from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class OperationLogResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: dict = {}
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OperationLogListResponse(BaseModel):
    items: List[OperationLogResponse]
    total: int
    page: int
    page_size: int
