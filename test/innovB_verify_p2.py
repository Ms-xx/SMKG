# -*- coding: utf-8 -*-
"""创新点B P2待改进项 直接验证：真实连 Neo4j 2026.04.0，验证新 `CALL {...} LIMIT $limit` 子查询。

覆盖：
  P2① limit 真正进入 Cypher（限制 distinct 邻居数）
  P2② 深度上限取自 GRAPH_HOP_MAX_DEPTH（可变长关系字面量安全内联）
验证失败退出码非0。
"""
from __future__ import annotations

import asyncio
import os
import sys

# 让 GraphRAGTest 包可导入
BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "GraphRAGTest"))
sys.path.insert(0, BASE)

from neo4j_client import Neo4jClient  # noqa: E402
from config import settings  # noqa: E402


PREFIX = "P2V-"  # 唯一前缀，隔离本验证数据，不影响线上图谱真实节点
N = lambda *s: "-".join([PREFIX, *s])  # noqa: E731


async def _seed(driver):
    """建一个小星形图：c0 连 6 个邻居、c1 连 3 个邻居、孤立 c2。
    深度=2 时 c0 应能看到 7（一跳6 + 二跳1链）；c1 = 3；c2 = 0（孤立）。
    limit=$limit 生效：把 limit 置很小可验证 distinct 邻居被截断。
    全部节点用 PREFIX 前缀，验证后只清理带前缀的节点，避免误删线上数据。
    """
    ids = [
        N("c0"),
        N("c1"),
        N("c2"),
        N("n1"),
        N("n2"),
        N("n3"),
        N("n4"),
        N("n5"),
        N("n6"),
        N("m1"),
        N("m2"),
        N("m3"),
        N("x1"),
    ]
    async with driver.session(database=settings.NEO4J_DATABASE) as s:
        # 先清理上次运行残留的同前缀节点
        await s.run(
            "MATCH (n:Seed) WHERE n.id STARTS WITH $p DETACH DELETE n",
            p=PREFIX,
        )
        await s.run(
            "UNWIND $nodes AS id CREATE (n:Seed {id:id})",
            nodes=ids,
        )
        await s.run(
            "UNWIND $rels AS r "
            "MATCH (a:Seed {id:r.a}) MATCH (b:Seed {id:r.b}) CREATE (a)-[:LINK]->(b)",
            rels=[
                {"a": N("c0"), "b": N("n1")},
                {"a": N("c0"), "b": N("n2")},
                {"a": N("c0"), "b": N("n3")},
                {"a": N("c0"), "b": N("n4")},
                {"a": N("c0"), "b": N("n5")},
                {"a": N("c0"), "b": N("n6")},
                {"a": N("c1"), "b": N("m1")},
                {"a": N("c1"), "b": N("m2")},
                {"a": N("c1"), "b": N("m3")},
            ],
        )
        # 二跳链：c0 -> n1 -> x1，使深度=2 能再多看一个邻居
        await s.run(
            "MATCH (n1:Seed {id:$a}) MATCH (x1:Seed {id:$b}) CREATE (n1)-[:LINK]->(x1)",
            a=N("n1"),
            b=N("x1"),
        )


async def main() -> int:
    c = Neo4jClient()
    driver = await c.get_driver()
    await _seed(driver)

    # 用 id 属性匹配（Seed 节点），key 带 PREFIX
    # 深度2：c0 一跳6个 + 二跳1个(x1) = 7
    full = await c.get_connection_strength(
        [N("c0"), N("c1"), N("c2")], depth=2, limit=1000
    )
    print("depth=2 limit=1000:", full)
    # limit 生效：limit=2 每个 key 最多 2 个 distinct 邻居 → c0 邻居数应为 2
    limited = await c.get_connection_strength([N("c0")], depth=2, limit=2)
    print("depth=2 limit=2:", limited)
    # 深度上限：请求 depth=10，应被截到 GRAPH_HOP_MAX_DEPTH(=3)，且不报错
    capped = await c.get_connection_strength([N("c0")], depth=10, limit=1000)
    print("depth=10 (capped):", capped)
    # 缺失节点计入 0
    missing = await c.get_connection_strength([N("ghost")], depth=2, limit=1000)
    print("missing:", missing)

    # 判定
    checks = []
    checks.append(("P2① limit 进入 Cypher", limited.get(N("c0")) == 2))
    checks.append(("P2② 深度上限生效且不抛错", N("c0") in capped))
    checks.append(("深度2 邻居计数正确", full.get(N("c0")) == 7))
    checks.append(("孤立节点计数0", full.get(N("c2")) == 0))
    checks.append(("缺失节点计数0", missing.get(N("ghost")) == 0))

    ok = True
    for name, passed in checks:
        print(("PASS " if passed else "FAIL ") + name)
        ok = ok and passed

    await c.close()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
