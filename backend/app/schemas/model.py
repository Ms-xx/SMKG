from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ModelBase(BaseModel):
    name: str
    version: str
    model_type: str
    framework: Optional[str] = None
    file_path: Optional[str] = None
    metrics: Optional[dict] = {}


class ModelCreate(ModelBase):
    pass


class ModelResponse(ModelBase):
    id: str
    is_active: bool
    created_by: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ModelStatusUpdate(BaseModel):
    is_active: bool
