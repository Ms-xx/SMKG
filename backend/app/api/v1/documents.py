from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
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
from app.services import reference_service
from app.services.document_service import DocumentService
from app.utils.minio_client import MinioClient


def _xml_escape(text) -> str:
    """对 XML 文本做单次安全转义。"""
    s = str(text)
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return s.replace('"', "&quot;").replace("'", "&apos;")


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


@router.get("/{document_id}/file")
async def get_document_file(
    document_id: str,
    current_user: dict = Depends(require_permission(DOCUMENT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """返回原始 PDF 文件（PDFViewer 内联查看用），鉴权后从 MinIO/本地存储读取。"""
    scope_all = has_permission(current_user, DOCUMENT_WRITE)
    doc = await doc_service.get_document(db, document_id, current_user["user_id"], scope_all)
    try:
        data = MinioClient().download_file(doc.file_path)
    except Exception as e:
        raise HTTPException(status_code=404, detail="PDF file not found") from e
    return Response(content=data, media_type="application/pdf")


@router.get("/{document_id}/fulltext")
async def get_fulltext(
    document_id: str,
    current_user: dict = Depends(require_permission(DOCUMENT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """分页全文文本（正文来源）：各页 text 元素按页序聚合。"""
    scope_all = has_permission(current_user, DOCUMENT_WRITE)
    return await doc_service.get_fulltext(db, document_id, current_user["user_id"], scope_all)


@router.get("/{document_id}/export")
async def export_document_jats(
    document_id: str,
    current_user: dict = Depends(require_permission(DOCUMENT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """
    导出结构化 JATS XML（article + front + body + ref-list）。

    正文聚合自分页 fulltext；参考文献用规则抽取（仅当 file_path 指向本地 PDF，
    否则 ref-list 为空，绝不编造）。JATS_EXPORT_ENABLED=False 时返回 503。
    """
    if not settings.JATS_EXPORT_ENABLED:
        raise HTTPException(status_code=503, detail="JATS export is disabled")

    scope_all = has_permission(current_user, DOCUMENT_WRITE)
    doc = await doc_service.get_document(db, document_id, current_user["user_id"], scope_all)
    title = str(getattr(doc, "title", None) or "").strip() or document_id

    # 正文：每页 text 按行拆分为 <p>
    fulltext = await doc_service.get_fulltext(db, document_id, current_user["user_id"], scope_all)
    body_paras: list[str] = []
    for page in fulltext.get("pages") or []:
        for seg in (str(page.get("text") or "")).split("\n"):
            if seg.strip():
                body_paras.append(seg.strip())

    # 参考文献：仅当 file_path 指向本地 PDF 时抽取，否则 ref-list 为空
    references: list[dict] = []
    file_path = getattr(doc, "file_path", None)
    if file_path:
        references = reference_service.reference_service.extract_references(file_path) or []
        references = reference_service.enhance_references_with_grobid(references)

    ref_list = reference_service.references_to_jats(references)
    if ref_list.startswith("<?xml"):
        ref_list = ref_list.split("\n", 1)[1]  # 去掉顶层声明，以便嵌入 <article>

    body_inner = "\n".join(f"        <p>{_xml_escape(p)}</p>" for p in body_paras)
    xml_str = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<article xmlns="http://www.ncbi.nlm.nih.gov/JATS1" '
        'xmlns:xlink="http://www.w3.org/1999/xlink">\n'
        "  <front>\n"
        "    <article-meta>\n"
        "      <title-group>\n"
        f"        <article-title>{_xml_escape(title)}</article-title>\n"
        "      </title-group>\n"
        "    </article-meta>\n"
        "  </front>\n"
        "  <body>\n"
        f"{body_inner}\n"
        "  </body>\n"
        f"{ref_list}\n"
        "</article>"
    )
    return Response(
        content=xml_str,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{document_id}.jats.xml"'},
    )


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
