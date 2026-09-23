from sqlalchemy import JSON, Column, DateTime, Float, Index, Integer, String, Text, func

from app.models.base import Base, generate_uuid


class Document(Base):
    __tablename__ = "documents"
    # 10.1 性能索引：新库由 create_all 生成；存量库见 backend/sql/idx_performance.sql
    __table_args__ = (
        Index("ix_documents_uploaded_by", "uploaded_by"),
        Index("ix_documents_status", "status"),
        Index("ix_documents_created_at", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(500), nullable=False)
    doi = Column(String(100), unique=True)
    authors = Column(JSON, default=list)
    affiliations = Column(JSON, default=list)
    abstract = Column(Text)
    keywords = Column(JSON, default=list)
    publication_date = Column(DateTime)
    journal = Column(String(200))
    references = Column(JSON, default=list)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    page_count = Column(Integer)
    status = Column(String(20), nullable=False, default="uploaded")
    uploaded_by = Column(String(36), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class DocumentPage(Base):
    __tablename__ = "document_pages"
    # 10.1 性能索引
    __table_args__ = (
        Index("ix_pages_doc_page", "document_id", "page_number"),
        Index("ix_pages_document_id", "document_id"),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), nullable=False)
    page_number = Column(Integer, nullable=False)
    image_path = Column(String(500))
    elements = Column(JSON, default=list)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class DocumentElement(Base):
    __tablename__ = "document_elements"
    # 10.1 性能索引
    __table_args__ = (
        Index("ix_elements_page_id", "page_id"),
        Index("ix_elements_type", "element_type"),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    page_id = Column(String(36), nullable=False)
    element_type = Column(String(20), nullable=False)
    bbox = Column(JSON, nullable=False)
    content = Column(Text)
    element_metadata = Column("metadata", JSON, default=dict)
    confidence = Column(Float)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
