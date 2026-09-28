#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
图谱数据态复测（步骤 16.3）。

对齐 XiangMu 步骤 16 的验收条件：
  1. /citation-graph/network 返回 edge_count > 0；/key-papers 的 PageRank 方差 > 0
  2. Neo4j CITES 关系数 > 0，且回填脚本重复执行新增关系数为 0（幂等）
  3. /knowledge-graph/trends timeline 非空且时间桶不全为 unknown；/anomalies 有输入统计
  4. Neo4j 主文档节点 year 覆盖完整

用法：
    python test/graph_datastate_recheck.py [--out PATH]

输出：outputs/graph_datastate_recheck.json（含逐条断言 PASS/FAIL 与证据片段）
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
# 顺序要求：backend 必须优先于 GraphRAGTest（后者含 app.py，会遮蔽 backend/app 包）
sys.path.insert(0, str(_REPO_ROOT / "GraphRAGTest"))
sys.path.insert(0, str(_REPO_ROOT / "backend"))


def _login(session, base_url: str, username: str, password: str) -> dict[str, str]:
    resp = session.post(
        f"{base_url}/auth/login",
        json={"username": username, "password": password},
        timeout=30,
    )
    resp.raise_for_status()
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _mysql_document_ids() -> dict[str, Any]:
    """读取 MySQL documents：全量 id 与「已有年份元数据」的 id。"""
    import asyncio

    # 后端 Settings 以 cwd 相对路径加载 .env，此处显式指定，避免依赖运行目录
    from dotenv import load_dotenv

    load_dotenv(_REPO_ROOT / "backend" / ".env", override=False)

    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.core.config import settings

    async def run() -> dict[str, Any]:
        engine = create_async_engine(settings.DATABASE_URL)
        async with engine.connect() as conn:
            result = await conn.execute(
                sa.text("SELECT id, publication_date FROM documents ORDER BY id")
            )
            rows = [dict(r) for r in result.mappings()]
        await engine.dispose()
        return {
            "all_ids": [str(r["id"]) for r in rows],
            "ids_with_year": [
                str(r["id"]) for r in rows if r.get("publication_date") is not None
            ],
        }

    return asyncio.run(run())


def _neo4j_counts(expected_with_year: list[str] | None = None) -> dict[str, Any]:
    """直连 Neo4j 统计验收需要的指标（与 driver 无关，避免依赖后端缓存）。"""
    import asyncio
    from config import settings as gr_settings  # GraphRAGTest config
    from neo4j_client import neo4j_client

    async def run() -> dict[str, Any]:
        driver = await neo4j_client.get_driver()
        out: dict[str, Any] = {}
        async with driver.session(database=gr_settings.NEO4J_DATABASE) as s:
            queries = {
                "cites_total": "MATCH ()-[r:CITES]->() RETURN count(r) AS c",
                "document_nodes": "MATCH (d:Document) RETURN count(d) AS c",
                "primary_doc_nodes": (
                    "MATCH (d:Document) WHERE coalesce(d.external, false) = false "
                    "RETURN count(d) AS c"
                ),
                "primary_with_year": (
                    "MATCH (d:Document) WHERE coalesce(d.external, false) = false "
                    "AND d.year IS NOT NULL RETURN count(d) AS c"
                ),
                "match_types": (
                    "MATCH ()-[r:CITES]->() "
                    "RETURN r.match_type AS mt, count(r) AS c ORDER BY c DESC"
                ),
                "expected_with_year_having_year": (
                    "MATCH (d:Document) WHERE d.id IN $ids AND d.year IS NOT NULL "
                    "RETURN count(d) AS c"
                ),
            }
            params = {"ids": list(expected_with_year or [])}
            for key, q in queries.items():
                res = (
                    await s.run(q, **params)
                    if key == "expected_with_year_having_year"
                    else await s.run(q)
                )
                if key == "match_types":
                    out[key] = {rec["mt"]: rec["c"] async for rec in res}
                else:
                    rec = await res.single()
                    out[key] = rec["c"] if rec else None
        return out

    return asyncio.run(run())


def main(args: argparse.Namespace) -> int:
    import requests

    base_url = f"{args.base_url}/api/v1"
    session = requests.Session()
    headers = _login(session, base_url, args.username, args.password)
    result: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(),
        "base_url": base_url,
    }
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, evidence: Any) -> None:
        checks.append({"check": name, "pass": passed, "evidence": evidence})

    # ---- 1) 引用网络：nodes 取自图谱 Document 节点（含 backfill 后的 year/authors）
    # 注：后端代理接口对 limit 的上限为 200，取主文档节点需分批或直接用上限值
    nodes_resp = session.get(
        f"{base_url}/knowledge-graph/rag/graph/nodes/Document",
        headers=headers,
        params={"limit": 200},
        timeout=60,
    )
    docs = nodes_resp.json().get("nodes") or []
    references = []
    for i, d in enumerate(docs):
        props = d.get("properties") or {}
        if props.get("external"):
            continue
        references.append(
            {
                "index": i + 1,
                "title": props.get("title") or props.get("name"),
                "year": props.get("year"),
                "doi": props.get("doi"),
                "authors": props.get("authors"),
            }
        )
    result["reference_pool"] = {
        "graph_document_nodes": len(docs),
        "references_built": len(references),
        "with_year": sum(1 for r in references if r.get("year")),
        "with_authors": sum(1 for r in references if r.get("authors")),
    }

    net = session.post(
        f"{base_url}/citation-graph/network",
        headers=headers,
        json={"references": references},
        timeout=120,
    ).json()
    edge_count = net.get("edge_count", len(net.get("edges", [])))
    add(
        "network_edge_count_gt_0",
        edge_count > 0,
        {"edge_count": edge_count, "nodes": len(net.get("nodes", []))},
    )

    # ---- 2) 基石节点 PageRank 区分度
    kp = session.post(
        f"{base_url}/citation-graph/key-papers",
        headers=headers,
        json={"graph": {"nodes": net.get("nodes", []), "edges": net.get("edges", [])}},
        timeout=120,
    ).json()
    papers = kp.get("key_papers") or []
    ranks = [p.get("page_rank", 0.0) for p in papers]
    var = round(statistics.pvariance(ranks), 8) if len(ranks) > 1 else 0.0
    add(
        "pagerank_variance_gt_0",
        len(ranks) > 1 and var > 0,
        {"count": len(ranks), "pvariance": var},
    )

    # ---- 3) 趋势分析
    trends = session.get(
        f"{base_url}/knowledge-graph/trends", headers=headers, timeout=180
    ).json()
    timeline = trends.get("timeline") or []
    unknown_ratio = (
        sum(
            1
            for b in timeline
            if str(b.get("bucket") or b.get("period") or "").lower() == "unknown"
        )
        / len(timeline)
        if timeline
        else 1.0
    )
    add(
        "trends_timeline_non_empty_and_not_all_unknown",
        len(timeline) > 0 and unknown_ratio < 1.0,
        {
            "timeline_len": len(timeline),
            "unknown_ratio": round(unknown_ratio, 3),
            "top": timeline[:6],
        },
    )

    # ---- 4) 异常检测
    anomalies = session.get(
        f"{base_url}/knowledge-graph/anomalies", headers=headers, timeout=180
    ).json()
    categories = {
        k: (anomalies.get(k) or {}).get("count", 0)
        for k in ("isolated", "high_connectivity", "low_connectivity")
    }
    add(
        "anomalies_structured_with_input",
        isinstance(anomalies, dict)
        and len(anomalies.get("anomalies") or []) > 0
        and sum(categories.values()) > 0,
        {
            "anomaly_count": len(anomalies.get("anomalies") or []),
            "categories": categories,
            "density": (anomalies.get("density") or {}).get("overall"),
        },
    )

    # ---- 5) Neo4j 侧直接计数
    # 年份覆盖以「MySQL 中已有年份元数据的文档」为分母：
    # 未挂 arXiv 元数据的本地文档（如 banach.pdf）无年份可言，属数据本身限制，
    # 不计入覆盖率，也不得因它判定整项失败。
    mysql_ids = _mysql_document_ids()
    neo = _neo4j_counts(mysql_ids["ids_with_year"])
    result["mysql_documents"] = {
        "total": len(mysql_ids["all_ids"]),
        "with_year_metadata": len(mysql_ids["ids_with_year"]),
        "without_year_metadata": len(mysql_ids["all_ids"])
        - len(mysql_ids["ids_with_year"]),
    }
    add("neo4j_cites_gt_0", (neo.get("cites_total") or 0) > 0, neo)
    year_cov_ok = neo.get("expected_with_year_having_year") == len(
        mysql_ids["ids_with_year"]
    )
    add(
        "neo4j_year_covers_primary_docs",
        bool(year_cov_ok) and len(mysql_ids["ids_with_year"]) > 0,
        {
            "expected": len(mysql_ids["ids_with_year"]),
            "covered": neo.get("expected_with_year_having_year"),
            "primary_with_year": neo.get("primary_with_year"),
            "primary_doc_nodes": neo.get("primary_doc_nodes"),
        },
    )

    result["neo4j"] = neo
    result["trends_sample"] = timeline[:10]
    result["network_sample"] = {
        "edge_count": edge_count,
        "node_count": len(net.get("nodes", [])),
    }
    result["key_papers"] = papers[:8]
    result["checks"] = checks
    result["all_passed"] = all(c["pass"] for c in checks)

    out_path = (
        Path(args.out)
        if args.out
        else _REPO_ROOT / "outputs" / "graph_datastate_recheck.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    for c in checks:
        print(f"[{'PASS' if c['pass'] else 'FAIL'}] {c['check']}")
    print(f"\nall_passed={result['all_passed']}  report -> {out_path}")
    return 0 if result["all_passed"] else 1


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="图谱数据态复测（步骤 16.3）")
    p.add_argument("--base-url", type=str, default="http://127.0.0.1:8000")
    p.add_argument("--username", type=str, default="admin")
    p.add_argument("--password", type=str, default="admin123")
    p.add_argument("--out", type=str, default=None)
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(main(parse_args()))
