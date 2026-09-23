from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import (
    DOCUMENT_READ,
    DOCUMENT_WRITE,
    has_permission,
    require_permission,
)
from app.schemas.document import (
    DocumentListResponse,
    DocumentResponse,
    DocumentUpdate,
    PageElementsResponse,
)
from app.services.document_service import DocumentService

router = APIRouter()
doc_service = DocumentService()


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = None,
    current_user: dict = Depends(require_permission(DOCUMENT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    return await doc_service.upload_document(db, file, title, current_user["user_id"])


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    current_user: dict = Depends(require_permission(DOCUMENT_READ)),
    db: AsyncSession = Depends(get_db),
):
    scope_all = has_permission(current_user, DOCUMENT_WRITE)
    documents, total = await doc_service.list_documents(
        db, page, page_size, status, keyword, current_user["user_id"], scope_all
    )
    return DocumentListResponse(items=documents, total=total, page=page, page_size=page_size)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: dict = Depends(require_permission(DOCUMENT_READ)),
    db: AsyncSession = Depends(get_db),
):
    scope_all = has_permission(current_user, DOCUMENT_WRITE)
    return await doc_service.get_document(db, document_id, current_user["user_id"], scope_all)


@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: str,
    update_data: DocumentUpdate,
    current_user: dict = Depends(require_permission(DOCUMENT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    return await doc_service.update_document(
        db, document_id, update_data, current_user["user_id"], True
    )


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    current_user: dict = Depends(require_permission(DOCUMENT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    await doc_service.delete_document(db, document_id, current_user["user_id"], True)


@router.post("/{document_id}/parse")
async def parse_document(
    document_id: str,
    current_user: dict = Depends(require_permission(DOCUMENT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    return await doc_service.trigger_parsing(db, document_id, current_user["user_id"], True)


@router.get("/{document_id}/fulltext")
async def get_fulltext(
    document_id: str,
    current_user: dict = Depends(require_permission(DOCUMENT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """分页全文文本（正文来源）：各页 text 元素按页序聚合。"""
    scope_all = has_permission(current_user, DOCUMENT_WRITE)
    return await doc_service.get_fulltext(db, document_id, current_user["user_id"], scope_all)


@router.get("/{document_id}/pages/{page_number}/elements", response_model=PageElementsResponse)
async def get_page_elements(
    document_id: str,
    page_number: int,
    current_user: dict = Depends(require_permission(DOCUMENT_READ)),
    db: AsyncSession = Depends(get_db),
):
    scope_all = has_permission(current_user, DOCUMENT_WRITE)
    await doc_service.get_document(db, document_id, current_user["user_id"], scope_all)
    page, elements = await doc_service.get_page_elements(db, document_id, page_number)
    return PageElementsResponse(
        page_number=page.page_number,
        elements=elements,
    )
