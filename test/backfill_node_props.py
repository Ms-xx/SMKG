#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
节点属性回填脚本（步骤 16.2.2）。

用法：
    python test/backfill_node_props.py [--dry-run] [--limit N] [--out PATH]

流程：
    1. 只读查询 MySQL documents 表（按 id 排序）；
    2. 逐条 extract_year(publication_date)；
    3. 调用 GraphRAGTest/neo4j_client.create_or_update_node（MERGE）写
       year/venue/authors/created_at；
    4. 输出汇总 JSON。

约束：
    - --dry-run 时禁止任何写调用，仅输出「将变更清单」；
    - Neo4j 不可达时非零退出并在输出给出连接错误，不静默成功。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# 路径准备：把 backend 与 GraphRAGTest 加入 sys.path
# 注意顺序：先插 GraphRAGTest、再插 backend，使 backend 位于 sys.path[0]。
# 否则 GraphRAGTest/app.py 会遮蔽 backend/app 包，导致
# "ModuleNotFoundError: No module named 'app.services'; 'app' is not a package"。
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "GraphRAGTest"))
sys.path.insert(0, str(_REPO_ROOT / "backend"))


async def _fetch_documents(limit: int | None) -> list[dict[str, Any]]:
    """只读查询 MySQL documents 表（按 id 排序）。"""
    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.core.config import settings

    engine = create_async_engine(settings.DATABASE_URL)
    rows: list[dict[str, Any]] = []
    sql = sa.text(
        "SELECT id, title, doi, authors, journal, publication_date, created_at "
        "FROM documents ORDER BY id"
    )
    async with engine.connect() as conn:
        result = await conn.execute(sql)
        for row in result.mappings():
            rows.append(dict(row))
            if limit and len(rows) >= limit:
                break
    await engine.dispose()
    return rows


def _build_props(row: dict[str, Any]) -> dict[str, Any]:
    """从 MySQL 行构造待写入 Neo4j 的属性（仅含可回填字段）。"""
    from app.services.graph_metadata import extract_authors, extract_venue, extract_year

    props: dict[str, Any] = {}
    year = extract_year(row.get("publication_date"))
    if year is not None:
        props["year"] = year
    venue = extract_venue(row.get("journal"))
    if venue is not None:
        props["venue"] = venue
    authors = extract_authors(row.get("authors"))
    if authors:
        props["authors"] = authors
    created_at = row.get("created_at")
    if isinstance(created_at, datetime):
        props["created_at"] = created_at.isoformat()
    elif isinstance(created_at, str) and created_at:
        props["created_at"] = created_at
    return props


async def _write_node(doc_id: str, title: str, props: dict[str, Any]) -> None:
    """调用 GraphRAGTest/neo4j_client.create_or_update_node（MERGE）。"""
    from neo4j_client import neo4j_client

    full_props = {"id": doc_id, "title": title, "name": title, **props}
    await neo4j_client.create_or_update_node(
        label="Document",
        match_key="id",
        match_value=doc_id,
        properties=full_props,
    )


async def _count_docs_with_year() -> int:
    """Cypher 校验：MATCH (d:Document) WHERE d.year IS NOT NULL RETURN count(d)。"""
    from neo4j_client import neo4j_client

    driver = await neo4j_client.get_driver()
    from config import settings as gr_settings

    async with driver.session(database=gr_settings.NEO4J_DATABASE) as session:
        result = await session.run(
            "MATCH (d:Document) WHERE d.year IS NOT NULL RETURN count(d) AS cnt"
        )
        record = await result.single()
        return int(record["cnt"])


async def _count_primary_docs() -> int:
    """统计主文档节点总数（external != true 的 Document 节点）。"""
    from neo4j_client import neo4j_client

    driver = await neo4j_client.get_driver()
    from config import settings as gr_settings

    async with driver.session(database=gr_settings.NEO4J_DATABASE) as session:
        result = await session.run(
            "MATCH (d:Document) WHERE coalesce(d.external, false) = false "
            "RETURN count(d) AS cnt"
        )
        record = await result.single()
        return int(record["cnt"])


async def main(args: argparse.Namespace) -> int:
    from app.services.graph_metadata import extract_year

    print(f"[backfill_node_props] dry_run={args.dry_run} limit={args.limit}")
    rows = await _fetch_documents(args.limit)
    print(f"[backfill_node_props] fetched {len(rows)} documents from MySQL")

    changes: list[dict[str, Any]] = []
    no_year: list[str] = []
    added = 0
    skipped_no_year = 0

    for row in rows:
        doc_id = str(row["id"])
        title = row.get("title") or ""
        props = _build_props(row)
        if "year" not in props:
            skipped_no_year += 1
            no_year.append(doc_id)
        changes.append({"doc_id": doc_id, "title": title[:60], "props": props})
        if not args.dry_run and props:
            try:
                await _write_node(doc_id, title, props)
                added += 1
            except Exception as e:
                print(f"[ERROR] write failed for {doc_id}: {e}", file=sys.stderr)
                return 2

    # 校验
    docs_with_year = 0
    primary_docs = 0
    if not args.dry_run:
        try:
            docs_with_year = await _count_docs_with_year()
            primary_docs = await _count_primary_docs()
        except Exception as e:
            print(f"[WARN] cypher verify failed: {e}", file=sys.stderr)

    summary = {
        "script": "backfill_node_props",
        "dry_run": args.dry_run,
        "fetched": len(rows),
        "added_or_updated": added,
        "skipped_no_year": skipped_no_year,
        "no_year_doc_ids": no_year,
        "docs_with_year_after": docs_with_year,
        "primary_docs_total": primary_docs,
        "changes_preview": changes[:20],
        "timestamp": datetime.now().isoformat(),
    }

    out_path = (
        Path(args.out)
        if args.out
        else _REPO_ROOT / "outputs" / "graph_node_props_backfill.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[backfill_node_props] summary written to {out_path}")
    print(
        json.dumps(
            {k: v for k, v in summary.items() if k != "changes_preview"},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Backfill Neo4j Document node properties from MySQL."
    )
    p.add_argument("--dry-run", action="store_true", help="不写 Neo4j，仅输出变更清单")
    p.add_argument("--limit", type=int, default=None, help="只处理前 N 条")
    p.add_argument("--out", type=str, default=None, help="汇总 JSON 输出路径")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    rc = asyncio.run(main(args))
    sys.exit(rc)
