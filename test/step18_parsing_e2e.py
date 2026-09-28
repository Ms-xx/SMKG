#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
步骤 18：多模态细粒度解析端到端验证与补强（XiangMu 阶段 E 第一梯队 P0）。

三类真实样本：
  1) 版本对：arXiv 1706.03762 v1 与 v7（同一论文不同版本，用于语义级去重验证）；
  2) 长篇文档：arXiv 2005.14165（GPT-3，约 70+ 页，用于长文档解析验证）；
  3) 扫描件：由 v7 前几页渲染成纯图像 PDF（无文本层，用于 OCR 链路验证）。

流程：
  1. 准备样本（下载 / 生成，落 outputs/samples/）；
  2. 经 POST /api/v1/documents/upload 入库并触发解析，轮询至 parsed；
  3. 采集解析证据：页数、正文字符数、各 element_type 计数、参考文献条数；
  4. 调 POST /api/v1/deduplication/detect 验证 v1/v7 同簇 + 保留最新版本建议；
  5. 落盘 outputs/dedup_v1_v7_report.json 与 outputs/parsing_e2e_report.json。

用法：
    python test/step18_parsing_e2e.py [--skip-download] [--parse-timeout 900]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "backend"))

BASE_URL = "http://127.0.0.1:8000"
API = f"{BASE_URL}/api/v1"
USERNAME = "admin"
PASSWORD = "admin123"

SAMPLES_DIR = _REPO_ROOT / "outputs" / "samples"

# 样本定义：key -> (文件名, 标题, 下载地址或特殊标记)
SAMPLES: dict[str, dict[str, str]] = {
    "v1": {
        "file": "attention_1706.03762v1.pdf",
        "title": "Attention Is All You Need (arXiv v1)",
        "url": "https://arxiv.org/pdf/1706.03762v1",
    },
    "v7": {
        "file": "attention_1706.03762v7.pdf",
        "title": "Attention Is All You Need (arXiv v7)",
        "url": "https://arxiv.org/pdf/1706.03762v7",
    },
    "long": {
        "file": "long_2005.14165.pdf",
        "title": "Language Models are Few-Shot Learners (长篇样本)",
        "url": "https://arxiv.org/pdf/2005.14165",
    },
    "scanned": {
        "file": "scanned_sample.pdf",
        "title": "扫描件样本（纯图像，无文本层）",
        "url": "",  # 由 v7 渲染生成
    },
}

UA = {"User-Agent": "Mozilla/5.0 (compatible; LX-Platform-E2E/1.0)"}


def login() -> str:
    resp = requests.post(
        f"{API}/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ────────────────────────── 样本准备 ──────────────────────────
def download_pdf(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 1024:
        print(f"  [cache] {dest.name} ({dest.stat().st_size} bytes)")
        return True
    try:
        r = requests.get(url, headers=UA, timeout=60)
        if r.status_code != 200 or not r.content.startswith(b"%PDF"):
            print(f"  [FAIL] 下载失败或非 PDF: {url} -> {r.status_code}")
            return False
        dest.write_bytes(r.content)
        print(f"  [downloaded] {dest.name} ({len(r.content)} bytes)")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  [FAIL] 下载异常 {url}: {e}")
        return False


def generate_scanned_pdf(
    source: Path, dest: Path, pages: int = 3, dpi: int = 150
) -> bool:
    """把源 PDF 前 N 页渲染为图像并重新封装为纯图像 PDF（无文本层）。"""
    if dest.exists() and dest.stat().st_size > 1024:
        print(f"  [cache] {dest.name} ({dest.stat().st_size} bytes)")
        return True
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("  [FAIL] 未安装 PyMuPDF(fitz)，无法生成扫描件样本")
        return False
    try:
        src = fitz.open(str(source))
        out = fitz.open()
        for i in range(min(pages, src.page_count)):
            page = src.load_page(i)
            pix = page.get_pixmap(dpi=dpi)
            rect = page.rect
            # PyMuPDF 的 Pixmap 不支持直接输出 pdf，需先转 PNG 再作为图像插入新页，
            # 这样得到的 PDF 只有位图、没有文本层（等价于扫描件）。
            out_page = out.new_page(width=rect.width, height=rect.height)
            out_page.insert_image(rect, pixmap=pix)
        out.save(str(dest))
        out.close()
        src.close()
        print(
            f"  [generated] {dest.name} ({dest.stat().st_size} bytes, {pages} 页纯图像)"
        )
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  [FAIL] 生成扫描件失败: {e}")
        return False


def prepare_samples(skip_download: bool) -> dict[str, Path]:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    print("[1/5] 准备样本")
    paths: dict[str, Path] = {}
    for key, cfg in SAMPLES.items():
        dest = SAMPLES_DIR / cfg["file"]
        if key == "scanned":
            src = SAMPLES_DIR / SAMPLES["v7"]["file"]
            ok = src.exists() and generate_scanned_pdf(src, dest)
        elif skip_download:
            ok = dest.exists()
            print(f"  [skip] {cfg['file']} exists={ok}")
        else:
            ok = download_pdf(cfg["url"], dest)
        if ok:
            paths[key] = dest
    return paths


# ────────────────────────── 入库与解析 ──────────────────────────
def upload_document(token: str, path: Path, title: str) -> dict[str, Any] | None:
    try:
        with path.open("rb") as f:
            r = requests.post(
                f"{API}/documents/upload",
                headers=auth_headers(token),
                files={"file": (path.name, f, "application/pdf")},
                data={"title": title},
                timeout=180,
            )
        if r.status_code not in (200, 201):
            print(f"  [FAIL] 上传 {path.name}: {r.status_code} {r.text[:200]}")
            return None
        doc = r.json()
        print(f"  [uploaded] {title} -> {doc.get('id')}")
        return doc
    except Exception as e:  # noqa: BLE001
        print(f"  [FAIL] 上传异常 {path.name}: {e}")
        return None


def find_existing_document(
    token: str, title: str, file_name: str
) -> dict[str, Any] | None:
    """按标题/文件名查已入库文档，避免重复上传造成语料污染。"""
    try:
        r = requests.get(
            f"{API}/documents/",
            headers=auth_headers(token),
            params={"keyword": file_name, "page_size": 20},
            timeout=30,
        )
        if r.status_code != 200:
            return None
        # 上传时传的 title 会被 PDF 元数据覆盖为文件名，因此两种写法都要匹配
        for item in r.json().get("items", []):
            if (item.get("title") or "").strip() in {title.strip(), file_name.strip()}:
                return item
    except Exception:  # noqa: BLE001
        return None
    return None


def trigger_parse(token: str, doc_id: str) -> bool:
    try:
        r = requests.post(
            f"{API}/documents/{doc_id}/parse", headers=auth_headers(token), timeout=60
        )
        return r.status_code in (200, 201, 202)
    except Exception:  # noqa: BLE001
        return False


def wait_parsed(token: str, doc_id: str, timeout: int) -> dict[str, Any]:
    deadline = time.time() + timeout
    last: dict[str, Any] = {}
    while time.time() < deadline:
        try:
            r = requests.get(
                f"{API}/documents/{doc_id}", headers=auth_headers(token), timeout=30
            )
            if r.status_code == 200:
                last = r.json()
                status = last.get("status")
                if status in ("parsed", "failed"):
                    return last
        except Exception:  # noqa: BLE001
            pass
        time.sleep(5)
    return {**last, "status": "timeout"}


async def element_stats(doc_id: str) -> dict[str, int]:
    """按 element_type 统计解析元素（直连 MySQL，避免抽样偏差）。"""
    import sqlalchemy as sa
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.core.config import settings

    engine = create_async_engine(settings.DATABASE_URL)
    stats: dict[str, int] = {}
    async with engine.connect() as conn:
        res = await conn.execute(
            sa.text(
                "SELECT de.element_type AS t, COUNT(*) AS c "
                "FROM document_elements de "
                "JOIN document_pages dp ON dp.id = de.page_id "
                "WHERE dp.document_id = :doc GROUP BY de.element_type"
            ),
            {"doc": doc_id},
        )
        stats = {row[0]: int(row[1]) for row in res}
        res = await conn.execute(
            sa.text("SELECT COUNT(*) FROM document_pages WHERE document_id = :doc"),
            {"doc": doc_id},
        )
        stats["_pages"] = int(res.scalar() or 0)
    await engine.dispose()
    return stats


def fulltext_length(token: str, doc_id: str) -> int:
    try:
        r = requests.get(
            f"{API}/documents/{doc_id}/fulltext",
            headers=auth_headers(token),
            timeout=60,
        )
        if r.status_code != 200:
            return 0
        data = r.json()
        if isinstance(data, dict):
            pages = data.get("pages") or []
            return sum(len(p.get("text") or "") for p in pages)
        return 0
    except Exception:  # noqa: BLE001
        return 0


def document_detail(token: str, doc_id: str) -> dict[str, Any]:
    try:
        r = requests.get(
            f"{API}/documents/{doc_id}", headers=auth_headers(token), timeout=30
        )
        return r.json() if r.status_code == 200 else {}
    except Exception:  # noqa: BLE001
        return {}


# ────────────────────────── 主流程 ──────────────────────────
def main(args: argparse.Namespace) -> int:
    token = login()
    paths = prepare_samples(args.skip_download)
    if len(paths) < 2:
        print("[FATAL] 样本不足，无法继续")
        return 2

    print("[2/5] 上传并解析样本")
    docs: dict[str, dict[str, Any]] = {}
    for key, path in paths.items():
        title = SAMPLES[key]["title"]
        doc = find_existing_document(token, title, SAMPLES[key]["file"])
        if doc:
            print(f"  [reuse] {title} -> {doc.get('id')}")
            if args.force_parse and doc.get("status") != "parsing":
                trigger_parse(token, doc["id"])
                doc = wait_parsed(token, doc["id"], args.parse_timeout)
        else:
            doc = upload_document(token, path, title)
            if not doc:
                continue
            trigger_parse(token, doc["id"])
            doc = wait_parsed(token, doc["id"], args.parse_timeout)
        print(
            f"  [parsed] {title} status={doc.get('status')} pages={doc.get('page_count')}"
        )
        docs[key] = doc

    print("[3/5] 采集解析证据")
    parse_report: dict[str, Any] = {
        "script": "step18_parsing_e2e",
        "generated_at": datetime.now().isoformat(),
        "samples": {},
    }
    for key, doc in docs.items():
        stats = asyncio.run(element_stats(doc["id"]))
        chars = fulltext_length(token, doc["id"])
        detail = document_detail(token, doc["id"])
        refs = detail.get("references") or []
        if isinstance(refs, str):
            try:
                refs = json.loads(refs)
            except ValueError:
                refs = []
        parse_report["samples"][key] = {
            "document_id": doc["id"],
            "title": doc.get("title"),
            "status": doc.get("status"),
            "page_count": doc.get("page_count"),
            "fulltext_chars": chars,
            "element_counts": stats,
            "references_count": len(refs),
            "has_formula": (stats.get("formula", 0) + stats.get("equation", 0)) > 0,
            "has_table": stats.get("table", 0) > 0,
            "has_figure": (stats.get("figure", 0) + stats.get("image", 0)) > 0,
            "heading_levels": sorted(
                t for t in stats if t.startswith("heading") or t.startswith("title")
            ),
        }
        print(
            f"  {key}: pages={doc.get('page_count')} chars={chars} "
            f"elements={ {k: v for k, v in stats.items() if not k.startswith('_')} }"
        )

    print("[4/5] 语义去重验证（v1 vs v7）")
    dedup_report: dict[str, Any] = {
        "script": "step18_parsing_e2e",
        "generated_at": datetime.now().isoformat(),
        "pairs": [],
        "passed": False,
    }
    if "v1" in docs and "v7" in docs:
        payload = {
            "documents": [
                {
                    "id": docs["v1"]["id"],
                    "title": docs["v1"].get("title"),
                    "text": " ".join(
                        [docs["v1"].get("title") or "", SAMPLES["v1"]["file"]]
                    ),
                },
                {
                    "id": docs["v7"]["id"],
                    "title": docs["v7"].get("title"),
                    "text": " ".join(
                        [docs["v7"].get("title") or "", SAMPLES["v7"]["file"]]
                    ),
                },
            ]
        }
        # 指纹以真实正文为准（截取前若干字符，避免请求体过大）
        for item, key in zip(payload["documents"], ("v1", "v7")):
            item["text"] = fetch_text_sample(token, docs[key]["id"])
        r = requests.post(
            f"{API}/deduplication/detect",
            headers=auth_headers(token),
            json=payload,
            timeout=60,
        )
        result = r.json() if r.status_code == 200 else {"error": r.text[:200]}
        clusters = result.get("clusters") or result.get("groups") or []
        target_ids = {str(docs["v1"]["id"]), str(docs["v7"]["id"])}
        same_cluster = False
        for cluster in clusters:
            members = cluster.get("documents") or cluster.get("items") or []
            member_ids = {_id_of(d) for d in members}
            if target_ids.issubset(member_ids):
                same_cluster = True
                break
        dedup_report["request_summary"] = {
            "v1_id": docs["v1"]["id"],
            "v7_id": docs["v7"]["id"],
        }
        dedup_report["response"] = result
        dedup_report["same_cluster"] = same_cluster
        dedup_report["keep_latest_suggestion"] = (
            result.get("suggestions") or result.get("keep") or None
        )
        dedup_report["passed"] = bool(same_cluster)
        print(f"  same_cluster={same_cluster}")
    else:
        dedup_report["error"] = "v1/v7 样本缺失，跳过"

    print("[5/5] 落盘报告")
    out_dedup = _REPO_ROOT / "outputs" / "dedup_v1_v7_report.json"
    out_parse = _REPO_ROOT / "outputs" / "parsing_e2e_report.json"
    out_dedup.write_text(
        json.dumps(dedup_report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    out_parse.write_text(
        json.dumps(parse_report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  {out_dedup}")
    print(f"  {out_parse}")
    return 0


def _id_of(item: Any) -> str | None:
    if isinstance(item, dict):
        return str(item.get("id") or item.get("document_id") or "")
    return str(item)


def fetch_text_sample(token: str, doc_id: str, limit: int = 6000) -> str:
    """取正文片段参与指纹计算（前 limit 字符）。"""
    try:
        r = requests.get(
            f"{API}/documents/{doc_id}/fulltext",
            headers=auth_headers(token),
            timeout=60,
        )
        if r.status_code != 200:
            return ""
        data = r.json()
        pages = data.get("pages") or []
        text = " ".join((p.get("text") or "") for p in pages)
        return text[:limit]
    except Exception:  # noqa: BLE001
        return ""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="步骤 18：多模态解析端到端验证")
    p.add_argument("--skip-download", action="store_true", help="样本已存在时跳过下载")
    p.add_argument(
        "--force-parse",
        action="store_true",
        help="已入库样本也重新触发解析（默认复用已解析结果）",
    )
    p.add_argument(
        "--parse-timeout", type=int, default=900, help="单个文档解析等待上限（秒）"
    )
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(main(parse_args()))
