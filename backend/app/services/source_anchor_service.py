# -*- coding: utf-8 -*-
"""
抗幻觉溯源与多文对比服务（对应 XiangMu 10.2 模块二）

职责：
1. 溯源锚点：从带来源元数据（document_id / page_number / snippet）的分块里，
   生成可用于前端跳转的出处锚点列表；
2. 多文对比：跨文档聚合候选分块，按关键词打分排序并输出「主题/时间线」对比框架。

依赖策略（可插拔、可降级）：
- 纯 Python 零依赖，永远可用；
- 关键字打分复用 semantic_search_service.keyword_score，缺 LLM 时对比结论降级为规则模板；
  与 GraphRAGTest /query 的真实接入（需 8001 服务返回带来源元数据的 context）预留为可选。
"""
from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.services.semantic_search_service import keyword_score


def extract_anchors(context_chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    context_chunks 形如:
        {"document_id": "...", "page_number": 3, "snippet": "...", "score": 0.8}

    仅保留含来源定位信息的块，输出规范化锚点。
    """
    anchors: list[dict[str, Any]] = []
    for c in context_chunks or []:
        doc_id = c.get("document_id") or c.get("doc_id")
        page = c.get("page_number") or c.get("page")
        snippet = c.get("snippet") or c.get("text") or ""
        if doc_id is None:
            continue
        anchors.append(
            {
                "document_id": str(doc_id),
                "page_number": int(page) if page is not None else None,
                "snippet": str(snippet)[:300],
                "score": round(float(c.get("score") or 0.0), 4),
            }
        )
    anchors.sort(key=lambda x: (x["score"], x["document_id"]), reverse=True)
    return anchors


def multi_document_compare(chunks_by_doc: list[dict[str, Any]], question: str) -> dict[str, Any]:
    """
    chunks_by_doc 形如:
        {"document_id": "...", "title": "...", "chunks": ["...", ...]}
    """
    rows: list[dict[str, Any]] = []
    for doc in chunks_by_doc or []:
        doc_id = str(doc.get("document_id") or doc.get("id") or "")
        title = doc.get("title") or doc_id
        for chunk in doc.get("chunks") or []:
            text = str(chunk)
            rows.append(
                {
                    "document_id": doc_id,
                    "title": title,
                    "snippet": text[:300],
                    "score": round(keyword_score(question, text), 4),
                }
            )
    rows.sort(key=lambda x: x["score"], reverse=True)

    # 时间线/主题分组：按文档聚合，取每篇最高分块代表该文档视角
    by_doc: dict[str, dict[str, Any]] = {}
    for r in rows:
        entry = by_doc.setdefault(
            r["document_id"],
            {"document_id": r["document_id"], "title": r["title"], "best_score": r["score"]},
        )
        if r["score"] > entry["best_score"]:
            entry["best_score"] = r["score"]
    perspective = sorted(by_doc.values(), key=lambda x: x["best_score"], reverse=True)

    conclusion = (
        f"基于 {len(rows)} 个候选分块、{len(perspective)} 篇文献的规则化对比："
        f"最相关来源为「{perspective[0]['title'] if perspective else '无'}」。"
        "（LLM 生成对比结论的能力预留，未接入时输出此规则模板。）"
    )

    return {
        "backend": "builtin",
        "question": question,
        "candidate_count": len(rows),
        "perspectives": perspective,
        "top_chunks": rows[:10],
        "conclusion": conclusion,
    }


class SourceAnchorService:
    @property
    def available(self) -> bool:
        return settings.SOURCE_ANCHOR_ENABLED

    def anchors(self, context_chunks: list[dict[str, Any]]) -> dict[str, Any]:
        return {"backend": "builtin", "anchors": extract_anchors(context_chunks)}

    def compare(self, chunks_by_doc: list[dict[str, Any]], question: str) -> dict[str, Any]:
        return multi_document_compare(chunks_by_doc, question)


# 全局单例
source_anchor_service = SourceAnchorService()
