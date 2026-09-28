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
                "chunk_index": (
                    int(c["chunk_index"]) if c.get("chunk_index") is not None else None
                ),
                "snippet": str(snippet)[:300],
                "score": round(float(c.get("score") or 0.0), 4),
            }
        )
    anchors.sort(key=lambda x: (x["score"], x["document_id"]), reverse=True)
    return anchors


def _fold_whitespace(text: str) -> str:
    """空白折叠：把任意连续空白折叠为单个空格，用于宽松子串匹配。"""
    return " ".join(str(text).split())


def _match_prefix48(snip_norm: str, page_norm: str) -> str | None:
    """前 48 字符包含匹配。"""
    prefix48 = snip_norm[:48]
    return prefix48 if prefix48 and prefix48 in page_norm else None


def _match_endswith(snip_norm: str, page_norm: str) -> str | None:
    """末尾匹配。"""
    return snip_norm if snip_norm and page_norm.endswith(snip_norm) else None


def _match_prefix40(snip_norm: str, page_norm: str) -> str | None:
    """前 40 字符包含匹配。"""
    prefix40 = snip_norm[:40]
    return prefix40 if prefix40 and prefix40 in page_norm else None


_SNIPPET_MATCHERS = (_match_prefix48, _match_endswith, _match_prefix40)


def _find_best_page(snippet: str, pages: list[dict[str, Any]]) -> tuple[Any, bool]:
    """逐页匹配 + 三种命中条件 + 选最长片段，返回 (best_page_no, has_any_text)。"""
    snip_norm = _fold_whitespace(snippet)
    best_page_no: Any = None
    best_len = -1
    has_any_text = False
    for p in pages:
        page_text = str(p.get("text") or "")
        if not page_text:
            continue
        has_any_text = True
        page_norm = _fold_whitespace(page_text)
        hit: str | None = None
        for matcher in _SNIPPET_MATCHERS:
            hit = matcher(snip_norm, page_norm)
            if hit:
                break
        if hit and len(hit) > best_len:
            best_len = len(hit)
            best_page_no = p.get("page_number")
    return best_page_no, has_any_text


def backfill_page_numbers(anchors: list[dict[str, Any]], pages_lookup: dict) -> dict[str, Any]:
    """依据页级全文做 chunk→page 的页级定位回填（步骤15【P2】）。

    anchors: list[{document_id, page_number?, chunk_index?, snippet?, score?}]
    pages_lookup: dict[document_id -> list[{page_number:int, text:str}]]（缺省 {}）

    确定性规则（不编造）：
    - 锚点已写死非 None 整数 page_number → 保留，不覆盖；
    - 否则 snippet 非空且 pages 非空：对每页用「宽松包含」逐页匹配合片段，
      选含最长连续片段的一页取 page_number；若所有页文本均为空字符串，
      回退到第一页的 page_number；
    - pages 为空或 snippet 为空 → 保持 None。

    宽松包含（保持简单）：
        prefix48 = snippet 前 48 个空白折叠字符
        命中即算：snip_norm[:48] in page_norm 或 page_norm.endswith(snip_norm)
                 或 snip_norm[:40] in page_norm

    返回 {"anchors": 更新后的锚点(附加 page_number 字段), "backfilled_count": int}
    """
    pages_lookup = pages_lookup or {}
    updated: list[dict[str, Any]] = []
    backfilled_count = 0
    for anchor in anchors or []:
        a = dict(anchor)
        cur = a.get("page_number")
        if isinstance(cur, int) and not isinstance(cur, bool):
            updated.append(a)
            continue
        doc_id = str(a.get("document_id") or "")
        pages = pages_lookup.get(doc_id) or []
        snippet = str(a.get("snippet") or "")
        if snippet and pages:
            best_page_no, has_any_text = _find_best_page(snippet, pages)
            if best_page_no is not None:
                a["page_number"] = int(best_page_no)
                backfilled_count += 1
            elif not has_any_text and pages:
                # 所有页文本均为空：回退第一页页码（页面本身存在）
                a["page_number"] = int(pages[0].get("page_number"))
        else:
            a["page_number"] = None
        updated.append(a)
    return {"anchors": updated, "backfilled_count": backfilled_count}


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
            {
                "document_id": r["document_id"],
                "title": r["title"],
                "best_score": r["score"],
            },
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

    def backfill(self, anchors: list[dict[str, Any]], pages_lookup: dict) -> dict[str, Any]:
        """页级定位回填：直接调用纯函数 backfill_page_numbers（供 API 编排与直测）。"""
        return backfill_page_numbers(anchors, pages_lookup)

    def compare(
        self, chunks_by_doc: list[dict[str, Any]], question: str, use_llm: bool = True
    ) -> dict[str, Any]:
        return multi_document_compare(chunks_by_doc, question, use_llm=use_llm)


# 全局单例
source_anchor_service = SourceAnchorService()
