from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text, func

from app.models.base import Base, generate_uuid


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(500), nullable=False)
    doi = Column(String(100), unique=True)
    authors = Column(JSON, default=list)
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

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), nullable=False)
    page_number = Column(Integer, nullable=False)
    image_path = Column(String(500))
    elements = Column(JSON, default=list)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class DocumentElement(Base):
    __tablename__ = "document_elements"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    page_id = Column(String(36), nullable=False)
    element_type = Column(String(20), nullable=False)
    bbox = Column(JSON, nullable=False)
    content = Column(Text)
    element_metadata = Column("metadata", JSON, default=dict)
    confidence = Column(Float)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
