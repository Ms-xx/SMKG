from sqlalchemy import JSON, Boolean, Column, DateTime, String, Text, func

from app.models.base import Base, generate_uuid


class AnnotationComment(Base):
    __tablename__ = "annotation_comments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    annotation_id = Column(String(36), nullable=False, index=True)
    parent_id = Column(String(36))
    user_id = Column(String(36), nullable=False)
    content = Column(Text, nullable=False)
    mentions = Column(JSON, default=list)  # 被 @ 提及的用户 user_id 列表
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), nullable=False, index=True)  # 接收者
    type = Column(String(30), nullable=False, default="mention")  # mention / reply / review
    title = Column(String(255))
    content = Column(Text)
    sender_id = Column(String(36))
    resource_type = Column(String(30), nullable=False, default="comment")
    resource_id = Column(String(36))
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
