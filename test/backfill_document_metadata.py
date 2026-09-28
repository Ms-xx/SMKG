#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文档元数据回填脚本（步骤 16.2 前置：先让 MySQL 具备 year/venue/authors，图谱回填才有数据源）。

用法：
    python test/backfill_document_metadata.py [--dry-run] [--out PATH]

流程：
    1. 读取 MySQL documents（id / title / file_path / doi / publication_date / journal / authors）；
    2. 从 file_path（或显式映射）提取 arXiv id；
    3. 调 arXiv 官方 API 拉取真实元数据（title / authors / published / doi）；
    4. 幂等写入 doi、authors、journal、publication_date；
    5. 汇总落盘 outputs/document_metadata_backfill.json。

约束：
    - --dry-run 零写入；
    - 已有值且与新值相同则计入 unchanged（重复执行 changed 应为 0）；
    - 元数据拉取失败不影响其他文档，逐条记录原因。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "backend"))

# file_path 无 arXiv 号、但人工确知的文献
_TITLE_ARXIV_OVERRIDES = {"attention is all you need (实测)": "1706.03762"}


async def _fetch_documents() -> list[dict[str, Any]]:
    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.core.config import settings

    engine = create_async_engine(settings.DATABASE_URL)
    rows: list[dict[str, Any]] = []
    async with engine.connect() as conn:
        result = await conn.execute(
            sa.text(
                "SELECT id, title, file_path, doi, journal, publication_date, authors "
                "FROM documents ORDER BY created_at"
            )
        )
        rows = [dict(r) for r in result.mappings()]
    await engine.dispose()
    return rows


def _arxiv_ids_per_doc(docs: list[dict[str, Any]]) -> dict[str, str | None]:
    """按文档推导 arXiv id（file_path 优先，其次标题映射）。"""
    from app.services.citation_graph_match import normalize_arxiv_id

    mapping: dict[str, str | None] = {}
    for d in docs:
        aid = normalize_arxiv_id(d.get("file_path"))
        if not aid:
            key = (d.get("title") or "").strip().lower()
            aid = normalize_arxiv_id(_TITLE_ARXIV_OVERRIDES.get(key))
        mapping[str(d["id"])] = aid
    return mapping


async def _apply_updates(updates: list[tuple[str, dict[str, Any]]]) -> None:
    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.core.config import settings

    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.connect() as conn:
        for doc_id, payload in updates:
            await conn.execute(
                sa.text(
                    "UPDATE documents SET doi=:doi, authors=:authors, journal=:journal, "
                    "publication_date=:pdate WHERE id=:id"
                ),
                {**payload, "id": doc_id},
            )
        await conn.commit()
    await engine.dispose()


def _build_target_props(doc: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    """构造目标值；与现值一致的部分由调用方判定 unchanged。"""
    year_part = (
        meta.get("published") or ""
    ).strip() or f"{meta.get('year') or ''}-01-01"
    try:
        pdate: Any = datetime.strptime(year_part[:10], "%Y-%m-%d").date()
    except ValueError:
        pdate = None
    return {
        "doi": str(meta.get("doi"))[:100] if meta.get("doi") else None,
        # authors 为 JSON 列：必须传 Python list，由驱动序列化；
        # 若传 json.dumps 后的字符串会被再次编码成「单元素字符串列表」。
        "authors": list(meta.get("authors") or []),
        "journal": str(meta.get("journal") or "arXiv preprint")[:200],
        "pdate": pdate,
    }


def _canon_authors(value: Any) -> str:
    """把 MySQL JSON 列（可能返回 str / list / None）规范化为可比较字符串。"""
    if value is None:
        return "[]"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=False)
    text = str(value).strip()
    if not text:
        return "[]"
    try:
        return json.dumps(json.loads(text), ensure_ascii=False)
    except (ValueError, TypeError):
        return text


def _is_unchanged(doc: dict[str, Any], target: dict[str, Any]) -> bool:
    return (
        (doc.get("doi") == target["doi"])
        and _canon_authors(doc.get("authors")) == _canon_authors(target["authors"])
        and (doc.get("journal") == target["journal"])
        and (doc.get("publication_date") == target["pdate"])
    )


async def main(args: argparse.Namespace) -> int:
    docs = await _fetch_documents()
    id_map = _arxiv_ids_per_doc(docs)
    unique_ids = sorted({a for a in id_map.values() if a})
    print(f"[doc_meta] documents={len(docs)} unique_arxiv_ids={len(unique_ids)}")

    metas: dict[str, dict[str, Any]] = {}
    if unique_ids:
        from corpus_expand import fetch_arxiv_metadata

        metas = fetch_arxiv_metadata(unique_ids)
    print(f"[doc_meta] arxiv metadata fetched={len(metas)}/{len(unique_ids)}")

    doc_by_id = {str(d["id"]): d for d in docs}
    candidates: list[tuple[str, dict[str, Any]]] = []
    missing: list[str] = []
    for d in docs:
        doc_id = str(d["id"])
        aid = id_map.get(doc_id)
        meta = metas.get(aid) if aid else None
        if not meta:
            missing.append(doc_id)
            continue
        candidates.append((doc_id, _build_target_props(d, meta)))

    # documents.doi 有唯一索引：同一个 DOI 只能落在一条文档上（按 created_at 最早者优先）。
    # 若某 DOI 已归属其它文档，则本条退化为 doi=NULL（重复副本仍保留其它元数据）。
    doi_owner: dict[str, str] = {
        str(d["doi"]): str(d["id"]) for d in docs if d.get("doi")
    }
    deduped = 0
    for doc_id, payload in candidates:
        doi = payload["doi"]
        if not doi:
            continue
        owner = doi_owner.get(doi)
        if owner is None:
            doi_owner[doi] = doc_id
        elif owner != doc_id:
            payload["doi"] = None
            deduped += 1

    planned: list[tuple[str, dict[str, Any]]] = []
    unchanged: list[str] = []
    for doc_id, payload in candidates:
        if _is_unchanged(doc_by_id[doc_id], payload):
            unchanged.append(doc_id)
        else:
            planned.append((doc_id, payload))

    if not args.dry_run and planned:
        await _apply_updates(planned)

    summary = {
        "script": "backfill_document_metadata",
        "dry_run": args.dry_run,
        "documents_total": len(docs),
        "arxiv_ids": unique_ids,
        "metadata_fetched": len(metas),
        "changed": len(planned),
        "doi_deduped": deduped,
        "unchanged": len(unchanged),
        "no_metadata": len(missing),
        "changed_doc_ids": [a for a, _ in planned],
        "no_metadata_doc_ids": missing,
        "generated_at": date.today().isoformat(),
        "timestamp": datetime.now().isoformat(),
    }
    out_path = (
        Path(args.out)
        if args.out
        else _REPO_ROOT / "outputs" / "document_metadata_backfill.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {k: v for k, v in summary.items() if k != "changed_doc_ids"},
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"[doc_meta] summary -> {out_path}")
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="回填 documents 表 arXiv 元数据")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--out", type=str, default=None)
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(asyncio.run(main(parse_args())))
