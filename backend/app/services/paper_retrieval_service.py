# -*- coding: utf-8 -*-
"""
论文检索与推荐服务（对应 XiangMu 10.2 模块四）

职责：
1. arXiv / PubMed 检索：调用公开 HTTP API（stdlib urllib + xml.etree/json，零第三方依赖）；
2. 相关性推荐：基于本地参考文献库与候选论文的关键词/Jaccard 打分。

依赖策略（可插拔、可降级）：
- 网络失败（超时/不可达/解析失败）时降级返回空列表 + error 标记，不抛异常；
- PDF 下载与定时追踪本服务已提供下载 PDF + 内存追踪注册表，真实「入库 + 定时轮询」见文档（需存储与调度器）。
"""
from __future__ import annotations

import datetime
import json
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from typing import Any

from app.core.config import settings

_ARXIV_API = "http://export.arxiv.org/api/query"
_PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_PUBMED_ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"


def _http_get(url: str, timeout: float = 10.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "SMKG/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _entry_text(entry, tag: str) -> str:
    el = entry.find(f"atom:{tag}", _ATOM_NS)
    return (el.text or "").strip() if el is not None and el.text else ""


def search_arxiv(query: str, max_results: int = 10) -> dict[str, Any]:
    params = urllib.parse.urlencode(
        {"search_query": f"all:{query}", "start": 0, "max_results": max_results}
    )
    try:
        xml_text = _http_get(f"{_ARXIV_API}?{params}")
        root = ET.fromstring(xml_text)
        results: list[dict[str, Any]] = []
        for entry in root.findall("atom:entry", _ATOM_NS):
            aid_el = entry.find("atom:id", _ATOM_NS)
            arxiv_id = (
                (aid_el.text or "").strip().rsplit("/abs/", 1)[-1]
                if aid_el is not None and aid_el.text
                else ""
            )
            results.append(
                {
                    "title": _entry_text(entry, "title"),
                    "summary": _entry_text(entry, "summary")[:400],
                    "authors": [
                        a.find("atom:name", _ATOM_NS).text
                        for a in entry.findall("atom:author", _ATOM_NS)
                        if a.find("atom:name", _ATOM_NS) is not None
                    ],
                    "arxiv_id": arxiv_id,
                    "published": _entry_text(entry, "published"),
                    "source": "arxiv",
                }
            )
        return {"backend": "arxiv", "query": query, "count": len(results), "results": results}
    except Exception as e:  # noqa: BLE001
        return {"backend": "arxiv", "query": query, "count": 0, "results": [], "error": str(e)}


def search_pubmed(query: str, max_results: int = 10) -> dict[str, Any]:
    try:
        esearch = urllib.parse.urlencode(
            {"db": "pubmed", "term": query, "retmax": max_results, "retmode": "json"}
        )
        data = json.loads(_http_get(f"{_PUBMED_ESEARCH}?{esearch}"))
        ids = data.get("esearchresult", {}).get("idlist", [])
        if not ids:
            return {"backend": "pubmed", "query": query, "count": 0, "results": []}
        esummary = urllib.parse.urlencode({"db": "pubmed", "id": ",".join(ids), "retmode": "json"})
        summary = json.loads(_http_get(f"{_PUBMED_ESUMMARY}?{esummary}"))
        results: list[dict[str, Any]] = []
        for pid in ids:
            item = summary.get("result", {}).get(pid, {})
            authors = [a.get("name") for a in item.get("authors", [])]
            results.append(
                {
                    "title": item.get("title", ""),
                    "summary": "",
                    "authors": authors,
                    "pubmed_id": pid,
                    "published": item.get("pubdate", ""),
                    "source": "pubmed",
                }
            )
        return {"backend": "pubmed", "query": query, "count": len(results), "results": results}
    except Exception as e:  # noqa: BLE001
        return {"backend": "pubmed", "query": query, "count": 0, "results": [], "error": str(e)}


def _tokens(text: str) -> set[str]:
    return {t for t in re_findall(text) if t}


def re_findall(text: str) -> list[str]:
    import re

    return re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", (text or "").lower())


def _jaccard_score(a: str, b: str) -> float:
    sa, sb = _tokens(a), _tokens(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def recommend(
    local_references: list[dict[str, Any]], candidates: list[dict[str, Any]]
) -> dict[str, Any]:
    """本地文献库 vs 候选论文相关性打分，输出推荐与理由。"""
    scored: list[dict[str, Any]] = []
    local_text = " ".join(
        f"{r.get('title') or ''} {r.get('journal') or ''}" for r in local_references or []
    )
    for c in candidates or []:
        cand_text = (
            f"{c.get('title') or ''} {c.get('summary') or ''} {' '.join(c.get('authors') or [])}"
        )
        title_sim = _jaccard_score(local_text, cand_text)
        reason = "与本地文献库关键词高度重叠" if title_sim >= 0.3 else "主题相关度一般"
        scored.append(
            {
                "title": c.get("title"),
                "source": c.get("source"),
                "score": round(title_sim, 4),
                "reason": reason,
            }
        )
    scored.sort(key=lambda x: x["score"], reverse=True)
    return {
        "backend": "builtin",
        "local_reference_count": len(local_references or []),
        "recommendations": scored,
    }


_ARXIV_PDF = "https://arxiv.org/pdf/{arxiv_id}"


def _http_get_bytes(url: str, timeout: float = 15.0) -> bytes:
    """下载二进制内容（如 PDF）。失败抛异常，由调用方降级。"""
    req = urllib.request.Request(url, headers={"User-Agent": "SMKG/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def pdf_url(result: dict[str, Any]) -> str | None:
    """根据检索结果构造 PDF 下载地址。arXiv 有直链；PubMed 无直接 PDF 需经 PMC/DOI。"""
    if result.get("source") == "arxiv" and result.get("arxiv_id"):
        return _ARXIV_PDF.format(arxiv_id=result["arxiv_id"])
    return None


class PaperRetrievalService:
    def __init__(self) -> None:
        # 内存态论文追踪注册表（进程内有效；真实定时轮询需调度器 + 持久化，见文档）
        self._tracking: dict[str, dict[str, Any]] = {}

    @property
    def available(self) -> bool:
        return settings.PAPER_RETRIEVAL_ENABLED

    def search(
        self, query: str, source: str = "arxiv", max_results: int | None = None
    ) -> dict[str, Any]:
        max_results = max_results or settings.ARXIV_MAX_RESULTS
        if source == "pubmed":
            return search_pubmed(query, max_results)
        return search_arxiv(query, max_results)

    def recommend(
        self, local_references: list[dict[str, Any]], candidates: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return recommend(local_references, candidates)

    def download_pdf(self, result: dict[str, Any]) -> dict[str, Any]:
        """下载检索结果的 PDF（返回元数据；字节丢弃，仅供判活与取大小）。"""
        meta, _data = self.download_bytes(result)
        return meta

    def download_bytes(self, result: dict[str, Any]) -> tuple[dict[str, Any], bytes | None]:
        """下载检索结果的 PDF 字节。

        返回 (元数据, 字节)。下载失败时返回 (元数据含 error, None)，由调用方降级。
        该方法是「下载 → 上传 MinIO → 触发解析入库」闭环的数据来源（见 /ingest）。
        """
        url = pdf_url(result)
        source = result.get("source")
        if not url:
            return (
                {
                    "source": source,
                    "downloaded": False,
                    "pdf_url": None,
                    "filename": None,
                    "file_size": 0,
                    "error": "暂无直接 PDF 下载地址（PubMed 需经 PMC/DOI 跳转），已降级",
                },
                None,
            )
        try:
            data = _http_get_bytes(url)
            arxiv_id = str(result.get("arxiv_id") or "").strip()
            meta = {
                "source": source,
                "downloaded": True,
                "pdf_url": url,
                "filename": f"{arxiv_id}.pdf" if arxiv_id else "paper.pdf",
                "file_size": len(data),
            }
            return meta, data
        except Exception as e:  # noqa: BLE001
            return (
                {
                    "source": source,
                    "downloaded": False,
                    "pdf_url": url,
                    "filename": None,
                    "file_size": 0,
                    "error": str(e),
                },
                None,
            )

    def register_tracking(
        self, query: str, source: str = "arxiv", interval_days: int = 7
    ) -> dict[str, Any]:
        """注册领域论文追踪（内存态）。返回值即注册记录。"""
        tracking_id = uuid.uuid4().hex[:12]
        record = {
            "id": tracking_id,
            "query": query,
            "source": source,
            "interval_days": interval_days,
            "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        }
        self._tracking[tracking_id] = record
        return record

    def list_tracking(self) -> dict[str, Any]:
        """列出当前内存态追踪注册表。"""
        return {
            "backend": "builtin",
            "count": len(self._tracking),
            "items": list(self._tracking.values()),
        }

    def mark_seen(self, tracking_id: str, result: dict[str, Any]) -> None:
        """记录某追踪下已见过的论文（内存态已见集合，供单进程演示）。"""
        seen = self._tracking.get(tracking_id, {}).setdefault("_seen", set())
        title = (result.get("title") or "").strip()
        if title:
            seen.add(title)


# 全局单例
paper_retrieval_service = PaperRetrievalService()
