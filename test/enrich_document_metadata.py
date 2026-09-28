# -*- coding: utf-8 -*-
"""
为已有知识图谱的 Document 节点补全元数据 (title/name/authors/year/doi)
来源 = 由文件名中的 arxiv id 对应到 arXiv 官方元数据
用法: 在 GraphRAGTest 目录运行 (读取 .env 真实 Neo4j 凭据)
输出: outputs/enrich_metadata.json
"""
import asyncio
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "GraphRAGTest"))
from config import settings  # noqa: E402
from neo4j import AsyncGraphDatabase  # noqa: E402

# arxiv id -> 真实元数据 (抓取自 arxiv.org/abs/)
ARXIV_META = {
    "1408.2982": {
        "title": "On the last question of Stefan Banach",
        "authors": ["Pasha Zusmanovich"],
        "year": 2014,
        "doi": "10.1016/j.exmath.2015.12.005",
    },
    "1804.07036": {
        "title": "Learning to Extract Coherent Summary via Deep Reinforcement Learning",
        "authors": ["Yuxiang Wu", "Baotian Hu"],
        "year": 2018,
        "doi": "10.48550/arXiv.1804.07036",
    },
    "1701.04715": {
        "title": "Geometric algebra and an acoustic space time for propagation in non-uniform flow",
        "authors": [
            "Alastair Gregory",
            "Anurag Agarwal",
            "Joan Lasenby",
            "Samuel Sinayoko",
        ],
        "year": 2017,
        "doi": "10.48550/arXiv.1701.04715",
    },
}


async def main() -> dict:
    driver = AsyncGraphDatabase.driver(
        settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
    )
    out = {"enriched": [], "total": 0}
    try:
        async with driver.session(database=settings.NEO4J_DATABASE) as s:
            result = await s.run(
                "MATCH (n:Document) RETURN n.id AS id, n.title AS title, n.name AS name"
            )
            nodes = [dict(r) async for r in result]
            for n in nodes:
                text = f"{n.get('title') or n.get('name') or ''} {n.get('id') or ''}"
                m = re.search(r"(\d{4}\.\d{4,5})", text)
                if m and m.group(1) in ARXIV_META:
                    meta = ARXIV_META[m.group(1)]
                    await s.run(
                        "MATCH (n:Document {id:$id}) SET n.title=$title, n.name=$title, "
                        "n.authors=$authors, n.year=$year, n.doi=$doi RETURN n",
                        id=n["id"],
                        title=meta["title"][:80],
                        authors=meta["authors"],
                        year=meta["year"],
                        doi=meta["doi"],
                    )
                    out["enriched"].append({"id": n["id"], "arxiv": m.group(1), **meta})
                    out["total"] += 1
    finally:
        await driver.close()
    return out


if __name__ == "__main__":
    res = asyncio.run(main())
    outdir = os.path.join(os.path.dirname(__file__), "..", "outputs")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "enrich_metadata.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    print(f"[written] {path}")
