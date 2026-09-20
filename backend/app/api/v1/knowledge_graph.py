from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.security import get_current_user
from app.services.entity_linking_service import entity_linking_service
from app.services.graph_service import GraphService
from app.services.graphrag_integration import graphrag_integration
from app.services.relation_inference_service import relation_inference_service
from app.services.semantic_search_service import semantic_search_service
from app.services.text_to_cypher_service import text_to_cypher_service

router = APIRouter()
graph_service = GraphService()


class CypherQuery(BaseModel):
    cypher: str
    params: Optional[dict] = {}


class RAGQueryRequest(BaseModel):
    question: str
    return_context: bool = False


class DocumentIndexRequest(BaseModel):
    doc_id: str
    doc_title: str
    entities: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {}
    chunks: list[str] = []


class NodeCreateRequest(BaseModel):
    label: str
    id: str
    properties: dict[str, Any] = {}


class RelationCreateRequest(BaseModel):
    source_label: str
    source_id: str
    target_label: str
    target_id: str
    rel_type: str
    properties: dict[str, Any] = {}


class EntityLinkRequest(BaseModel):
    entities: list[dict[str, Any]] = []


class EntityLinkSingleRequest(BaseModel):
    text: str
    entity_type: Optional[str] = None


class RelationInferenceRequest(BaseModel):
    triples: list[dict[str, Any]] = []


class LinkPredictionRequest(BaseModel):
    head: str
    relation: str
    triples: list[dict[str, Any]] = []
    top_k: int = 10


class TripleScoreRequest(BaseModel):
    head: str
    relation: str
    tail: str
    triples: list[dict[str, Any]] = []


class SuggestRequest(BaseModel):
    prefix: str
    candidates: list[str] = []
    limit: int = 10


class FacetSearchRequest(BaseModel):
    query: str = ""
    records: list[dict[str, Any]] = []
    facet_key: str = "label"
    limit: int = 20


class TextToCypherRequest(BaseModel):
    question: str
    node_labels: list[str] = []
    relation_types: list[str] = []
    limit: int = 20
    execute: bool = False


@router.get("/search")
async def search_graph(
    query: str,
    entity_type: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    results = await graph_service.search(query, entity_type, limit)
    return {"entities": results, "total": len(results)}


@router.get("/entities/{entity_id}")
async def get_entity(
    entity_id: str,
    current_user: dict = Depends(get_current_user),
):
    entity = await graph_service.get_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.get("/entities/{entity_id}/relations")
async def get_entity_relations(
    entity_id: str,
    depth: int = Query(1, ge=1, le=3),
    current_user: dict = Depends(get_current_user),
):
    results = await graph_service.get_entity_relations(entity_id, depth)
    return results


@router.post("/query")
async def execute_cypher(
    query: CypherQuery,
    current_user: dict = Depends(get_current_user),
):
    results = await graph_service.execute_cypher(query.cypher, query.params)
    return results


@router.get("/statistics")
async def get_graph_statistics(
    current_user: dict = Depends(get_current_user),
):
    return await graph_service.get_statistics()


@router.post("/entity-link")
async def link_entities(
    body: EntityLinkRequest,
    current_user: dict = Depends(get_current_user),
):
    """实体链接：接入 Wikidata/DBpedia，实体消歧与同义词合并。"""
    results = entity_linking_service.link_entities(body.entities)
    return {"results": results, "total": len(results)}


@router.post("/entity-link/single")
async def link_single_entity(
    body: EntityLinkSingleRequest,
    current_user: dict = Depends(get_current_user),
):
    """链接单个实体。"""
    result = entity_linking_service.link_entity(body.text, body.entity_type)
    if result is None:
        raise HTTPException(status_code=404, detail="无法链接该实体")
    return result


@router.post("/reason")
async def relation_reason(
    body: RelationInferenceRequest,
    current_user: dict = Depends(get_current_user),
):
    """关系推理：基于组合/逆关系/传递规则从三元组推导新关系。"""
    inferred = relation_inference_service.reason(body.triples)
    return {"inferred": inferred, "total": len(inferred)}


@router.post("/link-prediction")
async def link_prediction(
    body: LinkPredictionRequest,
    current_user: dict = Depends(get_current_user),
):
    """图谱补全 / 链路预测：给定头实体与关系，预测最可能的尾实体（TransE，可降级）。"""
    return relation_inference_service.predict_links(
        body.head, body.relation, body.triples, body.top_k
    )


@router.post("/triple-score")
async def triple_score(
    body: TripleScoreRequest,
    current_user: dict = Depends(get_current_user),
):
    """对候选三元组打分，用于图谱补全缺失边判定。"""
    score = relation_inference_service.score_triple(
        body.head, body.relation, body.tail, body.triples
    )
    return {"head": body.head, "relation": body.relation, "tail": body.tail, "score": score}


@router.post("/suggest")
async def search_suggest(
    body: SuggestRequest,
    current_user: dict = Depends(get_current_user),
):
    """语义搜索：搜索建议（前缀/子串/编辑距离自动补全）。"""
    return semantic_search_service.suggest(body.prefix, body.candidates, body.limit)


@router.post("/facet-search")
async def facet_search(
    body: FacetSearchRequest,
    current_user: dict = Depends(get_current_user),
):
    """语义搜索：分面搜索（关键字打分 + 按 facet_key 面计数）。"""
    return semantic_search_service.search(body.query, body.records, body.facet_key, body.limit)


@router.post("/text-to-cypher")
async def text_to_cypher(
    body: TextToCypherRequest,
    current_user: dict = Depends(get_current_user),
):
    """Text-to-Cypher：自然语言 → 只读 Cypher 查询（规则模板，LLM 预留可降级）。"""
    result = text_to_cypher_service.translate(
        body.question, body.node_labels, body.relation_types, body.limit
    )
    if result["cypher"]:
        ok, msg = text_to_cypher_service.validate(result["cypher"])
        if not ok:
            raise HTTPException(status_code=400, detail=msg)
        if body.execute:
            result["results"] = await graph_service.execute_cypher(
                result["cypher"], result["params"]
            )
    return result


# ─────────── GraphRAG 集成接口 ───────────


@router.get("/rag/health")
async def rag_health(
    current_user: dict = Depends(get_current_user),
):
    """GraphRAGTest 服务健康状态"""
    return graphrag_integration.health_check()


@router.get("/rag/llm/status")
async def rag_llm_status(
    current_user: dict = Depends(get_current_user),
):
    """LM Studio 当前状态"""
    return graphrag_integration.llm_status()


@router.get("/rag/llm/models")
async def rag_list_models(
    current_user: dict = Depends(get_current_user),
):
    """列出 LM Studio 可用模型"""
    return graphrag_integration.list_models()


@router.post("/rag/llm/load")
async def rag_load_model(
    model: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """让 LM Studio 预加载模型"""
    result = graphrag_integration.load_model(model)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.post("/rag/query")
async def rag_query(
    body: RAGQueryRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    GraphRAG 问答

    流程: 关键词提取 -> Neo4j 图谱检索 -> 组装上下文 -> Qwen 生成答案
    """
    result = graphrag_integration.rag_query(body.question, body.return_context)
    if "error" in result:
        raise HTTPException(status_code=502, detail=result)
    return result


@router.get("/rag/graph/stats")
async def rag_graph_stats(
    current_user: dict = Depends(get_current_user),
):
    """GraphRAG 图谱统计"""
    return graphrag_integration.graph_stats()


@router.get("/rag/graph/nodes/{label}")
async def rag_nodes_by_label(
    label: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    """按标签查询图谱节点"""
    return graphrag_integration.get_nodes_by_label(label, limit)


@router.get("/rag/graph/search/{keyword}")
async def rag_search_nodes(
    keyword: str,
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """按关键词搜索图谱节点"""
    return graphrag_integration.search_nodes(keyword, limit)


@router.get("/rag/graph/relations/type/{rel_type}")
async def rag_get_relations_by_type(
    rel_type: str,
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """按类型查询图谱关系"""
    return graphrag_integration.get_relations_by_type(rel_type, limit)


@router.post("/rag/graph/nodes")
async def rag_add_node(
    body: NodeCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    """添加图谱节点"""
    result = graphrag_integration.add_node(body.label, body.id, body.properties)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.post("/rag/graph/relations")
async def rag_add_relation(
    body: RelationCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    """添加图谱关系"""
    result = graphrag_integration.add_relation(
        body.source_label,
        body.source_id,
        body.target_label,
        body.target_id,
        body.rel_type,
        body.properties,
    )
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.post("/rag/index/document")
async def rag_index_document(
    body: DocumentIndexRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    将文档的实体和关系索引到 GraphRAG 图谱

    通常在文档解析 + 信息抽取完成后调用,
    将 extraction 结果批量写入 Neo4j
    """
    result = graphrag_integration.index_document(
        doc_id=body.doc_id,
        doc_title=body.doc_title,
        entities=body.entities,
        relations=body.relations,
        metadata=body.metadata,
        chunks=body.chunks,
    )
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.delete("/rag/graph/clear")
async def rag_clear_graph(
    current_user: dict = Depends(get_current_user),
):
    """清空 GraphRAG 图谱 (危险操作)"""
    result = graphrag_integration.clear_graph()
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.post("/rag/graph/seed")
async def rag_seed_demo_data(
    current_user: dict = Depends(get_current_user),
):
    """
    初始化示例数据到 Neo4j 图谱

    包含钙钛矿太阳能电池领域的10个实体和10条关系
    """
    result = graphrag_integration.seed_demo_data()
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result
