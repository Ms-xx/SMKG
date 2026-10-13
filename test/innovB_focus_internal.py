# -*- coding: utf-8 -*-
"""
创新点 B 内部快速校验：grounding_score 计算 + 图邻居扩跳重排序可用性。
直接从 GraphRAGTest 服务模块导入，避免依赖 LM Studio / 8001 常驻，仅需本机 Neo4j 连通。

用法（SciMKG）:
    python innovB_focus_internal.py
输出: outputs/innovB_focus_internal.json
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE_DIR, "GraphRAGTest"))

from loguru import logger  # noqa: E402

from graphrag_service import GraphRAGService  # noqa: E402
from config import settings  # noqa: E402

svc = GraphRAGService()


def check_grounding() -> dict:
    """答案多数 token 应被证据支撑 → score 较高；完全无关时→低分。"""
    context = {
        "nodes": [
            {"label": "Material", "properties": {"name": "钙钛矿", "id": "perovskite"}},
            {
                "label": "Property",
                "properties": {"name": "高光电转换效率", "id": "eff"},
            },
        ],
        "relations": [
            {
                "source": {"name": "钙钛矿", "id": "perovskite"},
                "target": {"name": "高光电转换效率", "id": "eff"},
                "relation": "HAS_PROPERTY",
                "properties": {"context": "钙钛矿太阳能电池具有高光电转换效率"},
            }
        ],
    }
    sources = [
        {
            "document_id": "doc1",
            "chunk_index": 0,
            "page_number": 1,
            "snippet": "钙钛矿太阳能电池具有较高的光电转换效率，适合低成本光伏。",
            "score": 0.95,
        }
    ]
    good = svc.compute_grounding_score(
        "钙钛矿太阳能电池具有较高的光电转换效率", context, sources
    )
    bad = svc.compute_grounding_score(
        "量子纠缠与量子计算的关系是什么", context, sources
    )
    disabled = None
    prev = settings.GROUNDING_ENABLED
    settings.GROUNDING_ENABLED = False
    disabled = svc.compute_grounding_score("任意答案", context, sources)
    settings.GROUNDING_ENABLED = prev
    return {
        "good_score": good["score"],
        "good_supported": good["supported_count"],
        "good_total": good["total_tokens"],
        "bad_score": bad["score"],
        "disabled": disabled["enabled"],
        "device_config": settings.GROUNDING_DEVICE,
    }


async def check_rerank() -> dict:
    """图谱不可用时降级原序；连通时正常返回（含 rerank 标记）。"""
    try:
        ctx = await svc.retrieve_context(["钙钛矿", "perovskite"])
        return {
            "rerank_enabled": ctx.get("rerank", {}).get("enabled"),
            "rerank_depth": ctx.get("rerank", {}).get("depth"),
            "rerank_applied": ctx.get("rerank", {}).get("applied"),
            "nodes": len(ctx.get("nodes", [])),
            "relations": len(ctx.get("relations", [])),
            "keyword_count": ctx.get("keyword_count"),
        }
    except Exception as e:  # 连不上 Neo4j 也返回，标记降级
        return {"rerank_error": str(e), "degraded": True}


async def main() -> None:
    grounding = check_grounding()
    rerank = await check_rerank()

    ok_good = grounding["good_score"] > 0.5
    ok_bad = grounding["bad_score"] <= grounding["good_score"]
    ok_disabled = grounding["disabled"] is False

    result = {
        "grounding": grounding,
        "grounding_pass": ok_good and ok_bad and ok_disabled,
        "rerank": rerank,
        "rerank_pass": rerank.get("rerank_enabled", False) is True,
        "switches": {
            "GRAPH_HOP_RERANK_ENABLED": settings.GRAPH_HOP_RERANK_ENABLED,
            "GROUNDING_ENABLED": settings.GROUNDING_ENABLED,
        },
    }
    out_path = os.path.join(BASE_DIR, "outputs", "innovB_focus_internal.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    all_ok = result["grounding_pass"]
    logger.info(f"grounding_pass={result['grounding_pass']} rerank={rerank}")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
