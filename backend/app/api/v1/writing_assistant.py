from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import DOCUMENT_READ, require_permission
from app.core.security import get_current_user
from app.models.document import Document
from app.services.writing_assistant_service import (
    generate_outline,
    writing_assistant_service,
)

router = APIRouter()


class OutlineRequest(BaseModel):
    idea: str = ""
    references: list[dict] = []
    # 可选：调用方可显式传入 verified 白名单（本地文档/图谱节点）；缺省由接口从库内构建
    verified: list[dict] | None = None


class DiagramRequest(BaseModel):
    diagram_type: str = Field(
        "mermaid", description="tikz | graphviz | mermaid | matplotlib"
    )
    spec: dict = {}


class CsvChartRequest(BaseModel):
    csv_text: str = ""
    chart_type: str = Field("bar", description="bar | line | radar | table")


class TranslateRequest(BaseModel):
    text: str = ""
    target: str = Field("zh", description="zh | en")


class LlmGenerateRequest(BaseModel):
    prompt: str = ""
    max_tokens: int = Field(500, ge=1, le=2000)


async def _build_verified_whitelist(db: AsyncSession) -> list[dict]:
    """从本地库 documents（含图谱 Document 节点的 document_id 回溯）构建 verified 白名单。

    仅取库内真实存在且有标题的文献，返回 [{title, document_id, node_id, page}]。
    库为空时返回空列表（调用方据此降级为不回显过滤的旧路径）。
    """
    rows = (await db.execute(select(Document.id, Document.title))).all()
    whitelist: list[dict] = []
    for doc_id, title in rows:
        if title:
            # node_id 复用 document_id（图谱 Document 节点与本地文档一一对应）
            whitelist.append(
                {
                    "title": title,
                    "document_id": doc_id,
                    "node_id": doc_id,
                    "page": None,
                }
            )
    return whitelist


@router.post("/outline")
async def outline(
    body: OutlineRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_permission(DOCUMENT_READ)),
):
    """论文框架生成：idea + 真实可溯源参考文献（无幻觉，杜绝 LLM 编造）。

    每条引用经存在性校验后才保留：优先使用调用方显式传入的 verified 白名单；
    缺省由接口从本地库 documents/图谱 Document 节点构建。无可溯源白名单（空库）时
    退化为原回显路径。返回 references[].source{document_id/node_id/page} 与
    dropped_references 统计。
    """
    verified = body.verified
    if not verified:
        verified = await _build_verified_whitelist(db)
    # 白名单为空 → 传 None（保留旧回显行为，接口不报错）
    return generate_outline(body.idea, body.references, verified or None)


@router.post("/diagram")
async def diagram(body: DiagramRequest, current_user: dict = Depends(get_current_user)):
    """架构图脚本生成：TikZ/Graphviz/Mermaid/Matplotlib 脚本模板。"""
    return writing_assistant_service.diagram(body.diagram_type, body.spec)


@router.post("/csv-chart")
async def csv_chart(
    body: CsvChartRequest, current_user: dict = Depends(get_current_user)
):
    """CSV 可视化：零依赖 SVG 图表（折线/柱状/雷达/表格）。"""
    return writing_assistant_service.csv_chart(body.csv_text, body.chart_type)


@router.post("/translate")
async def translate(
    body: TranslateRequest, current_user: dict = Depends(get_current_user)
):
    """中英学术翻译（9.1）：可插拔。未配置翻译端点时降级回显原文。"""
    return writing_assistant_service.translate(body.text, body.target)


@router.post("/llm-generate")
async def llm_generate(
    body: LlmGenerateRequest, current_user: dict = Depends(get_current_user)
):
    """真实 LLM 文本生成（9.2）：可插拔。未配置 LLM 端点时降级为规则占位。"""
    return writing_assistant_service.llm_generate(body.prompt, body.max_tokens)
