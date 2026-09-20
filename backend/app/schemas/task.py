from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class TaskBase(BaseModel):
    task_type: str
    document_id: Optional[str] = None
    assigned_to: Optional[str] = None
    priority: int = 0
    due_at: Optional[datetime] = None
    params: Optional[dict] = {}


class TaskCreate(TaskBase):
    pass


class TaskAssign(BaseModel):
    """手动分配任务：指定负责人、优先级、截止日期。"""

    assigned_to: str
    priority: Optional[int] = None
    due_at: Optional[datetime] = None


class TaskUpdate(BaseModel):
    status: Optional[str] = None
    progress: Optional[float] = None
    result: Optional[dict] = None
    error_message: Optional[str] = None


class TaskResponse(BaseModel):
    id: str
    task_type: str
    document_id: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_by: Optional[str] = None
    due_at: Optional[datetime] = None
    status: str
    priority: int
    progress: float
    params: dict = {}
    result: dict = {}
    error_message: Optional[str] = None
    celery_task_id: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TaskListResponse(BaseModel):
    items: List[TaskResponse]
    total: int
    page: int
    page_size: int
