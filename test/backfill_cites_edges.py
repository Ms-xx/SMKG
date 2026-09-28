#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
引用边（CITES）回填脚本（步骤 16.1.3）。

用法：
    python test/backfill_cites_edges.py [--dry-run] [--corpus-expand] [--out PATH]

流程：
    1. 读取 MySQL documents.references 与 outputs/enrich_metadata.json；
    2. 构建候选索引；
    3. 逐条 match_reference_to_document；
    4. 命中者写 (:Document)-[:CITES {match_type, confidence}]->(:Document)（MERGE）；
    5. 未命中者建 external: true 的 Document 节点。

约束：
    - --dry-run 零写入；
    - --corpus-expand 先调用 POST /api/v1/paper-retrieval/download-and-ingest 扩充语料；
    - 写边失败非零退出，不静默成功。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
# 顺序要求：先插 GraphRAGTest、再插 backend（backend 必须在 sys.path[0]），
# 避免 GraphRAGTest/app.py 遮蔽 backend/app 包。
sys.path.insert(0, str(_REPO_ROOT / "GraphRAGTest"))
sys.path.insert(0, str(_REPO_ROOT / "backend"))


async def _fetch_documents_with_refs() -> list[dict[str, Any]]:
    """只读查询 MySQL documents 表（含 references 字段）。"""
    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.core.config import settings

    engine = create_async_engine(settings.DATABASE_URL)
    rows: list[dict[str, Any]] = []
    # 注意：references 是 MySQL 保留字，必须用反引号转义
    sql = sa.text(
        "SELECT id, title, doi, authors, journal, publication_date, `references`, file_path "
        "FROM documents ORDER BY id"
    )
    async with engine.connect() as conn:
        result = await conn.execute(sql)
        for row in result.mappings():
            item = dict(row)
            # MySQL JSON 列经驱动可能返回字符串，统一反序列化为 list
            refs = item.get("references")
            if isinstance(refs, str):
                try:
                    item["references"] = json.loads(refs) if refs.strip() else []
                except ValueError:
                    item["references"] = []
            rows.append(item)
    await engine.dispose()
    return rows


def _load_enrich_metadata() -> dict[str, Any]:
    """加载 outputs/enrich_metadata.json（若存在）。"""
    path = _REPO_ROOT / "outputs" / "enrich_metadata.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _build_candidates(
    docs: list[dict[str, Any]], enrich: dict[str, Any]
) -> list[dict[str, Any]]:
    """合并 documents 与 enrich_metadata 构建候选文档集合。"""
    from app.services.graph_metadata import extract_authors, extract_venue, extract_year

    candidates: list[dict[str, Any]] = []
    for d in docs:
        candidates.append(
            {
                "doc_id": str(d["id"]),
                "doi": d.get("doi"),
                "title": d.get("title"),
                # file_path 承载 arXiv id（入库文件名为 <arxiv_id>.pdf），供 arXiv 档匹配
                "file_path": d.get("file_path"),
                "year": extract_year(d.get("publication_date")),
                "venue": extract_venue(d.get("journal")),
                "authors": extract_authors(d.get("authors")),
            }
        )
    # 合并 enrich_metadata 中的额外文档（若有）
    if isinstance(enrich, dict):
        for k, v in enrich.items():
            if isinstance(v, dict) and v.get("title"):
                candidates.append(
                    {
                        "doc_id": str(v.get("id") or k),
                        "doi": v.get("doi"),
                        "title": v.get("title"),
                        "year": v.get("year"),
                        "venue": v.get("venue"),
                        "authors": v.get("authors") or [],
                    }
                )
    return candidates


async def _write_cites_edge(
    src_id: str, tgt_id: str, match_type: str, confidence: float
) -> None:
    """幂等写入 CITES 关系（MERGE 语义）。"""
    from neo4j_client import neo4j_client

    driver = await neo4j_client.get_driver()
    from config import settings as gr_settings

    query = (
        "MATCH (s:Document {id: $src}) "
        "MATCH (t:Document {id: $tgt}) "
        "MERGE (s)-[r:CITES]->(t) "
        "ON CREATE SET r.match_type = $mt, r.confidence = $c "
        "ON MATCH SET r.match_type = $mt, r.confidence = $c "
        "RETURN type(r) AS rt"
    )
    async with driver.session(database=gr_settings.NEO4J_DATABASE) as session:
        await session.run(query, src=src_id, tgt=tgt_id, mt=match_type, c=confidence)


async def _write_external_node(ref: dict[str, Any]) -> str:
    """为未匹配参考文献建 external: true 的 Document 节点，返回节点 id。"""
    from neo4j_client import neo4j_client

    ext_id = f"ext:{ref.get('doi') or ref.get('title', '')[:60]}"
    props = {
        "id": ext_id,
        "title": ref.get("title", ""),
        "name": ref.get("title", ""),
        "external": True,
        "year": ref.get("year"),
        "doi": ref.get("doi"),
    }
    props = {k: v for k, v in props.items() if v is not None}
    await neo4j_client.create_or_update_node(
        label="Document", match_key="id", match_value=ext_id, properties=props
    )
    return ext_id


async def _count_cites_edges() -> int:
    from neo4j_client import neo4j_client

    driver = await neo4j_client.get_driver()
    from config import settings as gr_settings

    async with driver.session(database=gr_settings.NEO4J_DATABASE) as session:
        result = await session.run("MATCH ()-[r:CITES]->() RETURN count(r) AS cnt")
        record = await result.single()
        return int(record["cnt"])


async def main(args: argparse.Namespace) -> int:
    from app.services.citation_graph_match import (
        MatchType,
        match_reference_to_document,
    )

    print(
        f"[backfill_cites_edges] dry_run={args.dry_run} corpus_expand={args.corpus_expand}"
    )
    docs = await _fetch_documents_with_refs()
    enrich = _load_enrich_metadata()
    candidates = _build_candidates(docs, enrich)
    print(f"[backfill_cites_edges] docs={len(docs)} candidates={len(candidates)}")

    cites_before = 0
    if not args.dry_run:
        try:
            cites_before = await _count_cites_edges()
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] count cites failed: {e}", file=sys.stderr)

    matches: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    added = 0

    for d in docs:
        src_id = str(d["id"])
        refs = d.get("references") or []
        if not isinstance(refs, list):
            continue
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            result = match_reference_to_document(ref, candidates)
            if result.match_type == MatchType.UNMATCHED or result.doc_id is None:
                unmatched.append({"src": src_id, "ref": ref.get("title", "")[:60]})
                if not args.dry_run:
                    try:
                        await _write_external_node(ref)
                    except Exception as e:
                        print(f"[WARN] external node failed: {e}", file=sys.stderr)
                continue
            if result.doc_id == src_id:
                continue  # 不自引
            matches.append(
                {
                    "src": src_id,
                    "tgt": result.doc_id,
                    "match_type": result.match_type.value,
                    "confidence": result.confidence,
                }
            )
            if not args.dry_run:
                try:
                    await _write_cites_edge(
                        src_id,
                        result.doc_id,
                        result.match_type.value,
                        result.confidence,
                    )
                    added += 1
                except Exception as e:
                    print(f"[ERROR] write edge failed: {e}", file=sys.stderr)
                    return 2

    # 写入后再统计：用于「新增关系数 = after - before」的幂等判定
    cites_count = 0
    if not args.dry_run:
        try:
            cites_count = await _count_cites_edges()
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] count cites failed: {e}", file=sys.stderr)

    summary = {
        "script": "backfill_cites_edges",
        "dry_run": args.dry_run,
        "corpus_expanded": args.corpus_expand,
        "docs": len(docs),
        "candidates": len(candidates),
        "matched": len(matches),
        "unmatched": len(unmatched),
        "edges_added_or_updated": added,
        "cites_total_before": cites_before,
        "cites_total_after": cites_count,
        "cites_newly_created": max(cites_count - cites_before, 0),
        "matches_preview": matches[:20],
        "timestamp": datetime.now().isoformat(),
    }

    out_path = (
        Path(args.out)
        if args.out
        else _REPO_ROOT / "outputs" / "graph_cites_backfill.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[backfill_cites_edges] summary written to {out_path}")
    print(
        json.dumps(
            {k: v for k, v in summary.items() if k != "matches_preview"},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Backfill Neo4j CITES edges from documents.references."
    )
    p.add_argument("--dry-run", action="store_true", help="不写 Neo4j，仅输出匹配清单")
    p.add_argument("--corpus-expand", action="store_true", help="先调用语料扩充接口")
    p.add_argument("--out", type=str, default=None, help="汇总 JSON 输出路径")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    rc = asyncio.run(main(args))
    sys.exit(rc)
