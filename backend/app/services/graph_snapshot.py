"""全图快照纯函数模块：导出载荷归一化与缓存键构造（零副作用，可纯函数单测）。"""

from typing import Any, NamedTuple


class GraphSnapshot(NamedTuple):
    """归一化后的全图快照（节点 + 关系）。"""

    nodes: list[dict[str, Any]]
    relations: list[dict[str, Any]]


def _normalize_node(nd: dict[str, Any], fallback_label: str | None = None) -> dict[str, Any]:
    """单个节点归一化：id 优先 properties.id 回退 nd.id；label 优先 nd.label 回退查询所用 label。"""
    props = nd.get("properties") or {}
    node_id = props.get("id") or nd.get("id")
    label = nd.get("label") or fallback_label
    return {"id": node_id, "label": label, "properties": props}


def _normalize_relation(rel: dict[str, Any], fallback_type: str | None = None) -> dict[str, Any]:
    """单个关系归一化：端点 dict 取 id、标量原样；type 优先 relation 回退 type 再回退 rel_type。"""
    source = rel.get("source")
    target = rel.get("target")
    source_id = source.get("id") if isinstance(source, dict) else source
    target_id = target.get("id") if isinstance(target, dict) else target
    rel_type = rel.get("relation") or rel.get("type") or rel.get("rel_type") or fallback_type
    return {"source": source_id, "target": target_id, "type": rel_type}


def normalize_export_payload(payload: dict[str, Any]) -> GraphSnapshot:
    """将下游 /graph/export 载荷归一化为 GraphSnapshot。

    归一化规则与 graph_insights._load_full_graph() 逐条等价：
    - Node.id 优先 properties.id 回退 nd.id
    - Node.label 优先 nd.label 回退查询所用 label（导出载荷中节点自带 label）
    - Relation.source/target 端点 dict 取 id、标量原样
    - Relation.type 优先 relation 回退 type 再回退 rel_type
    - 空载荷或下游错误 → ([], [])
    """
    if not isinstance(payload, dict) or "error" in payload:
        return GraphSnapshot(nodes=[], relations=[])

    raw_nodes = payload.get("nodes") or []
    raw_relations = payload.get("relations") or []

    nodes: list[dict[str, Any]] = []
    for nd in raw_nodes:
        if not isinstance(nd, dict):
            continue
        nodes.append(_normalize_node(nd, fallback_label=nd.get("label")))

    relations: list[dict[str, Any]] = []
    for rel in raw_relations:
        if not isinstance(rel, dict):
            continue
        relations.append(_normalize_relation(rel))

    return GraphSnapshot(nodes=nodes, relations=relations)


def snapshot_cache_key() -> str:
    """全图快照缓存键：平台级共享、不含用户身份、版本稳定。"""
    return "kg:graph-snapshot:v1"


def is_empty_snapshot(snapshot: GraphSnapshot) -> bool:
    """判断快照是否为空（节点与关系均无）。"""
    return not snapshot.nodes and not snapshot.relations
