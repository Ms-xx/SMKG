# -*- coding: utf-8 -*-
"""graph_snapshot 纯函数单测：归一化、缓存键、空判定（U-01~U-03，无 async 用例）。"""
from app.services.graph_snapshot import (
    GraphSnapshot,
    is_empty_snapshot,
    normalize_export_payload,
    snapshot_cache_key,
)


def test_u01_normalize_node_id_and_relation_endpoints():
    """U-01：节点 properties.id 优先/回退、关系端点 dict/标量、type 回退链、空载荷 → ([], [])。"""
    # 空载荷
    snap = normalize_export_payload({})
    assert snap == GraphSnapshot(nodes=[], relations=[])
    # 下游错误
    snap = normalize_export_payload({"error": "down"})
    assert snap == GraphSnapshot(nodes=[], relations=[])

    # 节点 id 优先 properties.id
    payload = {
        "nodes": [
            {"label": "Material", "properties": {"id": "p1", "year": 2019}},
            {"label": "Property", "properties": {}, "id": "fallback-id"},
        ],
        "relations": [],
    }
    snap = normalize_export_payload(payload)
    assert snap.nodes[0]["id"] == "p1"
    assert snap.nodes[0]["label"] == "Material"
    assert snap.nodes[0]["properties"]["year"] == 2019
    # properties.id 缺失时回退到节点自身 id
    assert snap.nodes[1]["id"] == "fallback-id"

    # 关系端点 dict/标量 + type 回退链
    payload = {
        "nodes": [],
        "relations": [
            {"source": {"id": "s1"}, "relation": "CITES", "target": {"id": "t1"}},
            {"source": "scalar_s", "type": "HAS_PROPERTY", "target": "scalar_t"},
            {"source": "s3", "rel_type": "RELATED", "target": "t3"},
        ],
    }
    snap = normalize_export_payload(payload)
    assert snap.relations[0] == {"source": "s1", "target": "t1", "type": "CITES"}
    assert snap.relations[1] == {
        "source": "scalar_s",
        "target": "scalar_t",
        "type": "HAS_PROPERTY",
    }
    assert snap.relations[2] == {"source": "s3", "target": "t3", "type": "RELATED"}


def test_u02_equivalent_to_legacy_aggregation_with_cites_and_year():
    """U-02：与既有 _load_full_graph 口径等价（含 CITES 边与 year 属性，红线步骤 16）。"""
    # 模拟下游 /graph/export 一次返回的载荷
    export_payload = {
        "total_nodes": 2,
        "total_relations": 1,
        "node_labels": {"Paper": 2},
        "relation_types": {"CITES": 1},
        "nodes": [
            {
                "label": "Paper",
                "properties": {"id": "p1920", "year": 1920, "title": "A"},
            },
            {
                "label": "Paper",
                "properties": {"id": "p1956", "year": 1956, "title": "B"},
            },
        ],
        "relations": [
            {
                "source": {"id": "p1956", "year": 1956},
                "relation": "CITES",
                "target": {"id": "p1920", "year": 1920},
                "properties": {},
            }
        ],
    }
    snap = normalize_export_payload(export_payload)

    # 模拟既有 _load_full_graph 按类别聚合的等价口径（纯函数模拟）
    legacy_nodes = []
    for nd in export_payload["nodes"]:
        node_id = (nd.get("properties") or {}).get("id") or nd.get("id")
        legacy_nodes.append(
            {
                "id": node_id,
                "label": nd.get("label"),
                "properties": nd.get("properties") or {},
            }
        )
    legacy_relations = []
    for rel in export_payload["relations"]:
        source = rel.get("source") or {}
        target = rel.get("target") or {}
        legacy_relations.append(
            {
                "source": source.get("id") if isinstance(source, dict) else source,
                "target": target.get("id") if isinstance(target, dict) else target,
                "type": rel.get("relation") or rel.get("type"),
            }
        )

    assert snap.nodes == legacy_nodes
    assert snap.relations == legacy_relations
    # 红线步骤 16：年份桶与 CITES 边完整呈现
    assert snap.nodes[0]["properties"]["year"] == 1920
    assert snap.nodes[1]["properties"]["year"] == 1956
    assert snap.relations[0]["type"] == "CITES"
    assert snap.relations[0]["source"] == "p1956"
    assert snap.relations[0]["target"] == "p1920"


def test_u03_cache_key_platform_shared_stable():
    """U-03：键含业务前缀、与用户身份无关、版本稳定。"""
    key = snapshot_cache_key()
    assert key.startswith("kg:")
    assert "user" not in key.lower()
    assert "v1" in key
    # 多次调用稳定
    assert snapshot_cache_key() == key


def test_is_empty_snapshot():
    """空快照判定。"""
    assert is_empty_snapshot(GraphSnapshot(nodes=[], relations=[])) is True
    assert is_empty_snapshot(GraphSnapshot(nodes=[{"id": "x"}], relations=[])) is False
    assert (
        is_empty_snapshot(GraphSnapshot(nodes=[], relations=[{"source": "a"}])) is False
    )
