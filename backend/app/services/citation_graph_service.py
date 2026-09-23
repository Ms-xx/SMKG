# -*- coding: utf-8 -*-
"""
引用图谱挖掘与综述服务（对应 XiangMu 10.2 模块五）

职责：
1. 引用网络建图：从结构化参考文献按 title/doi 匹配建节点与 CITES 边；
2. 基石节点挖掘：PageRank + 介数中心性（自实现，零依赖）；
3. 自动综述：规则模板（按主题聚合 + 时间线）；
4. Future Work 去重：simhash/minhash 相似聚合。

依赖策略（可插拔、可降级）：
- 纯 Python 实现，零第三方依赖，永远可用；
- 真实 LLM 综述生成预留，未接入时降级规则模板。
"""
from __future__ import annotations

import json
import re
import urllib.request
from typing import Any

from loguru import logger

from app.core.config import settings
from app.services.deduplication_service import simhash_similarity


def _paper_key(ref: dict[str, Any]) -> str:
    doi = (ref.get("doi") or "").strip().lower()
    if doi:
        return f"doi:{doi}"
    title = re.sub(r"[^a-z0-9]+", "", (ref.get("title") or "").lower())
    return f"title:{title}" if title else f"idx:{ref.get('index')}"


def build_citation_network(references: list[dict[str, Any]]) -> dict[str, Any]:
    """每篇参考文献一个节点；同 key 去重；CITES 边基于共享作者/主题启发式（零元数据时为空图）。"""
    nodes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in references or []:
        key = _paper_key(r)
        if not key or key in seen:
            continue
        seen.add(key)
        nodes.append(
            {
                "id": key,
                "label": (r.get("title") or f"参考文献 {r.get('index')}")[:60],
                "year": r.get("year"),
                "doi": r.get("doi"),
                "ref_index": r.get("index"),
            }
        )

    edges: list[dict[str, Any]] = []
    # 观测到相同「作者 + 期刊」组合时建立弱连接（启发式共现）
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            a, b = nodes[i], nodes[j]
            if a["year"] and b["year"] and a["year"] == b["year"]:
                continue
            # 简化：标题 n-gram 高度相似则视为同主题弱连接
            if simhash_similarity(a["label"], b["label"]) >= 0.82:
                edges.append({"source": a["id"], "target": b["id"], "type": "TOPIC"})

    return {
        "backend": "builtin",
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
    }


def page_rank(
    graph: dict[str, Any], damping: float = 0.85, iterations: int = 100
) -> dict[str, float]:
    nodes = [n["id"] for n in graph.get("nodes", [])]
    edges = graph.get("edges", [])
    out_deg: dict[str, int] = dict.fromkeys(nodes, 0)
    for e in edges:
        out_deg[e["source"]] = out_deg.get(e["source"], 0) + 1
    n = len(nodes)
    if n == 0:
        return {}
    rank = dict.fromkeys(nodes, 1.0 / n)
    for _ in range(iterations):
        # 悬挂节点（无出边）质量均匀再分配，保证总得分守恒
        dangling = sum(rank[nv] for nv in nodes if out_deg[nv] == 0)
        new_rank = dict.fromkeys(nodes, (1 - damping) / n + damping * dangling / n)
        for e in edges:
            src, dst = e["source"], e["target"]
            if out_deg.get(src, 0) > 0:
                new_rank[dst] = new_rank.get(dst, 0.0) + damping * rank[src] / out_deg[src]
        rank = new_rank
    return rank


def betweenness_centrality(graph: dict[str, Any]) -> dict[str, float]:
    """未加权 Brandes 介数中心性，纯 Python。"""
    nodes = graph.get("nodes", [])
    node_ids = {n["id"] for n in nodes}
    adj: dict[str, list[str]] = {n: [] for n in node_ids}
    for e in graph.get("edges", []):
        if e["source"] in adj and e["target"] in adj:
            adj[e["source"]].append(e["target"])
            adj[e["target"]].append(e["source"])
    cb = dict.fromkeys(node_ids, 0.0)
    for s in node_ids:
        stack: list[str] = []
        pred: dict[str, list[str]] = {n: [] for n in node_ids}
        dist = dict.fromkeys(node_ids, -1)
        sigma = dict.fromkeys(node_ids, 0)
        dist[s] = 0
        sigma[s] = 1
        queue = [s]
        while queue:
            v = queue.pop(0)
            stack.append(v)
            for w in adj[v]:
                if dist[w] < 0:
                    dist[w] = dist[v] + 1
                    queue.append(w)
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    pred[w].append(v)
        delta = dict.fromkeys(node_ids, 0.0)
        while stack:
            w = stack.pop()
            for v in pred[w]:
                delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w]) if sigma[w] else 0.0
            if w != s:
                cb[w] += delta[w]
    if len(node_ids) > 2:
        norm = 2.0 / ((len(node_ids) - 1) * (len(node_ids) - 2))
        cb = {k: v * norm for k, v in cb.items()}
    return cb


def key_papers(graph: dict[str, Any]) -> dict[str, Any]:
    pr = page_rank(graph)
    bc = betweenness_centrality(graph)
    nodes = graph.get("nodes", [])
    by_id = {n["id"]: n for n in nodes}
    ranked = sorted(
        pr.items(),
        key=lambda kv: (kv[1], bc.get(kv[0], 0.0)),
        reverse=True,
    )
    result = []
    for node_id, rank in ranked:
        result.append(
            {
                "id": node_id,
                "label": by_id.get(node_id, {}).get("label"),
                "year": by_id.get(node_id, {}).get("year"),
                "page_rank": round(rank, 6),
                "betweenness": round(bc.get(node_id, 0.0), 6),
            }
        )
    return {"backend": "builtin", "key_papers": result}


def _llm_chat_completion(
    endpoint: str, model: str, messages: list[dict[str, str]], timeout: float
) -> str:
    """调用 OpenAI 兼容 /v1/chat/completions 生成综述正文，失败抛异常由调用方降级。"""
    url = endpoint.rstrip("/") + "/chat/completions"
    payload = json.dumps(
        {"model": model, "messages": messages, "temperature": 0.3}
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    return (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""


def generate_survey(
    references: list[dict[str, Any]], top_papers: list[dict[str, Any]]
) -> dict[str, Any]:
    """领域综述：配置 LLM 时用真实 LLM 生成；否则降级规则模板。"""
    years = sorted({r.get("year") for r in references or [] if r.get("year")})
    top_titles = [p.get("label") for p in (top_papers or [])[:5] if p.get("label")]
    timeline = [
        {"year": y, "count": sum(1 for r in references or [] if r.get("year") == y)} for y in years
    ]

    ref_brief = [
        (
            f"- [{r.get('index') or i}] ({r.get('year') or 'N/A'}) {r.get('title') or ''}"
            + (f" 作者：{', '.join(r.get('authors') or [])}" if r.get("authors") else "")
        )
        for i, r in enumerate(references or [])
    ]
    key_brief = "\n".join(
        f"- {t}" for t in top_titles
    ) or "（无）"
    prompt = (
        "请基于下面给出的参考文献列表撰写一段中文学术领域综述（3-5 句），"
        "概述该领域的研究脉络、技术路线与代表性工作。不得编造参考文献中不存在的观点；"
        "只输出综述正文，不要前缀。\n\n"
        f"参考文献（{len(references or [])} 篇）：\n" + "\n".join(ref_brief) + "\n\n"
        f"代表性基石文献：\n{key_brief}"
    )

    if settings.LLM_ENABLED and settings.LLM_ENDPOINT:
        try:
            text = _llm_chat_completion(
                settings.LLM_ENDPOINT,
                settings.LLM_MODEL,
                [
                    {
                        "role": "system",
                        "content": "你是科学文献综述助手。依据给定参考文献，给出严谨、不编造、结构清晰的领域综述。",
                    },
                    {"role": "user", "content": prompt},
                ],
                settings.LLM_TIMEOUT,
            ).strip()
            if text:
                return {
                    "backend": "llm",
                    "model": settings.LLM_MODEL,
                    "reference_count": len(references or []),
                    "timeline": timeline,
                    "top_papers": top_titles,
                    "survey": text,
                }
            logger.warning("LLM 综述返回空，降级规则模板")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"LLM 综述不可用，降级规则模板: {e}")

    text = (
        f"领域综述（规则模板）：共 {len(references or [])} 篇参考文献，"
        f"覆盖年限 {years[0] if years else 'N/A'}–{years[-1] if years else 'N/A'}。"
        + (f"基石文献：{'; '.join(top_titles)}。" if top_titles else "暂无可识别基石文献。")
        + "（LLM 综述能力未接入或调用失败，已降级为规则模板。）"
    )
    return {
        "backend": "rule",
        "reference_count": len(references or []),
        "timeline": timeline,
        "top_papers": top_titles,
        "survey": text,
    }


def deduplicate_future_work(chunks: list[str], threshold: float = 0.85) -> dict[str, Any]:
    """Future Work 片段相似去重：simhash 相似度贪心聚合。"""
    groups: list[list[str]] = []
    representatives: list[str] = []
    for c in chunks or []:
        matched = False
        for i, rep in enumerate(representatives):
            if simhash_similarity(rep, c) >= threshold:
                groups[i].append(c)
                matched = True
                break
        if not matched:
            representatives.append(c)
            groups.append([c])
    unique = [g[0] for g in groups]
    return {
        "backend": "simhash",
        "threshold": threshold,
        "input_count": len(chunks or []),
        "unique_count": len(unique),
        "unique": unique,
    }


class CitationGraphService:
    @property
    def available(self) -> bool:
        return settings.CITATION_GRAPH_ENABLED

    def network(self, references: list[dict[str, Any]]) -> dict[str, Any]:
        return build_citation_network(references)

    def key_papers(self, graph: dict[str, Any]) -> dict[str, Any]:
        return key_papers(graph)

    def survey(
        self, references: list[dict[str, Any]], top_papers: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        graph = build_citation_network(references)
        kp = key_papers(graph).get("key_papers", []) if not top_papers else top_papers
        return generate_survey(references, kp)

    def deduplicate_future_work(self, chunks: list[str]) -> dict[str, Any]:
        return deduplicate_future_work(chunks)


# 全局单例
citation_graph_service = CitationGraphService()
