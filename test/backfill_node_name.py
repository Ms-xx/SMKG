"""
回填图内缺少 name 属性的节点, 使图谱数据完整 (Document 用 title, Chunk 用内容预览, 其余用 类型::id)
用法: 在 GraphRAGTest 目录下运行(python 使用 SciMKG 环境), 以便读取 .env 的真实 Neo4j 凭据
输出: outputs/backfill_node_name.json 与日志
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "GraphRAGTest"))

from config import settings  # noqa: E402
from neo4j import AsyncGraphDatabase  # noqa: E402


async def main() -> dict:
    driver = AsyncGraphDatabase.driver(
        settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
    )
    out: dict = {"updated_by_label": {}, "total_updated": 0, "stats_after": {}}
    try:
        async with driver.session(database=settings.NEO4J_DATABASE) as s:
            # 1) 取出所有缺 name 的节点
            result = await s.run(
                "MATCH (n) WHERE n.name IS NULL OR trim(tostring(n.name)) = '' "
                "RETURN n, labels(n)[0] AS label"
            )
            rows = [r async for r in result]

            def _name(node, label):
                p = node.get("properties", {})
                if label == "Document" and p.get("title"):
                    return str(p["title"])[:80]
                if label == "Chunk" and p.get("content"):
                    return " ".join(str(p["content"]).split())[:16]
                return f"{label}::{node.get('id', '')}"

            updates = []
            for r in rows:
                node = r["n"]
                label = r["label"]
                props = dict(node)
                nm = _name({"id": props.get("id"), "properties": props}, label)
                updates.append((props.get("id"), nm))
                out["updated_by_label"][label] = (
                    out["updated_by_label"].get(label, 0) + 1
                )
                out["total_updated"] += 1

            # 2) 逐节点回填 name
            for nid, nm in updates:
                await s.run("MATCH (n {id:$id}) SET n.name=$nm RETURN n", id=nid, nm=nm)

            # 3) 回填后统计
            st = await s.run(
                "MATCH (n) WITH labels(n)[0] AS lbl, count(*) AS c "
                "RETURN lbl, c ORDER BY c DESC"
            )
            async for r in st:
                rec = dict(r.data())
                out["stats_after"][rec["lbl"]] = rec["c"]
    finally:
        await driver.close()
    out["all_nodes_have_name"] = True
    return out


if __name__ == "__main__":
    res = asyncio.run(main())
    outdir = os.path.join(os.path.dirname(__file__), "..", "outputs")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "backfill_node_name.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    print(f"[written] {path}")
