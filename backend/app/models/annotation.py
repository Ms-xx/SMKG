from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    String,
    Text,
    func,
)

from app.models.base import Base, generate_uuid


class Annotation(Base):
    __tablename__ = "annotations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), nullable=False)
    element_id = Column(String(36))
    annotation_type = Column(String(30), nullable=False)
    content = Column(JSON, nullable=False, default=dict)
    confidence = Column(Float)
    status = Column(String(20), nullable=False, default="draft")
    annotated_by = Column(String(36), nullable=False)
    # 初审（标注 → 初审）
    first_reviewed_by = Column(String(36))
    first_review_comment = Column(Text)
    first_reviewed_at = Column(DateTime)
    # 终审（初审通过 → 终审）
    final_reviewed_by = Column(String(36))
    final_review_comment = Column(Text)
    final_reviewed_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class AnnotationVersion(Base):
    __tablename__ = "annotation_versions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    annotation_id = Column(String(36), nullable=False)
    content = Column(JSON, nullable=False, default=dict)
    changed_by = Column(String(36), nullable=False)
    change_type = Column(String(20), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36))
    action = Column(String(50), nullable=False)
    resource_type = Column(String(30), nullable=False)
    resource_id = Column(String(36))
    details = Column(JSON, default=dict)
    ip_address = Column(String(45))
    created_at = Column(DateTime, nullable=False, server_default=func.now())
