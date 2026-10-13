# -*- coding: utf-8 -*-
"""核对 innovA 写入 Neo4j 的实体节点（按类型计数）与连通性后关闭。"""
from __future__ import annotations
import sys, os, asyncio, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
from app.utils.neo4j_client import Neo4jClient

async def main():
    client = Neo4jClient()
    q = ("MATCH (n) WHERE n.source IS NULL OR n.source='innovA' "
         "WITH n RETURN labels(n)[0] AS label, collect(n.name) AS names")
    rows = await client.execute_query(q)
    by_type: dict = {}
    total = 0
    for r in rows:
        lab = r.get("label")
        names = r.get("names") or []
        if lab not in ("MATERIAL", "METHOD", "METRIC", "TASK", "OTHERSCIENTIFICTERM"):
            continue
        by_type.setdefault(lab, []).extend(names)
        total += len(names)
    await client.close()
    print(json.dumps({"total": total, "by_type": {k: v for k, v in by_type.items()}}, ensure_ascii=False, indent=2))

asyncio.run(main())