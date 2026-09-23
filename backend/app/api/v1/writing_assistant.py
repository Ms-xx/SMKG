from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.services.writing_assistant_service import writing_assistant_service

router = APIRouter()


class OutlineRequest(BaseModel):
    idea: str = ""
    references: list[dict] = []


class DiagramRequest(BaseModel):
    diagram_type: str = Field("mermaid", description="tikz | graphviz | mermaid | matplotlib")
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


@router.post("/outline")
async def outline(body: OutlineRequest, current_user: dict = Depends(get_current_user)):
    """论文框架生成：idea + 真实参考文献（无幻觉，仅回显真实条目）。"""
    return writing_assistant_service.outline(body.idea, body.references)


@router.post("/diagram")
async def diagram(body: DiagramRequest, current_user: dict = Depends(get_current_user)):
    """架构图脚本生成：TikZ/Graphviz/Mermaid/Matplotlib 脚本模板。"""
    return writing_assistant_service.diagram(body.diagram_type, body.spec)


@router.post("/csv-chart")
async def csv_chart(body: CsvChartRequest, current_user: dict = Depends(get_current_user)):
    """CSV 可视化：零依赖 SVG 图表（折线/柱状/雷达/表格）。"""
    return writing_assistant_service.csv_chart(body.csv_text, body.chart_type)


@router.post("/translate")
async def translate(body: TranslateRequest, current_user: dict = Depends(get_current_user)):
    """中英学术翻译（9.1）：可插拔。未配置翻译端点时降级回显原文。"""
    return writing_assistant_service.translate(body.text, body.target)


@router.post("/llm-generate")
async def llm_generate(
    body: LlmGenerateRequest, current_user: dict = Depends(get_current_user)
):
    """真实 LLM 文本生成（9.2）：可插拔。未配置 LLM 端点时降级为规则占位。"""
    return writing_assistant_service.llm_generate(body.prompt, body.max_tokens)
