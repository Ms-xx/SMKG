#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
语料扩充驱动器（步骤 16.1.1）。

用法：
    python test/corpus_expand.py [--ids 1607.06450,1409.0473] [--sleep 3.5] [--out PATH]

流程：
    1. 管理员登录获取 JWT（/api/v1/auth/login）；
    2. 对每个 arXiv id 调用 arXiv 官方 API 拉取真实元数据（title/authors/year/doi）；
    3. 调用 POST /api/v1/paper-retrieval/download-and-ingest 完成
       「arXiv → PDF → MinIO → 建文档 → 触发解析」真实入库闭环；
    4. 汇总落盘 outputs/corpus_expand_report.json（含逐篇耗时与失败原因）。

约束：
    - arXiv 官方限流，默认每次请求间隔 3.5s；
    - 单篇失败不影响整体，失败原因如实记录；
    - 脚本只写后端接口，不直接改库，保证与线上链路一致。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "backend"))

_ARXIV_API = "http://export.arxiv.org/api/query"
_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}

# 默认语料：取自库内已解析《Attention Is All You Need》参考文献中的 arXiv id，
# 以保证回填后能产生真实 CITES 边。
DEFAULT_IDS = [
    "1607.06450",
    "1409.0473",
    "1703.03906",
    "1601.06733",
    "1406.1078",
    "1610.02357",
    "1412.3555",
    "1705.03122",
    "1308.0850",
    "1602.02410",
    "1610.10099",
    "1703.10722",
    "1703.03130",
    "1511.06114",
    "1508.04025",
]


def _http_get(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "SciDocPlatform/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read().decode("utf-8", errors="replace")


def fetch_arxiv_metadata(ids: list[str]) -> dict[str, dict[str, Any]]:
    """批量拉取 arXiv 官方元数据，返回 {arxiv_id: metadata}。"""
    params = urllib.parse.urlencode(
        {"id_list": ",".join(ids), "start": 0, "max_results": len(ids)}
    )
    xml_text = _http_get(f"{_ARXIV_API}?{params}", timeout=60)
    root = ET.fromstring(xml_text)
    out: dict[str, dict[str, Any]] = {}

    def _text(entry: ET.Element, tag: str) -> str:
        el = entry.find(f"atom:{tag}", _ATOM_NS)
        return (el.text or "").strip() if el is not None else ""

    for entry in root.findall("atom:entry", _ATOM_NS):
        id_el = entry.find("atom:id", _ATOM_NS)
        aid = (
            (id_el.text or "").strip().rsplit("/abs/", 1)[-1]
            if id_el is not None
            else ""
        )
        if not aid:
            continue
        # arXiv API 返回的 id 可能形如 1607.06450v2，统一去版本号入库，便于与文件名匹配
        aid = re.sub(r"v\d+$", "", aid)
        authors = [
            a.find("atom:name", _ATOM_NS).text.strip()
            for a in entry.findall("atom:author", _ATOM_NS)
            if a.find("atom:name", _ATOM_NS) is not None
            and a.find("atom:name", _ATOM_NS).text
        ]
        published = _text(entry, "published")
        out[aid] = {
            "arxiv_id": aid,
            "title": " ".join(_text(entry, "title").split()),
            "authors": authors,
            "year": published[:4] or None,
            "doi": f"10.48550/arXiv.{aid}",
            "journal": "arXiv preprint",
            "published": published,
            "summary": " ".join(_text(entry, "summary").split())[:300],
        }
    return out


def login(base_url: str, username: str, password: str) -> str:
    payload = json.dumps({"username": username, "password": password}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/api/v1/auth/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        body = json.loads(resp.read().decode("utf-8"))
    return body["access_token"]


def ingest(
    base_url: str, token: str, result: dict[str, Any], timeout: int = 180
) -> dict[str, Any]:
    payload = json.dumps({"result": result}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/api/v1/paper-retrieval/download-and-ingest",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def main(args: argparse.Namespace) -> int:
    from app.core.config import settings

    base_url = args.base_url or f"http://127.0.0.1:8000"
    ids = [i.strip() for i in args.ids.split(",") if i.strip()]
    print(f"[corpus_expand] target={len(ids)} ids={ids}")

    meta_map = fetch_arxiv_metadata(ids)
    print(f"[corpus_expand] arxiv metadata fetched={len(meta_map)}/{len(ids)}")

    token = login(base_url, args.username, args.password)
    print("[corpus_expand] login ok")

    records: list[dict[str, Any]] = []
    ok = failed = 0
    for idx, aid in enumerate(ids, 1):
        meta = meta_map.get(aid)
        record: dict[str, Any] = {"arxiv_id": aid, "metadata_found": meta is not None}
        if meta:
            record.update(
                {k: meta[k] for k in ("title", "authors", "year", "doi", "journal")}
            )
        started = time.time()
        try:
            result = {"source": "arxiv", "arxiv_id": aid, **(meta or {})}
            resp = ingest(base_url, token, result, timeout=args.timeout)
            record["http"] = {k: resp.get(k) for k in ("ingested", "document_id")}
            record["download"] = resp.get("download")
            if resp.get("ingested"):
                ok += 1
            else:
                failed += 1
        except Exception as e:  # noqa: BLE001
            failed += 1
            record["error"] = str(e)
        record["elapsed_s"] = round(time.time() - started, 2)
        records.append(record)
        print(
            f"  [{idx}/{len(ids)}] {aid} ingested={record.get('http', {}).get('ingested')} "
            f"{record['elapsed_s']}s err={record.get('error', '')}"
        )
        if idx < len(ids):
            time.sleep(args.sleep)

    summary = {
        "script": "corpus_expand",
        "base_url": base_url,
        "requested": len(ids),
        "ingested_ok": ok,
        "failed": failed,
        "sleep_s": args.sleep,
        "records": records,
        "timestamp": datetime.now().isoformat(),
        "settings_fingerprint": {
            "db": str(getattr(settings, "DATABASE_URL", "")).split("@")[-1],
        },
    }
    out_path = (
        Path(args.out)
        if args.out
        else _REPO_ROOT / "outputs" / "corpus_expand_report.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[corpus_expand] report -> {out_path}  ok={ok} failed={failed}")
    return 0 if ok else 1


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="扩充真实 arXiv 语料（download-and-ingest 闭环）"
    )
    p.add_argument("--ids", type=str, default=",".join(DEFAULT_IDS))
    p.add_argument("--base-url", type=str, default=None)
    p.add_argument("--username", type=str, default="admin")
    p.add_argument("--password", type=str, default="admin123")
    p.add_argument("--sleep", type=float, default=3.5)
    p.add_argument("--timeout", type=int, default=180)
    p.add_argument("--out", type=str, default=None)
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(main(parse_args()))
