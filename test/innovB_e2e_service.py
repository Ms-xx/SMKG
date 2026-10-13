# -*- coding: utf-8 -*-
"""
创新点 B 端到端实测（走真实 /api/v1 服务 8001）：
  索引一篇含实体/关系/chunk 的中文材料文档 → 提问 → 校验返回的 grounding_score 与 rerank。
需 GraphRAGTest 已启动（8001）且 Neo4j 已连接；LM Studio 缺失时 LLM 降级为规则，不影响验证。

用法（SciMKG）:
    python innovB_e2e_service.py
输出: outputs/innovB_e2e_service.json
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
API = "http://localhost:8001/api/v1"

DOC_ID = "innovB-demo-doc"


def _post(path: str, payload: dict):
    req = urllib.request.Request(
        API + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(path: str):
    with urllib.request.urlopen(API + path, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    # 0. 健康
    health = _get("/health")

    # 1. 索引一篇中文材料文档（实体/关系/chunk）
    idx = _post(
        "/index/document",
        {
            "doc_id": DOC_ID,
            "doc_title": "钙钛矿太阳能电池材料研究",
            "entities": [
                {"text": "钙钛矿", "entity_type": "Material"},
                {"text": "光电转换效率", "entity_type": "Property"},
                {"text": "太阳能电池", "entity_type": "Device"},
            ],
            "relations": [
                {
                    "source": "钙钛矿",
                    "source_type": "Material",
                    "target": "光电转换效率",
                    "target_type": "Property",
                    "relation_type": "HAS_PROPERTY",
                    "context": "钙钛矿材料具有较高的光电转换效率。",
                },
                {
                    "source": "钙钛矿",
                    "source_type": "Material",
                    "target": "太阳能电池",
                    "target_type": "Device",
                    "relation_type": "USED_IN",
                    "context": "钙钛矿被用于制备高性能太阳能电池。",
                },
            ],
            "metadata": {"year": 2024, "venue": "Advanced Materials"},
            "chunks": [
                "钙钛矿材料具有较高的光电转换效率，被广泛用于太阳能电池研究。",
                "研究人员通过优化工艺显著提升了钙钛矿太阳能电池的光电转换效率。",
            ],
        },
    )

    # 2. 提问（返回 grounding + rerank）
    q = _post(
        "/query",
        {
            "question": "钙钛矿太阳能电池的光电转换效率如何？",
            "return_context": True,
            "include_sources": True,
        },
    )

    g = q.get("grounding", {})
    rerank = (q.get("context", {}) or {}).get("rerank", {})

    result = {
        "health": health,
        "index": idx,
        "query": {
            "question": q.get("question"),
            "answer": q.get("answer"),
            "keywords": q.get("keywords"),
        },
        "grounding": {
            "enabled": g.get("enabled"),
            "score": g.get("score"),
            "supported_count": g.get("supported_count"),
            "total_tokens": g.get("total_tokens"),
            "evidence_sources": g.get("evidence_sources"),
            "evidence_nodes": g.get("evidence_nodes"),
        },
        "rerank": {
            "enabled": rerank.get("enabled"),
            "depth": rerank.get("depth"),
            "applied": rerank.get("applied"),
        },
        "sources_count": len(q.get("sources", []) or []),
        "context_nodes": len((q.get("context", {}) or {}).get("nodes", []) or []),
        "context_relations": len(
            (q.get("context", {}) or {}).get("relations", []) or []
        ),
    }

    # 3. 判定：有了证据后 iOS 支撑分应为非0（若 LLM 正常更能拿到高值）
    grounding_ok = g.get("enabled") is True and isinstance(g.get("score"), float)
    rerank_ok = isinstance(rerank, dict) and rerank.get("enabled") is True

    result["pass"] = grounding_ok and rerank_ok
    result["note"] = (
        "grounding_score 已随 /query 返回；LLM 在线时 score 更高，离线仅验证输出结构与降级路径。"
    )

    out_path = os.path.join(BASE_DIR, "outputs", "innovB_e2e_service.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("PASS" if result["pass"] else "FAIL")
    sys.exit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
