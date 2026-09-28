import json
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, model_validator

from app.services.latex_format import wrap_latex


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


def _coerce_bbox(value: Any) -> list:
    """把 ``bbox`` 统一为坐标列表。

    ``document_elements.bbox`` 是 JSON 列，但历史上写入的是 ``json.dumps([...])``
    的**字符串**（双重编码），直接按 ``list`` 校验会使接口 500；此处兼容
    ``list`` / JSON 字符串（最多解两层）/ ``None`` 等形态，解析失败降级为空列表。
    """
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        current: Any = value
        for _ in range(2):
            if not isinstance(current, str):
                break
            try:
                current = json.loads(current)
            except (TypeError, ValueError):
                return []
        return current if isinstance(current, list) else []
    return []


class PageElementResponse(BaseModel):
    """页面元素响应。

    公式元素统一以 **LaTeX** 交付，字段口径与
    :mod:`app.services.latex_format` 一致：

    - ``latex``：规范 LaTeX 主体（无定界符），便于直接复制；
    - ``latex_display``：带统一定界符（行内 ``$...$`` / 行间 ``$$...$$``），可直接渲染；
    - ``is_display``：``True`` 行间公式 / ``False`` 行内公式；
    - ``formula_number``：公式编号（``\\tag{}`` 或行尾 ``(1)``）；
    - ``formula_source``：来源（``image_pix2tex`` / ``text_layer``）；
    - ``formula_normalized``：是否成功转成 LaTeX（``False`` 时前端应降级为文本展示）。
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    element_type: str
    bbox: list = []
    content: Optional[str] = None
    confidence: Optional[float] = None
    metadata: dict = {}

    # ── 公式 LaTeX 统一字段（仅 element_type='formula' 时有值）──
    latex: Optional[str] = None
    latex_display: Optional[str] = None
    is_display: Optional[bool] = None
    formula_number: Optional[str] = None
    formula_source: Optional[str] = None
    formula_normalized: Optional[bool] = None

    @model_validator(mode="before")
    @classmethod
    def _from_element(cls, data: Any) -> Any:
        """把 ORM 元素规整为可校验的 dict（含 LaTeX 字段派生）。"""
        if isinstance(data, dict):
            return data
        meta = getattr(data, "element_metadata", None)
        if not isinstance(meta, dict):
            meta = {}
        element_type = getattr(data, "element_type", None)
        content = getattr(data, "content", None)
        payload: dict = {
            "id": getattr(data, "id", None),
            "element_type": element_type,
            "bbox": _coerce_bbox(getattr(data, "bbox", None)),
            "content": content,
            "confidence": getattr(data, "confidence", None),
            "metadata": meta,
        }
        if element_type == "formula":
            display = meta.get("is_display")
            body = meta.get("latex") or content or ""
            payload.update(
                {
                    "latex": body,
                    "latex_display": meta.get("latex_display") or wrap_latex(body, bool(display)),
                    "is_display": bool(display) if display is not None else None,
                    "formula_number": meta.get("number"),
                    "formula_source": meta.get("source"),
                    "formula_normalized": meta.get("normalized"),
                }
            )
        return payload


class PageElementsResponse(BaseModel):
    page_number: int
    elements: List[PageElementResponse]
