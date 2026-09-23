from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import get_current_user
from app.services.citation_link_service import citation_link_service

router = APIRouter()


class CitationMapRequest(BaseModel):
    pages_text: list[str] = []
    references: list[dict] = []


class TitleTreeRequest(BaseModel):
    pdf_path: str = ""


@router.post("/map")
async def build_map(body: CitationMapRequest, current_user: dict = Depends(get_current_user)):
    """引用 ↔ 参考文献双向映射：定位正文 [n] 引用并关联 reference index。"""
    return citation_link_service.build_map(body.pages_text, body.references)


@router.post("/title-tree")
async def title_tree(body: TitleTreeRequest, current_user: dict = Depends(get_current_user)):
    """标题树：读取 PDF 大纲层级（PyMuPDF get_toc），缺失降级为空树。"""
    return citation_link_service.title_tree(body.pdf_path)
