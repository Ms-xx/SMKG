from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class DocumentBase(BaseModel):
    title: str
    doi: Optional[str] = None
    authors: Optional[List[str]] = []
    abstract: Optional[str] = None
    keywords: Optional[List[str]] = []
    publication_date: Optional[datetime] = None
    journal: Optional[str] = None


class DocumentCreate(BaseModel):
    title: Optional[str] = None


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    doi: Optional[str] = None
    authors: Optional[List[str]] = None
    abstract: Optional[str] = None
    keywords: Optional[List[str]] = None
    publication_date: Optional[datetime] = None
    journal: Optional[str] = None
    references: Optional[List[dict]] = None


class DocumentResponse(BaseModel):
    id: str
    title: str
    doi: Optional[str] = None
    authors: List[str] = []
    affiliations: List[str] = []
    abstract: Optional[str] = None
    keywords: List[str] = []
    publication_date: Optional[datetime] = None
    journal: Optional[str] = None
    references: List[dict] = []
    file_path: str
    file_size: Optional[int] = None
    page_count: Optional[int] = None
    status: str
    uploaded_by: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    items: List[DocumentResponse]
    total: int
    page: int
    page_size: int


class PageElementResponse(BaseModel):
    id: str
    element_type: str
    bbox: list
    content: Optional[str] = None
    confidence: Optional[float] = None
    metadata: dict = {}


class PageElementsResponse(BaseModel):
    page_number: int
    elements: List[PageElementResponse]
