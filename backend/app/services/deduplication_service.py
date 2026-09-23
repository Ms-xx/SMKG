# -*- coding: utf-8 -*-
"""
语义去重与版本管理服务（对应 XiangMu 10.2 模块一）

职责：
1. 语义指纹：char n-gram + SimHash（64bit），识别同源论文的不同版本（如 arXiv v1↔v7）；
2. 重复分组：基于指纹两两相似度（汉明距离）构建相似簇，给出「保留最新版本」建议；
3. 作者机构抽取：正则启发式提取 affiliation / 邮箱域名。

依赖策略（可插拔、可降级）：
- 纯 Python 实现（hashlib + re），零第三方依赖，永远可用；
- 指纹不依赖 numpy/向量模型，接口不变。
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from app.core.config import settings

_ARXIV_ID_RE = re.compile(r"\b(\d{4}\.\d{4,5})\s*(v\d{1,2})\b", re.IGNORECASE)

_AFFILIATION_HINTS = (
    "university",
    "univ.",
    "college",
    "institute",
    "laboratory",
    "lab.",
    "academy",
    "school",
    "department",
    "dept.",
    "center",
    "centre",
    "hospital",
    "大学",
    "学院",
    "研究院",
    "研究所",
    "实验室",
    "中心",
    "医院",
)


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", (text or "").lower())


def _ngrams(text: str, n: int = 3) -> list[str]:
    t = re.sub(r"\s+", " ", text or "").lower().strip()
    if not t:
        return []
    if len(t) < n:
        return [t]
    return [t[i : i + n] for i in range(len(t) - n + 1)]


def _simhash(text: str, n: int = 3) -> int:
    vector = [0] * 64
    for gram in _ngrams(text, n):
        digest = hashlib.md5(gram.encode("utf-8")).hexdigest()
        h = int(digest, 16)
        for i in range(64):
            vector[i] += 1 if (h >> i) & 1 else -1
    return sum((1 << i) for i, x in enumerate(vector) if x > 0)


def hamming_distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def simhash_similarity(a: str, b: str, n: int = 3) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return 1.0 - hamming_distance(_simhash(a, n), _simhash(b, n)) / 64.0


def extract_arxiv_version(title: str) -> dict[str, Any] | None:
    """从标题/文本识别 arXiv 编号与版本（如 1706.03762v7）。"""
    if not title:
        return None
    m = _ARXIV_ID_RE.search(title)
    if m:
        return {"arxiv_id": m.group(1), "version": m.group(2).lower()}
    m2 = re.search(r"arxiv\s*[:#]?\s*(\d{4}\.\d{4,5})", title, re.IGNORECASE)
    if m2:
        return {"arxiv_id": m2.group(1), "version": None}
    return None


def extract_affiliations(text: str) -> list[str]:
    """从作者/通讯信息文本中启发式抽取机构名与邮箱域名。"""
    if not text:
        return []
    hits: list[str] = []
    for line in re.split(r"[\n;；]", text or ""):
        line = line.strip()
        if not line:
            continue
        low = line.lower()
        if "@" in line:
            hits.extend(re.findall(r"@([\w.-]+)", line))
            continue
        if any(h in low for h in _AFFILIATION_HINTS) and len(line) <= 120:
            hits.append(line)
    seen: set[str] = set()
    out: list[str] = []
    for h in hits:
        k = h.lower()
        if k not in seen:
            seen.add(k)
            out.append(h)
    return out


class DeduplicationService:
    """语义去重服务：SimHash 指纹分组 + 版本建议 + 机构抽取（纯 Python 零依赖）。"""

    @property
    def available(self) -> bool:
        return settings.DEDUPLICATION_ENABLED

    def _fingerprint_text(self, doc: dict[str, Any]) -> str:
        return " ".join(str(doc.get(k) or "") for k in ("title", "abstract", "text"))[:2000]

    def detect(
        self, documents: list[dict[str, Any]], threshold: float | None = None
    ) -> dict[str, Any]:
        threshold = settings.DEDUP_THRESHOLD if threshold is None else threshold
        n = len(documents)
        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        fingerprints = [self._fingerprint_text(d) for d in documents]
        pairs: list[dict[str, Any]] = []
        for i in range(n):
            for j in range(i + 1, n):
                sim = simhash_similarity(fingerprints[i], fingerprints[j])
                if sim >= threshold:
                    union(i, j)
                    pairs.append(
                        {
                            "a_id": documents[i].get("id"),
                            "b_id": documents[j].get("id"),
                            "similarity": round(sim, 4),
                        }
                    )

        buckets: dict[int, list[int]] = {}
        for i in range(n):
            buckets.setdefault(find(i), []).append(i)

        clusters: list[dict[str, Any]] = []
        for members in buckets.values():
            if len(members) < 2:
                continue
            members.sort()
            cluster_docs = []
            keep = None
            keep_version = -1
            for idx in members:
                doc = documents[idx]
                info = extract_arxiv_version(str(doc.get("title") or ""))
                version_num = (
                    int(info["version"].lstrip("v")) if info and info.get("version") else 0
                )
                cluster_docs.append(
                    {
                        "id": doc.get("id"),
                        "title": doc.get("title"),
                        "version": info["version"] if info else None,
                    }
                )
                if version_num > keep_version:
                    keep_version = version_num
                    keep = doc.get("id")
            clusters.append(
                {
                    "size": len(members),
                    "document_ids": [documents[i].get("id") for i in members],
                    "documents": cluster_docs,
                    "suggestion": {
                        "keep": keep,
                        "reason": (
                            "同源版本中保留最新版本（arXiv 版本号最高）"
                            if keep_version > 0
                            else "语义相似度高于阈值，建议保留其一"
                        ),
                    },
                }
            )

        return {
            "backend": "simhash",
            "threshold": round(threshold, 4),
            "total_documents": n,
            "duplicate_pairs": pairs,
            "cluster_count": len(clusters),
            "clusters": clusters,
        }

    def affiliations(self, text: str) -> dict[str, Any]:
        return {"backend": "rule", "affiliations": extract_affiliations(text)}


# 全局单例
deduplication_service = DeduplicationService()
