"""
GraphRAG API 路由
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from neo4j_client import neo4j_client
from lmstudio_client import llm_client as lmstudio_client
from graphrag_service import graphrag_service
from indexer import graph_indexer

router = APIRouter()


# ─── 请求/响应模型 ───────────────────────────────────────

class NodeCreate(BaseModel):
    label: str = Field(..., description="节点标签，如 Material, Property, Method")
    id: str = Field(..., description="节点唯一标识")
    properties: dict[str, Any] = Field(default_factory=dict)


class RelationCreate(BaseModel):
    source_label: str
    source_id: str
    target_label: str
    target_id: str
    rel_type: str
    properties: dict[str, Any] = Field(default_factory=dict)


class BatchImportRequest(BaseModel):
    nodes: list[NodeCreate] = Field(default_factory=list)
    relations: list[RelationCreate] = Field(default_factory=list)
    document_id: Optional[str] = Field(None, description="可选：关联文档 ID")
    document_title: Optional[str] = Field(None, description="可选：文档标题")


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    return_context: bool = Field(False, description="是否返回检索到的图谱上下文")
    include_sources: bool = Field(True, description="是否返回带 document_id / snippet 的溯源来源")


class DocumentIndexRequest(BaseModel):
    doc_id: str
    doc_title: str
    entities: list[dict[str, Any]] = Field(default_factory=list)
    relations: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    chunks: list[str] = Field(default_factory=list, description="文档文本分块，用于向量化入库")


class HybridSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(5, ge=1, le=100)


class GenerateRequest(BaseModel):
    prompt: str
    system_prompt: Optional[str] = None
    temperature: float = Field(0.7, ge=0, le=2.0)
    max_tokens: int = Field(1024, ge=1, le=8192)


class LoadModelRequest(BaseModel):
    model: Optional[str] = Field(None, description="模型 ID，不填则使用 .env 中的默认模型")


# ─── 健康检查 ───────────────────────────────────────

@router.get("/health")
async def health():
    """服务健康状态"""
    return {
        "status": "healthy",
        "service": "GraphRAG",
        "version": "1.0.0",
    }


# ─── 图谱管理 ───────────────────────────────────────

@router.post("/graph/nodes")
async def create_node(body: NodeCreate):
    """添加实体节点"""
    result = await neo4j_client.create_or_update_node(
        label=body.label,
        match_key="id",
        match_value=body.id,
        properties={"id": body.id, **body.properties},
    )
    return {"message": "节点创建成功", "node": result}


@router.post("/graph/relations")
async def create_relation(body: RelationCreate):
    """添加实体间关系"""
    result = await neo4j_client.create_relation(
        source_label=body.source_label,
        source_key="id",
        source_value=body.source_id,
        target_label=body.target_label,
        target_key="id",
        target_value=body.target_id,
        rel_type=body.rel_type,
        properties=body.properties,
    )
    return {"message": "关系创建成功", "relation": result}


@router.post("/graph/batch")
async def batch_import(body: BatchImportRequest):
    """
    批量导入节点和关系到图谱

    支持两种模式:
    1. 纯节点/关系导入: 填写 nodes/relations
    2. 完整文档索引: 填写 document_id/document_title + entities/relations
    """
    if body.document_id:
        # 完整文档索引模式
        result = await graph_indexer.index_document(
            doc_id=body.document_id,
            doc_title=body.document_title or body.document_id,
            entities=[n.model_dump() for n in body.nodes],
            relations=[r.model_dump() for r in body.relations],
            metadata={},
        )
        return {"message": "文档索引完成", **result}

    # 纯节点/关系导入
    nodes_result = await neo4j_client.batch_import_nodes(
        "GenericEntity",
        [{"id": n.id, **n.properties} for n in body.nodes],
        id_key="id",
    )
    rels_result = await neo4j_client.batch_import_relations(
        [r.model_dump() for r in body.relations]
    )
    return {
        "message": "批量导入完成",
        "nodes": nodes_result,
        "relations": rels_result,
    }


@router.delete("/graph/clear")
async def clear_graph():
    """清空整个图谱 (危险操作!)"""
    result = await neo4j_client.clear_graph()
    return {"message": "图谱已清空", **result}


@router.get("/graph/stats")
async def graph_stats():
    """图谱统计信息"""
    stats = await neo4j_client.get_stats()
    return stats


@router.get("/graph/nodes/{label}")
async def get_nodes_by_label(
    label: str,
    limit: int = Query(50, ge=1, le=200),
):
    """按标签查询所有节点"""
    nodes = await neo4j_client.find_nodes_by_label(label, limit=limit)
    return {"label": label, "count": len(nodes), "nodes": nodes}


@router.get("/graph/nodes/keyword/{keyword}")
async def search_nodes(
    keyword: str,
    limit: int = Query(20, ge=1, le=100),
):
    """按关键词模糊搜索节点"""
    nodes = await neo4j_client.find_nodes_by_keyword(keyword, limit=limit)
    return {"keyword": keyword, "count": len(nodes), "nodes": nodes}


@router.get("/graph/relations/type/{rel_type}")
async def get_relations_by_type(
    rel_type: str,
    limit: int = Query(20, ge=1, le=100),
):
    """按类型查询关系"""
    rels = await neo4j_client.find_relations_by_keyword("", rel_type=rel_type, limit=limit)
    return {"type": rel_type, "count": len(rels), "relations": rels}


# ─── GraphRAG 问答 ───────────────────────────────────────

@router.post("/query")
async def rag_query(body: QueryRequest):
    """
    GraphRAG 问答

    流程:
    1. LLM 提取关键词
    2. Neo4j 图谱检索相关实体和关系
    3. 组装上下文 + 调用 LLM 生成答案
    """
    result = await graphrag_service.query(
        question=body.question,
        return_context=body.return_context,
        include_sources=body.include_sources,
    )
    return result


@router.get("/query/history")
async def query_history():
    """查询历史 (内存中保留最近 20 条)"""
    return {"history": graphrag_service._history[-20:]}


# ─── LLM / 模型管理 ───────────────────────────────────────

@router.get("/llm/models")
async def list_models():
    """列出 LM Studio 中已加载/可用的模型"""
    try:
        return lmstudio_client.list_models()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"LM Studio 连接失败: {e}")


@router.get("/llm/status")
async def llm_status():
    """LLM 当前状态"""
    try:
        model = lmstudio_client.get_loaded_model()
        return {
            "llm_provider": "LM Studio",
            "base_url": lmstudio_client.base_url,
            "current_model": lmstudio_client._current_model,
            "loaded_model": model,
        }
    except Exception as e:
        return {
            "llm_provider": "LM Studio",
            "base_url": lmstudio_client.base_url,
            "status": "disconnected",
            "error": str(e),
        }


@router.post("/llm/load")
async def load_model(body: LoadModelRequest):
    """
    让 LM Studio 预加载模型到内存

    模型加载需要一定时间(取决于模型大小和显存/内存),
    建议在首次使用前预先调用此接口
    """
    try:
        result = lmstudio_client.load_model(model_id=body.model)
        return {"message": "模型加载成功", "model": body.model or lmstudio_client._current_model, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模型加载失败: {e}")


@router.post("/llm/unload")
async def unload_model():
    """卸载当前模型"""
    try:
        result = lmstudio_client.unload_model()
        return {"message": "模型已卸载", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/llm/generate")
async def direct_generate(body: GenerateRequest):
    """
    直接调用 LLM 生成文本 (不经过 GraphRAG)

    用于测试 LLM 连接或不需要图谱检索的场景
    """
    try:
        response = lmstudio_client.generate(
            prompt=body.prompt,
            system_prompt=body.system_prompt,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )
        content = lmstudio_client.extract_content(response)
        return {
            "prompt": body.prompt,
            "answer": content,
            "raw": response,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM 生成失败: {e}")


# ─── 文档索引 ───────────────────────────────────────

@router.post("/index/document")
async def index_document(body: DocumentIndexRequest):
    """
    将一篇文档的实体和关系完整索引到图谱

    通常在文档解析 + 信息抽取完成后调用,
    将抽取结果 (entities + relations) 写入 Neo4j

    entities 格式:
    [{"text": "钙钛矿", "entity_type": "Material", "start": 0, "end": 3}, ...]

    relations 格式:
    [{"source": "钙钛矿", "source_type": "Material", "target": "高效率",
      "target_type": "Property", "relation_type": "HAS_PROPERTY",
      "context": "钙钛矿具有高光电转换效率"}, ...]
    """
    result = await graph_indexer.index_document(
        doc_id=body.doc_id,
        doc_title=body.doc_title,
        entities=body.entities,
        relations=body.relations,
        metadata=body.metadata,
        chunks=body.chunks,
    )
    return {"message": "文档索引完成", **result}


@router.post("/hybrid/search")
async def hybrid_search(body: HybridSearchRequest):
    """
    混合检索（向量 + BM25 + RRF，可选 Cross-Encoder 精排）

    返回与索引管线写入的实体 / 关系 / chunk 向量库对齐的检索结果。
    """
    from hybrid_retrieval import hybrid_retriever

    return hybrid_retriever.search(query=body.query, top_k=body.top_k)


# ─── 演示数据 ───────────────────────────────────────

DEMO_NODES = [
    # 材料类 (原有5个)
    {"label": "Material", "id": "MAPbI3", "properties": {"name": "MAPbI₃", "full_name": "甲基铵碘化铅", "formula": "CH₃NH₃PbI₃", "description": "最常用的钙钛矿吸光材料"}},
    {"label": "Material", "id": "FAPbI3", "properties": {"name": "FAPbI₃", "full_name": "甲脒碘化铅", "formula": "HC(NH₂)₂PbI₃", "description": "具有更窄带隙的钙钛矿材料"}},
    {"label": "Material", "id": "Spiro-OMeTAD", "properties": {"name": "Spiro-OMeTAD", "full_name": "空穴传输材料", "formula": "C81H68N4O8", "description": "常用的空穴传输材料"}},
    {"label": "Material", "id": "TiO2", "properties": {"name": "TiO₂", "full_name": "二氧化钛", "formula": "TiO₂", "description": "电子传输层材料"}},
    {"label": "Material", "id": "PCBM", "properties": {"name": "PCBM", "full_name": "富勒烯衍生物", "formula": "C72H14O2", "description": "电子传输材料"}},
    # 材料类 (新增10个)
    {"label": "Material", "id": "CsPbI3", "properties": {"name": "CsPbI₃", "full_name": "铯铅碘化物", "formula": "CsPbI₃", "description": "全无机钙钛矿材料，热稳定性好"}},
    {"label": "Material", "id": "FASnI3", "properties": {"name": "FASnI₃", "full_name": "甲脒锡碘化物", "formula": "FASnI₃", "description": "锡基钙钛矿，低毒环保"}},
    {"label": "Material", "id": "PTAA", "properties": {"name": "PTAA", "full_name": "聚[双(4-苯基)(2,4,6-三甲基苯基)胺]", "formula": "C51H43N", "description": "聚合物空穴传输材料"}},
    {"label": "Material", "id": "PEDOT_PSS", "properties": {"name": "PEDOT:PSS", "full_name": "聚(3,4-乙烯二氧噻吩):聚苯乙烯磺酸", "formula": "(C6H4O2S)n", "description": "透明导电聚合物电极"}},
    {"label": "Material", "id": "SnO2", "properties": {"name": "SnO₂", "full_name": "氧化锡", "formula": "SnO₂", "description": "电子传输层材料，带隙宽"}},
    {"label": "Material", "id": "ZrO2", "properties": {"name": "ZrO₂", "full_name": "氧化锆", "formula": "ZrO₂", "description": "绝缘层材料"}},
    {"label": "Material", "id": "Al2O3", "properties": {"name": "Al₂O₃", "full_name": "氧化铝", "formula": "Al₂O₃", "description": "钝化层材料"}},
    {"label": "Material", "id": "Au", "properties": {"name": "Au", "full_name": "金", "formula": "Au", "description": "金属电极材料"}},
    {"label": "Material", "id": "Ag", "properties": {"name": "Ag", "full_name": "银", "formula": "Ag", "description": "金属电极材料"}},
    {"label": "Material", "id": "ITO", "properties": {"name": "ITO", "full_name": "氧化铟锡", "formula": "In₂O₃:Sn", "description": "透明导电氧化物电极"}},
    # 性能类 (原有3个)
    {"label": "Property", "id": "high_efficiency", "properties": {"name": "高效率", "value": "25.7%", "description": "单结钙钛矿太阳能电池最高效率"}},
    {"label": "Property", "id": "good_stability", "properties": {"name": "稳定性", "description": "钙钛矿材料的稳定性"}},
    {"label": "Property", "id": "broad_absorption", "properties": {"name": "宽光谱吸收", "description": "覆盖可见光区域"}},
    # 性能类 (新增10个)
    {"label": "Property", "id": "high_voltage", "properties": {"name": "高开路电压", "value": "1.18V", "description": "钙钛矿电池开路电压可达1.18V"}},
    {"label": "Property", "id": "high_fill_factor", "properties": {"name": "高填充因子", "value": "84%", "description": "填充因子可达84%"}},
    {"label": "Property", "id": "long_diffusion", "properties": {"name": "长载流子扩散长度", "value": ">1μm", "description": "载流子扩散长度超过1微米"}},
    {"label": "Property", "id": "low_recombination", "properties": {"name": "低复合率", "description": "缺陷密度低，载流子复合少"}},
    {"label": "Property", "id": "tunable_bandgap", "properties": {"name": "可调带隙", "description": "通过组分调控带隙1.2-3.0eV"}},
    {"label": "Property", "id": "low_cost", "properties": {"name": "低成本", "description": "原材料成本低，可溶液法制备"}},
    {"label": "Property", "id": "flexible", "properties": {"name": "柔性可弯曲", "description": "可制备在柔性基底上"}},
    {"label": "Property", "id": "high_transparency", "properties": {"name": "高透明度", "description": "可见光透过率高"}},
    {"label": "Property", "id": "fast_charge", "properties": {"name": "快速电荷提取", "description": "载流子迁移率高"}},
    {"label": "Property", "id": "photo_thermal", "properties": {"name": "光热转换", "description": "优异的光热转换性能"}},
    # 方法类 (原有2个)
    {"label": "Method", "id": "anti_solvent_method", "properties": {"name": "反溶剂法", "full_name": "反溶剂结晶法", "description": "通过反溶剂诱导钙钛矿结晶"}},
    {"label": "Method", "id": "vacuum_deposition", "properties": {"name": "真空蒸镀法", "description": "真空条件下物理气相沉积"}},
    # 方法类 (新增10个)
    {"label": "Method", "id": "one_step_method", "properties": {"name": "一步法", "description": "前驱体一步直接成膜"}},
    {"label": "Method", "id": "two_step_method", "properties": {"name": "两步法", "description": "先沉积PbI₂再转化为钙钛矿"}},
    {"label": "Method", "id": "inkjet_printing", "properties": {"name": " inkjet打印", "description": "喷墨打印技术制备薄膜"}},
    {"label": "Method", "id": "blade_coating", "properties": {"name": "刮刀涂布", "description": "大面积薄膜制备技术"}},
    {"label": "Method", "id": "spin_coating", "properties": {"name": "旋涂法", "description": "实验室常用薄膜制备方法"}},
    {"label": "Method", "id": "gas_assistant", "properties": {"name": "气淬法", "description": "惰性气体辅助结晶"}},
    {"label": "Method", "id": "hot_casting", "properties": {"name": "热铸法", "description": "热基底上快速结晶"}},
    {"label": "Method", "id": "interface_engineering", "properties": {"name": "界面工程", "description": "修饰界面提升性能"}},
    {"label": "Method", "id": "passivation", "properties": {"name": "钝化处理", "description": "减少表面缺陷态"}},
    {"label": "Method", "id": "light_soaking", "properties": {"name": "光浸润", "description": "光照提升器件性能"}},
    # 设备/参数类 (新增5个)
    {"label": "Parameter", "id": "annealing_temp", "properties": {"name": "退火温度", "value": "100°C", "description": "钙钛矿薄膜退火温度"}},
    {"label": "Parameter", "id": "spin_speed", "properties": {"name": "旋涂转速", "value": "3000rpm", "description": "旋涂工艺转速参数"}},
    {"label": "Parameter", "id": "humidity", "properties": {"name": "环境湿度", "value": "30%", "description": "制备环境相对湿度"}},
    # 结果类 (新增5个)
    {"label": "Result", "id": "stabilized_power", "properties": {"name": "稳态输出", "value": "24.5%", "description": "稳态功率转换效率"}},
    {"label": "Result", "id": "T80_lifetime", "properties": {"name": "T80寿命", "value": "1000h", "description": "效率衰减至80%的时间"}},
    {"label": "Result", "id": "jsc_value", "properties": {"name": "短路电流密度", "value": "26mA/cm²", "description": "Jsc值"}},
    {"label": "Result", "id": "voc_value", "properties": {"name": "开路电压", "value": "1.15V", "description": "Voc值"}},
    {"label": "Result", "id": "ff_value", "properties": {"name": "填充因子", "value": "82%", "description": "FF值"}},
]

DEMO_RELATIONS = [
    # 原有关系
    {"source_label": "Material", "source_id": "MAPbI3", "target_label": "Property", "target_id": "high_efficiency", "rel_type": "ACHIEVES", "properties": {"context": "MAPbI₃钙钛矿电池实现了超过25%的光电转换效率"}},
    {"source_label": "Material", "source_id": "MAPbI3", "target_label": "Property", "target_id": "good_stability", "rel_type": "HAS_CHALLENGE", "properties": {"context": "MAPbI₃对水分和热量敏感，稳定性有待提升"}},
    {"source_label": "Material", "source_id": "FAPbI3", "target_label": "Property", "target_id": "high_efficiency", "rel_type": "ACHIEVES", "properties": {"context": "FAPbI₃基电池效率可达26%"}},
    {"source_label": "Material", "source_id": "MAPbI3", "target_label": "Property", "target_id": "broad_absorption", "rel_type": "EXHIBITS", "properties": {"context": "MAPbI₃吸收光谱范围400-800nm"}},
    {"source_label": "Method", "source_id": "anti_solvent_method", "target_label": "Material", "target_id": "MAPbI3", "rel_type": "PRODUCES", "properties": {"context": "反溶剂法可制备高质量MAPbI₃薄膜"}},
    {"source_label": "Method", "source_id": "vacuum_deposition", "target_label": "Material", "target_id": "FAPbI3", "rel_type": "PRODUCES", "properties": {"context": "真空蒸镀可精确控制FAPbI₃薄膜厚度"}},
    {"source_label": "Material", "source_id": "Spiro-OMeTAD", "target_label": "Material", "target_id": "MAPbI3", "rel_type": "TRANSPORTS_HOLE", "properties": {"context": "Spiro-OMeTAD作为空穴传输层与MAPbI₃配合使用"}},
    {"source_label": "Material", "source_id": "TiO2", "target_label": "Material", "target_id": "MAPbI3", "rel_type": "TRANSPORTS_ELECTRON", "properties": {"context": "TiO₂电子传输层提取MAPbI₃的光生电子"}},
    {"source_label": "Material", "source_id": "PCBM", "target_label": "Material", "target_id": "FAPbI3", "rel_type": "TRANSPORTS_ELECTRON", "properties": {"context": "PCBM作为电子传输层用于FAPbI₃器件"}},
    {"source_label": "Property", "source_id": "high_efficiency", "target_label": "Property", "target_id": "good_stability", "rel_type": "REQUIRES", "properties": {"context": "高效率钙钛矿电池需要同时具备良好的稳定性"}},
    # 新增关系 (40+条)
    {"source_label": "Material", "source_id": "CsPbI3", "target_label": "Property", "target_id": "good_stability", "rel_type": "EXHIBITS", "properties": {"context": "CsPbI₃全无机钙钛矿热稳定性优异"}},
    {"source_label": "Material", "source_id": "CsPbI3", "target_label": "Property", "target_id": "high_efficiency", "rel_type": "ACHIEVES", "properties": {"context": "CsPbI₃电池效率超过21%"}},
    {"source_label": "Material", "source_id": "FASnI3", "target_label": "Property", "target_id": "low_cost", "rel_type": "ENABLES", "properties": {"context": "锡基钙钛矿避免了铅的毒性问题"}},
    {"source_label": "Material", "source_id": "PTAA", "target_label": "Material", "target_id": "FAPbI3", "rel_type": "TRANSPORTS_HOLE", "properties": {"context": "PTAA作为空穴层提升FAPbI₃器件性能"}},
    {"source_label": "Material", "source_id": "PEDOT_PSS", "target_label": "Material", "target_id": "MAPbI3", "rel_type": "TRANSPORTS_HOLE", "properties": {"context": "PEDOT:PSS可用于倒置结构电池"}},
    {"source_label": "Material", "source_id": "SnO2", "target_label": "Material", "target_id": "FAPbI3", "rel_type": "TRANSPORTS_ELECTRON", "properties": {"context": "SnO₂低温制备电子传输层"}},
    {"source_label": "Material", "source_id": "ZrO2", "target_label": "Material", "target_id": "MAPbI3", "rel_type": "INSULATES", "properties": {"context": "ZrO₂绝缘层阻止载流子复合"}},
    {"source_label": "Material", "source_id": "Al2O3", "target_label": "Material", "target_id": "MAPbI3", "rel_type": "PASSIVATES", "properties": {"context": "Al₂O₃钝化层减少界面复合"}},
    {"source_label": "Material", "source_id": "Au", "target_label": "Material", "target_id": "Spiro-OMeTAD", "rel_type": "ELECTRODE", "properties": {"context": "Au作为顶部电极"}},
    {"source_label": "Material", "source_id": "Ag", "target_label": "Material", "target_id": "PCBM", "rel_type": "ELECTRODE", "properties": {"context": "Ag作为背电极"}},
    {"source_label": "Material", "source_id": "ITO", "target_label": "Material", "target_id": "PEDOT_PSS", "rel_type": "SUBSTRATE", "properties": {"context": "ITO导电玻璃作为透明基底"}},
    {"source_label": "Property", "source_id": "high_voltage", "target_label": "Property", "target_id": "high_efficiency", "rel_type": "CONTRIBUTES", "properties": {"context": "高开路电压有助于提升效率"}},
    {"source_label": "Property", "source_id": "high_fill_factor", "target_label": "Property", "target_id": "high_efficiency", "rel_type": "CONTRIBUTES", "properties": {"context": "高填充因子提升器件性能"}},
    {"source_label": "Property", "source_id": "long_diffusion", "target_label": "Property", "target_id": "high_efficiency", "rel_type": "ENABLES", "properties": {"context": "长扩散长度减少复合损失"}},
    {"source_label": "Property", "source_id": "low_recombination", "target_label": "Property", "target_id": "high_voltage", "rel_type": "CAUSES", "properties": {"context": "低复合率带来高开路电压"}},
    {"source_label": "Property", "source_id": "tunable_bandgap", "target_label": "Property", "target_id": "high_efficiency", "rel_type": "ENABLES", "properties": {"context": "可调带隙优化光谱吸收"}},
    {"source_label": "Property", "source_id": "low_cost", "target_label": "Property", "target_id": "flexible", "rel_type": "ENABLES", "properties": {"context": "低成本有利于大规模生产"}},
    {"source_label": "Property", "source_id": "flexible", "target_label": "Property", "target_id": "high_voltage", "rel_type": "ENABLES", "properties": {"context": "柔性器件可弯曲使用"}},
    {"source_label": "Property", "source_id": "high_transparency", "target_label": "Property", "target_id": "photo_thermal", "rel_type": "EXHIBITS", "properties": {"context": "高透明度利于光热应用"}},
    {"source_label": "Property", "source_id": "fast_charge", "target_label": "Property", "target_id": "high_fill_factor", "rel_type": "CAUSES", "properties": {"context": "快速电荷提取提升填充因子"}},
    {"source_label": "Method", "source_id": "one_step_method", "target_label": "Material", "target_id": "MAPbI3", "rel_type": "PRODUCES", "properties": {"context": "一步法简化工艺流程"}},
    {"source_label": "Method", "source_id": "two_step_method", "target_label": "Material", "target_id": "MAPbI3", "rel_type": "PRODUCES", "properties": {"context": "两步法可控性更好"}},
    {"source_label": "Method", "source_id": "inkjet_printing", "target_label": "Material", "target_id": "FAPbI3", "rel_type": "PRODUCES", "properties": {"context": " inkjet打印实现图案化"}},
    {"source_label": "Method", "source_id": "blade_coating", "target_label": "Material", "target_id": "MAPbI3", "rel_type": "PRODUCES", "properties": {"context": "刮刀涂布适合大面积制备"}},
    {"source_label": "Method", "source_id": "spin_coating", "target_label": "Material", "target_id": "MAPbI3", "rel_type": "PRODUCES", "properties": {"context": "旋涂法是实验室标准工艺"}},
    {"source_label": "Method", "source_id": "interface_engineering", "target_label": "Property", "target_id": "high_efficiency", "rel_type": "IMPROVES", "properties": {"context": "界面工程显著提升效率"}},
    {"source_label": "Method", "source_id": "passivation", "target_label": "Property", "target_id": "good_stability", "rel_type": "IMPROVES", "properties": {"context": "钝化处理提升器件稳定性"}},
    {"source_label": "Method", "source_id": "light_soaking", "target_label": "Property", "target_id": "high_efficiency", "rel_type": "IMPROVES", "properties": {"context": "光浸润提升初始效率"}},
    {"source_label": "Parameter", "source_id": "annealing_temp", "target_label": "Material", "target_id": "MAPbI3", "rel_type": "AFFECTS", "properties": {"context": "退火温度影响结晶质量"}},
    {"source_label": "Parameter", "source_id": "spin_speed", "target_label": "Material", "target_id": "MAPbI3", "rel_type": "AFFECTS", "properties": {"context": "旋涂转速影响薄膜厚度"}},
    {"source_label": "Parameter", "source_id": "humidity", "target_label": "Material", "target_id": "MAPbI3", "rel_type": "AFFECTS", "properties": {"context": "环境湿度影响成膜质量"}},
    {"source_label": "Result", "source_id": "stabilized_power", "target_label": "Material", "target_id": "MAPbI3", "rel_type": "MEASURES", "properties": {"context": "稳态输出验证器件性能"}},
    {"source_label": "Result", "source_id": "T80_lifetime", "target_label": "Property", "target_id": "good_stability", "rel_type": "MEASURES", "properties": {"context": "T80寿命评估稳定性"}},
    {"source_label": "Result", "source_id": "jsc_value", "target_label": "Material", "target_id": "FAPbI3", "rel_type": "MEASURES", "properties": {"context": "短路电流密度是重要参数"}},
    {"source_label": "Result", "source_id": "voc_value", "target_label": "Material", "target_id": "FAPbI3", "rel_type": "MEASURES", "properties": {"context": "开路电压与界面质量相关"}},
    {"source_label": "Result", "source_id": "ff_value", "target_label": "Material", "target_id": "FAPbI3", "rel_type": "MEASURES", "properties": {"context": "填充因子反映器件质量"}},
    {"source_label": "Material", "source_id": "FAPbI3", "target_label": "Property", "target_id": "tunable_bandgap", "rel_type": "EXHIBITS", "properties": {"context": "FAPbI₃可通过Br掺杂调控带隙"}},
    {"source_label": "Material", "source_id": "MAPbI3", "target_label": "Property", "target_id": "low_recombination", "rel_type": "EXHIBITS", "properties": {"context": "MAPbI₃缺陷容忍度高"}},
    {"source_label": "Material", "source_id": "TiO2", "target_label": "Property", "target_id": "low_recombination", "rel_type": "HAS_CHALLENGE", "properties": {"context": "TiO₂界面复合需进一步优化"}},
    {"source_label": "Method", "source_id": "hot_casting", "target_label": "Material", "target_id": "MAPbI3", "rel_type": "PRODUCES", "properties": {"context": "热铸法获得大晶粒薄膜"}},
    {"source_label": "Method", "source_id": "gas_assistant", "target_label": "Material", "target_id": "FAPbI3", "rel_type": "PRODUCES", "properties": {"context": "气淬法控制结晶速率"}},
    {"source_label": "Material", "source_id": "CsPbI3", "target_label": "Property", "target_id": "photo_thermal", "rel_type": "EXHIBITS", "properties": {"context": "CsPbI₃具有优异光热稳定性"}},
]


@router.post("/seed/demo")
async def seed_demo_data():
    """初始化钙钛矿太阳能电池领域的10个示例实体和10条关系"""
    created_nodes = 0
    created_relations = 0

    # 创建节点
    for node_data in DEMO_NODES:
        try:
            await neo4j_client.create_or_update_node(
                label=node_data["label"],
                match_key="id",
                match_value=node_data["id"],
                properties=node_data["properties"],
            )
            created_nodes += 1
        except Exception as e:
            pass

    # 创建关系
    for rel_data in DEMO_RELATIONS:
        try:
            await neo4j_client.create_relation(
                source_label=rel_data["source_label"],
                source_key="id",
                source_value=rel_data["source_id"],
                target_label=rel_data["target_label"],
                target_key="id",
                target_value=rel_data["target_id"],
                rel_type=rel_data["rel_type"],
                properties=rel_data.get("properties"),
            )
            created_relations += 1
        except Exception as e:
            pass

    stats = await neo4j_client.get_stats()
    return {
        "message": "示例数据初始化完成",
        "nodes_created": created_nodes,
        "relations_created": created_relations,
        "total_nodes": stats.get("total_nodes", 0),
        "total_relations": stats.get("total_relations", 0),
    }
