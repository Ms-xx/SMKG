# -*- coding: utf-8 -*-
"""
抗幻觉溯源与多文对比服务（对应 XiangMu 10.2 模块二）

职责：
1. 溯源锚点：从带来源元数据（document_id / page_number / snippet）的分块里，
   生成可用于前端跳转的出处锚点列表；
2. 从 GraphRAGTest(8001) 拉取真实来源：`anchors_from_rag` 复用 `graphrag_integration.rag_query`
   返回的 `sources`，转为真实出处锚点（backend=rag）；
3. 多文对比：跨文档聚合候选分块，按关键词打分排序并输出「主题/时间线」对比框架，
   配置 LLM 时用真实 LLM 生成对比结论（backend=llm）。

依赖策略（可插拔、可降级）：
- 纯 Python 零依赖，永远可用；
- 关键字打分复用 semantic_search_service.keyword_score；
- LLM 对比结论复用 OpenAI 兼容端点，未配置/失败自动降级规则模板；
- GraphRAGTest(8001) 不可达或无数来源时，`anchors_from_rag` 降级返回空锚点并标注 note。
"""
from __future__ import annotations

import json
import urllib.request
from typing import Any

from loguru import logger

from app.core.config import settings
from app.services.semantic_search_service import keyword_score


def _llm_chat_completion(
    endpoint: str, model: str, messages: list[dict[str, str]], timeout: float
) -> str:
    """调用 OpenAI 兼容 /v1/chat/completions 生成对比结论，失败抛异常由调用方降级。"""
    url = endpoint.rstrip("/") + "/chat/completions"
    payload = json.dumps({"model": model, "messages": messages, "temperature": 0.3}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    return (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""


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
                "chunk_index": int(c["chunk_index"]) if c.get("chunk_index") is not None else None,
                "snippet": str(snippet)[:300],
                "score": round(float(c.get("score") or 0.0), 4),
            }
        )
    anchors.sort(key=lambda x: (x["score"], x["document_id"]), reverse=True)
    return anchors


def anchors_from_rag(question: str) -> dict[str, Any]:
    """从 GraphRAGTest(8001) `/query` 的真实 `sources` 生成溯源锚点。

    8001 不可达 / 无数来源时降级：`backend="builtin"`，`anchors=[]`，附 note 说明。
    """
    from app.services.graphrag_integration import graphrag_integration

    try:
        result = graphrag_integration.rag_query(question, return_context=True, include_sources=True)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"GraphRAGTest 溯源拉取异常，降级空锚点: {e}")
        return {
            "backend": "builtin",
            "question": question,
            "anchors": [],
            "note": "GraphRAGTest(8001) 连接异常，无真实溯源锚点。",
        }

    if result.get("error"):
        return {
            "backend": "builtin",
            "question": question,
            "anchors": [],
            "note": f"GraphRAGTest 返回错误，无真实溯源锚点：{result.get('error')}",
        }

    sources = result.get("sources") or []
    if not sources:
        return {
            "backend": "builtin",
            "question": question,
            "anchors": [],
            "note": "GraphRAGTest 未检索到带来源的 chunk，请先经 /index/document 索引文档分块。",
        }

    anchors = extract_anchors(sources)
    return {
        "backend": "rag",
        "question": question,
        "anchor_count": len(anchors),
        "anchors": anchors,
    }


def multi_document_compare(
    chunks_by_doc: list[dict[str, Any]], question: str, use_llm: bool = True
) -> dict[str, Any]:
    """
    chunks_by_doc 形如:
        {"document_id": "...", "title": "...", "chunks": ["...", ...]}

    结论：配置 LLM 时用真实 LLM 生成对比结论（backend=llm），否则规则模板（backend=builtin）。
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

    conclusion = ""
    backend = "builtin"
    note = ""
    if use_llm and settings.LLM_ENABLED and settings.LLM_ENDPOINT:
        doc_brief = "\n".join(
            f"- 《{p['title']}》相关原文："
            + next(
                (r["snippet"] for r in rows if r["document_id"] == p["document_id"]),
                "（无）",
            )
            for p in perspective[:5]
        )
        prompt = (
            "请基于以下多篇文献的相关原文，撰写一段中文对比结论（3-5 句），"
            "指出各文献在该主题上的观点异同与研究脉络。不得编造原文不存在的内容；"
            f"只输出对比结论正文，不要前缀。\n\n研究问题：{question}\n\n" + doc_brief
        )
        try:
            conclusion = _llm_chat_completion(
                settings.LLM_ENDPOINT,
                settings.LLM_MODEL,
                [
                    {
                        "role": "system",
                        "content": "你是科学文献对比助手。依据给定文献原文，给出严谨、不编造的对比结论。",
                    },
                    {"role": "user", "content": prompt},
                ],
                settings.LLM_TIMEOUT,
            ).strip()
            if conclusion:
                backend = "llm"
                note = ""
        except Exception as e:  # noqa: BLE001
            logger.warning(f"LLM 对比结论不可用，降级规则模板: {e}")

    if not conclusion:
        conclusion = (
            f"基于 {len(rows)} 个候选分块、{len(perspective)} 篇文献的规则化对比："
            f"最相关来源为「{perspective[0]['title'] if perspective else '无'}」。"
            "（LLM 对比结论未接入或调用失败，已降级为规则模板。）"
        )
        note = note or "未配置 LLM 端点或调用失败，已降级为规则模板。"

    return {
        "backend": backend,
        "question": question,
        "candidate_count": len(rows),
        "perspectives": perspective,
        "top_chunks": rows[:10],
        "conclusion": conclusion,
        "note": note,
    }


class SourceAnchorService:
    @property
    def available(self) -> bool:
        return settings.SOURCE_ANCHOR_ENABLED

    def anchors(self, context_chunks: list[dict[str, Any]]) -> dict[str, Any]:
        return {"backend": "builtin", "anchors": extract_anchors(context_chunks)}

    def rag_anchors(self, question: str) -> dict[str, Any]:
        return anchors_from_rag(question)

    def compare(
        self, chunks_by_doc: list[dict[str, Any]], question: str, use_llm: bool = True
    ) -> dict[str, Any]:
        return multi_document_compare(chunks_by_doc, question, use_llm=use_llm)


# 全局单例
source_anchor_service = SourceAnchorService()
