from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text, func

from app.models.base import Base, generate_uuid


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    task_type = Column(String(30), nullable=False)
    document_id = Column(String(36))
    assigned_to = Column(String(36))
    assigned_by = Column(String(36))
    due_at = Column(DateTime)
    status = Column(String(20), nullable=False, default="pending")
    priority = Column(Integer, nullable=False, default=0)
    progress = Column(Float, nullable=False, default=0)
    params = Column(JSON, default=dict)
    result = Column(JSON, default=dict)
    error_message = Column(Text)
    celery_task_id = Column(String(255))
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
