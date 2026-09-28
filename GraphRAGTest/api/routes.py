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
    # 上限与 /graph/relations/type 对齐（5000）：后端全图拉取（trends / anomalies）
    # 需要一次性取完某标签的全部节点，原先 le=200 会导致超限后请求被拒。
    limit: int = Query(50, ge=1, le=5000),
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
    limit: int = Query(20, ge=1, le=5000),
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




