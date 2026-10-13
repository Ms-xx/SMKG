# -*- coding: utf-8 -*-
"""
创新点 D 校验：多智能体图谱融合（多 agent 抽取 → 冲突消解 → 实体/关系写回 Neo4j）。

覆盖：
- 纯函数：_entities_to_graph_format / _build_relations_from_cooccurrence（句内共现建关系）
- 降级：开关关闭不落图谱；图不可用捕获异常降级不阻断主流程（mock）
- 链路：multi_agent_service.run() 返回 graph_fusion 字段，写回为 True（mock index_document）
- 实测（可选）：若 GraphRAGTest 8001 在线则真实写回，否则跳过

用法（SciMKG）:
    python innovD_multi_agent_graph_fusion.py
输出: outputs/innovD_multi_agent_graph_fusion.json
"""
from __future__ import annotations

import json
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE_DIR, "backend"))

from loguru import logger  # noqa: E402

import app.services.multi_agent_service as mas  # noqa: E402
import app.services.graphrag_integration as gi  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.services.multi_agent_service import (  # noqa: E402
    _build_relations_from_cooccurrence,
    _entities_to_graph_format,
    multi_agent_service,
)

# 保存原类便于恢复
_ORIG_INTEG = gi.GraphRAGIntegration


def test_pure_builders() -> dict:
    items = [
        {"text": "钙钛矿", "type": "Material"},
        {"text": "高效率", "type": "Property"},
        {"text": "石墨烯", "type": "Material"},
    ]
    ents = _entities_to_graph_format(items)
    assert ents == [
        {"text": "钙钛矿", "entity_type": "Material"},
        {"text": "高效率", "entity_type": "Property"},
        {"text": "石墨烯", "entity_type": "Material"},
    ], ents

    text = "钙钛矿具有高效率。石墨烯用于钙钛矿器件制备。"
    rels = _build_relations_from_cooccurrence(items, text, "CO_OCCURS")
    # 句1命中钙钛矿+高效率 → 1 条；句2命中石墨烯+钙钛矿 → 1 条；共 2 条
    assert len(rels) == 2, rels
    keys = {(r["source"], r["target"]) for r in rels}
    assert ("钙钛矿", "高效率") in keys
    assert ("钙钛矿", "石墨烯") in keys
    assert all(r["relation_type"] == "CO_OCCURS" for r in rels)

    # 空实体 → 空关系
    assert _build_relations_from_cooccurrence([], text, "CO_OCCURS") == []
    return {"entities": ents, "relations": rels}


def test_fusion_degraded_disabled() -> dict:
    settings.MULTI_AGENT_GRAPH_FUSION_ENABLED = False
    r = multi_agent_service.fuse_to_graph("d1", "主题", [], "")
    assert r["graph_written"] is False and r["reason"] == "disabled", r

    settings.MULTI_AGENT_GRAPH_FUSION_ENABLED = True
    r2 = multi_agent_service.fuse_to_graph("d1", "主题", [], "正文")
    assert r2["graph_written"] is False and r2["reason"] == "no_entities", r2
    return {"disabled": r, "no_entities": r2}


def test_fusion_degraded_graph_unavailable() -> dict:
    """mock 使 index_document 抛异常 → 降级为 graph_written=False 且不阻断。"""
    orig = multi_agent_service.fuse_to_graph.__globals__

    class BoomInteg:
        def index_document(self, *a, **k):
            raise ConnectionError("Neo4j 未连接")

    gi.GraphRAGIntegration = BoomInteg
    try:
        r = multi_agent_service.fuse_to_graph("d2", "主题", [{"text": "钙钛矿", "type": "Material"}], "钙钛矿应用")
    finally:
        gi.GraphRAGIntegration = _ORIG_INTEG
    assert r["graph_written"] is False and r["reason"] == "exception", r
    assert r["entities"] == 1
    return r


def test_run_fusion_mocked_write() -> dict:
    """mock 使 index_document 返回成功 → run() 返回 graph_fusion.graph_written=True。"""
    captured = {}

    def fake_index_document(**kwargs):
        captured.update(kwargs)
        return {
            "doc_id": kwargs["doc_id"],
            "entities_imported": len(kwargs["entities"]),
            "relations_imported": len(kwargs["relations"]),
            "doc_entity_links": len(kwargs["entities"]),
            "chunks_imported": 1 if kwargs["chunks"] else 0,
            "entities_vectorized": 0,
            "relations_vectorized": 0,
            "chunks_vectorized": 0,
            "errors": [],
        }

    class OkInteg:
        def index_document(self, **kwargs):
            return fake_index_document(**kwargs)

    gi.GraphRAGIntegration = OkInteg
    try:
        session = multi_agent_service.run(
            query="钙钛矿光伏材料效率",
            context="钙钛矿具有高光电转换效率。稳定钙钛矿适合太阳能电池。",
            agents=["extract", "summarize"],
            mode="merge",
        )
    finally:
        gi.GraphRAGIntegration = _ORIG_INTEG

    gf = session.get("graph_fusion", {})
    assert gf.get("graph_written") is True, gf
    assert gf.get("doc_id") == f"session:{session['session_id']}"
    assert gf.get("entities", 0) >= 1
    # 写入的实体应来自消解后的 final_items
    assert captured.get("entities"), "index_document 收到空实体"
    return {"session_id": session["session_id"], "graph_fusion": gf, "final_items": session["resolution"]["final_items"]}


def _graph_stats() -> dict | None:
    """查询 GraphRAGTest 的 /graph/stats，返回节点/关系统计（不可用时返回 None）。"""
    import httpx

    try:
        r = httpx.get("http://localhost:8001/api/v1/graph/stats", timeout=3)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


def real_e2e() -> dict:
    """GraphRAGTest 8001 在线则真实写回，否则跳过；并核对 /graph/stats 落库计数。"""
    import httpx

    try:
        h = httpx.get("http://localhost:8001/api/v1/health", timeout=2)
        if h.status_code != 200:
            return {"skipped": "graphragtest-offline", "note": "未启动 8001，跳过真实写回"}
    except Exception as exc:
        return {"skipped": "graphragtest-offline", "note": str(exc)}

    before = _graph_stats() or {}

    session = multi_agent_service.run(
        query="钙钛矿太阳能电池",
        context="钙钛矿具有高光电转换效率。稳定钙钛矿应用于太阳能电池器件。石墨烯增益传输层性能。",
        agents=["extract", "summarize"],
        mode="merge",
    )
    gf = session.get("graph_fusion", {})
    after = _graph_stats() or {}

    # /graph/stats 落库核对：新增 Document 节点、且 relation_types 含 HAS_ENTITY / CO_OCCURS。
    # 计数跨次累计、不写死 3/1，仅校验确实写入（graph_written 且 stats 可见关系类型）。
    node_labels = after.get("node_labels") or {}
    rels = after.get("relation_types") or {}
    imported = {
        "graph_stats_written": gf.get("graph_written") is True,
        "document_node_count": node_labels.get("Document", 0),
        "has_entity_count": rels.get("HAS_ENTITY", 0),
        "co_occurs_count": rels.get("CO_OCCURS", 0),
        "before": before,
        "after": after,
    }
    # 真实环境下仍可能因 Neo4j 未连接而降级；此处只上报结果不强制断言
    return {"graph_fusion": gf, "final_items": session["resolution"]["final_items"], **imported}


def main() -> None:
    results = {
        "innovD": "multi_agent_graph_fusion",
        "enabled": settings.MULTI_AGENT_GRAPH_FUSION_ENABLED,
        "rel_type_default": settings.MULTI_AGENT_FUSION_REL_TYPE_DEFAULT,
        "pure_builders": test_pure_builders(),
        "fusion_degraded_disabled": test_fusion_degraded_disabled(),
        "fusion_degraded_graph_unavailable": test_fusion_degraded_graph_unavailable(),
        "run_mocked_write": test_run_fusion_mocked_write(),
        "real_e2e": real_e2e(),
    }
    out = os.path.join(BASE_DIR, "outputs", "innovD_multi_agent_graph_fusion.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    logger.info(f"结果已写入 {out}")


if __name__ == "__main__":
    main()