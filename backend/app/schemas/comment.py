from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class CommentCreate(BaseModel):
    annotation_id: str
    content: str
    parent_id: Optional[str] = None


class CommentResponse(BaseModel):
    id: str
    annotation_id: str
    parent_id: Optional[str] = None
    user_id: str
    username: Optional[str] = None
    full_name: Optional[str] = None
    content: str
    mentions: List[str] = []
    created_at: datetime
    updated_at: datetime


class CommentListResponse(BaseModel):
    items: List[CommentResponse]
    total: int
    page: int
    page_size: int


class NotificationResponse(BaseModel):
    id: str
    type: str
    title: Optional[str] = None
    content: Optional[str] = None
    sender_id: Optional[str] = None
    sender_name: Optional[str] = None
    resource_type: str
    resource_id: Optional[str] = None
    is_read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: List[NotificationResponse]
    total: int
    unread_count: int
    page: int
    page_size: int


class UnreadCountResponse(BaseModel):
    count: int
