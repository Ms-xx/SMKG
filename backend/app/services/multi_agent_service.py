# -*- coding: utf-8 -*-
"""
多 Agent 协作与冲突解决（步骤 9）：LLM 多智能体编排（科研助手方向）。

协调器（Coordinator）把任务分派给多个专用智能体：
- parse（文献解析 Agent）：结构 / 关键词 / 公式检测；
- extract（信息抽取 Agent）：实体抽取；
- qa（问答 Agent）：回答问题；
- summarize（综述 Agent）：提炼总结。

各 Agent 独立产出后，协调器做冲突解决（投票 / 合并 / 仲裁），输出最终结论、
每个 Agent 的独立结果与冲突明细。

依赖策略：
- 纯 Python 零依赖编排（不依赖 langchain/langgraph），永远可用；
- 每个 Agent 的生成后端可切换：builtin（规则模板，确定性、零依赖）| llm（可插拔 LLM
  回调，预留，可接入 GraphRAGTest/LM Studio 或任意 OpenAI 兼容接口）；LLM 不可用时
  自动降级 builtin；
- 会话默认进程内内存注册表，可用 MULTI_AGENT_STORE_PATH 指定 JSON 文件持久化。
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from collections import Counter
from typing import Any, Callable

from loguru import logger

from app.core.config import settings

# 智能体标识
AGENT_PARSE = "parse"
AGENT_EXTRACT = "extract"
AGENT_QA = "qa"
AGENT_SUMMARIZE = "summarize"

# 智能体描述注册表（顺序即默认参与顺序）
AGENT_REGISTRY: list[dict[str, str]] = [
    {"name": AGENT_PARSE, "description": "文献解析：结构、关键词、公式检测", "kind": "text"},
    {"name": AGENT_EXTRACT, "description": "信息抽取：实体抽取", "kind": "items"},
    {"name": AGENT_QA, "description": "问答：基于规则模板生成答案", "kind": "text"},
    {"name": AGENT_SUMMARIZE, "description": "综述：提炼核心内容", "kind": "text"},
]

RESOLUTION_MODES = ("vote", "merge", "arbitrate")

# LLM 生成回调（可插拔；默认 None = 使用 builtin 规则模板）
_llm_complete: Callable[[str], str] | None = None


def set_llm_backend(callback: Callable[[str], str] | None) -> None:
    """注入 LLM 生成回调；传 None 时关闭 LLM，回退 builtin 规则模板。"""
    global _llm_complete
    _llm_complete = callback


# ── 规则模板（builtin 后端，确定性）──────────────────────────────
_WORD_RE = re.compile(r"[\w\u4e00-\u9fff][\w\u4e00-\u9fff-]*")


def _tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text or "")


def _summary_first_sentences(text: str, n: int = 2) -> str:
    sentences = [s.strip() for s in re.split(r"[。！？!?]+", text or "") if s.strip()]
    selected = sentences[:n]
    return "。".join(selected) + ("。" if selected else "")


def _parse_fallback(text: str) -> dict[str, Any]:
    tokens = _tokenize(text)
    has_formula = bool(re.search(r"\$[^$]+\$|\\[a-zA-Z]+", text or ""))
    return {
        "word_count": len(tokens),
        "has_formula": has_formula,
        "keywords": tokens[:10],
        "content": f"该文本共 {len(tokens)} 词" + ("，含公式" if has_formula else "") + "。",
    }


# 中文领域关键词 → 实体类型（规则兜底）
_MATERIAL_KEYWORDS: dict[str, str] = {
    "钙钛矿": "Material",
    "石墨烯": "Material",
    "量子点": "Material",
    "太阳能电池": "Device",
    "高效率": "Property",
    "制备方法": "Method",
}


def _extract_fallback(text: str) -> dict[str, Any]:
    """规则抽取：英文专有名词 + 中文领域关键词 → 实体列表（可降级）。"""
    entities: list[dict[str, Any]] = []
    seen: set[str] = set()
    for m in re.finditer(r"\b[A-Z][a-z]+(?:[- ][A-Z][a-z]+)*\b", text or ""):
        name = m.group(0)
        key = name.lower()
        if len(name) > 2 and key not in seen:
            seen.add(key)
            entities.append({"text": name, "type": "ENTITY", "confidence": 0.7})
    for kw, typ in _MATERIAL_KEYWORDS.items():
        if kw in (text or "") and kw not in seen:
            seen.add(kw)
            entities.append({"text": kw, "type": typ, "confidence": 0.85})
    return {
        "items": entities,
        "content": f"抽取到 {len(entities)} 个实体。",
    }


def _qa_fallback(query: str) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {"content": "（空问题）"}
    if any(k in q for k in ("什么", "定义", "是")):
        return {"content": f"关于「{q}」：规则模板确定性回答（LLM 后端可插拔替换）。"}
    if any(k in q for k in ("多少", "数量", "几个", "统计")):
        return {"content": "数量类问题：请结合知识图谱统计结果（规则模板）。"}
    return {"content": f"已收到问题「{q}」，规则模板兜底回答。"}


def _summarize_fallback(text: str) -> dict[str, Any]:
    return {"content": _summary_first_sentences(text) or "（无法生成摘要）", "confidence": 0.6}


_FALLBACKS: dict[str, Callable[[str], dict[str, Any]]] = {
    AGENT_PARSE: _parse_fallback,
    AGENT_EXTRACT: _extract_fallback,
    AGENT_QA: _qa_fallback,
    AGENT_SUMMARIZE: _summarize_fallback,
}


def _generate(agent: str, text: str) -> dict[str, Any]:
    """生成单个 Agent 的结果：LLM 可用则用 LLM，否则规则模板降级。"""
    use_llm = settings.MULTI_AGENT_BACKEND == "llm" and _llm_complete is not None
    if use_llm:
        try:
            out = _llm_complete(f"[{agent}] 任务输入：{(text or '')[:2000]}")
            if out:
                return {"content": str(out), "backend": "llm", "confidence": 0.8}
        except Exception as exc:  # pragma: no cover - LLM 调用异常降级
            logger.warning(f"多 Agent LLM 调用失败，降级规则模板：{exc}")
    result = _FALLBACKS[agent](text or "")
    result.setdefault("confidence", 0.9 if agent != AGENT_SUMMARIZE else 0.6)
    result["backend"] = "builtin"
    return result


# ── 冲突解决（投票 / 合并 / 仲裁）────────────────────────────────
def _normalize_text(s: str) -> str:
    return (s or "").strip().lower()


def _resolve_answers(answers: list[dict[str, Any]], mode: str) -> tuple[str | None, list[dict]]:
    """对文本类答案做冲突解决，返回 (final_text, unresolved)。"""
    if not answers:
        return None, []

    totals: dict[str, int] = {}
    for p in answers:
        key = _normalize_text(p.get("content", ""))
        totals[key] = totals.get(key, 0) + 1

    if mode == "merge":
        seen: list[str] = []
        parts: list[str] = []
        for p in answers:
            key = _normalize_text(p.get("content", ""))
            if key not in seen:
                seen.append(key)
                parts.append(p.get("content", ""))
        return "；".join(parts), []

    if mode == "arbitrate":
        best = max(answers, key=lambda p: p.get("confidence", 0.0))
        top_conf = best.get("confidence", 0.0)
        rivals = [
            p
            for p in answers
            if _normalize_text(p.get("content", "")) != _normalize_text(best.get("content", ""))
            and p.get("confidence", 0.0) == top_conf
        ]
        unresolved = (
            [
                {
                    "type": "arbitrate_tie",
                    "description": "多个 Agent 置信度相同且答案不同，仲裁无法唯一确定",
                }
            ]
            if rivals
            else []
        )
        return best.get("content"), unresolved

    # vote：多数票决；平票时返回首个出现且票数最高者，标记 unresolved
    top_count = max(totals.values())
    winners = [k for k, c in totals.items() if c == top_count]
    final = None
    for p in answers:
        if _normalize_text(p.get("content", "")) in winners:
            final = p.get("content")
            break
    unresolved = (
        [{"type": "vote_tie", "description": "出现平票，投票结果随机取首个"}]
        if len(winners) > 1
        else []
    )
    return final, unresolved


def _resolve_items(
    sources: list[dict[str, Any]], mode: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """对列表类（实体）产出做冲突解决，返回 (items, conflicts)。"""
    by_text: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for src in sources:
        base_conf = src.get("confidence", 0.5)
        for it in src.get("items") or []:
            txt = _normalize_text(str(it.get("text", "")))
            if not txt:
                continue
            if txt not in by_text:
                by_text[txt] = []
                order.append(txt)
            by_text[txt].append(
                {
                    "type": str(it.get("type", "")),
                    "agent": src.get("agent", ""),
                    "confidence": it.get("confidence", base_conf),
                }
            )

    items: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for txt in order:
        recs = by_text[txt]
        types = [r["type"] for r in recs]
        uniq_types = list(dict.fromkeys(types))
        if len(uniq_types) > 1:
            conflicts.append(
                {
                    "type": "entity_type",
                    "text": txt,
                    "types": uniq_types,
                    "agents": list(dict.fromkeys(r["agent"] for r in recs)),
                    "description": f"实体「{txt}」被标注为多种类型：{'/'.join(uniq_types)}",
                }
            )
            if mode == "vote":
                chosen = Counter(types).most_common(1)[0][0]
                items.append({"text": txt, "type": chosen})
            elif mode == "arbitrate":
                best = max(recs, key=lambda r: r.get("confidence", 0.0))
                items.append({"text": txt, "type": best["type"]})
            else:  # merge：保留全部类型（去重）
                for t in uniq_types:
                    items.append({"text": txt, "type": t})
        else:
            items.append({"text": txt, "type": uniq_types[0]})
    return items, conflicts


def resolve_conflicts(proposals: list[dict[str, Any]], mode: str = "merge") -> dict[str, Any]:
    """对多个 Agent 的产出做冲突检测与解决（纯函数，可独立调用）。

    proposals[i] = {"agent", "content", "items", "confidence"}
    mode: vote | merge | arbitrate
    """
    mode = mode if mode in RESOLUTION_MODES else "merge"
    valid = [p for p in proposals if p]
    answers: list[dict[str, Any]] = []
    item_sources: list[dict[str, Any]] = []
    for p in valid:
        if p.get("items"):
            item_sources.append(p)
        elif p.get("content"):
            answers.append(p)

    conflicts: list[dict[str, Any]] = []

    # 文本答案冲突：多个 Agent 给出不同答案
    if answers:
        distinct: dict[str, list[str]] = {}
        for p in answers:
            distinct.setdefault(_normalize_text(p.get("content", "")), []).append(p["agent"])
        if len(distinct) > 1:
            conflicts.append(
                {
                    "type": "answer",
                    "agents": [p["agent"] for p in answers],
                    "description": f"{len(distinct)} 个不同答案",
                    "answers": [
                        {
                            "agent": p["agent"],
                            "answer": p.get("content"),
                            "confidence": p.get("confidence", 0.5),
                        }
                        for p in answers
                    ],
                }
            )

    final_text, unresolved = _resolve_answers(answers, mode)
    final_items, item_conflicts = _resolve_items(item_sources, mode)
    conflicts.extend(item_conflicts)

    return {
        "mode": mode,
        "conflicts": conflicts,
        "final_text": final_text,
        "final_items": final_items,
        "unresolved": unresolved,
        "participants": [p.get("agent") for p in valid],
    }


# ── 会话存储 ─────────────────────────────────────────────────────
class _SessionStore:
    """进程内会话注册表，线程安全，可 JSON 持久化（与 A/B 测试一致）。"""

    def __init__(self, path: str | None = None):
        self._lock = threading.Lock()
        self._sessions: dict[str, dict[str, Any]] = {}
        self._path = path
        if path:
            self._load()

    def _load(self) -> None:
        if not self._path or not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                self._sessions = json.load(f).get("sessions", {})
        except (OSError, ValueError) as exc:
            logger.warning(f"多 Agent 会话注册表加载失败，降级为空：{exc}")

    def _save(self) -> None:
        if not self._path:
            return
        try:
            os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump({"sessions": self._sessions}, f, ensure_ascii=False, default=str)
        except OSError as exc:
            logger.warning(f"多 Agent 会话注册表持久化失败：{exc}")

    def add(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._sessions[record["session_id"]] = record
            self._save()
        return dict(record)

    def get(self, session_id: str) -> dict[str, Any] | None:
        with self._lock:
            rec = self._sessions.get(session_id)
            return dict(rec) if rec else None

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self._sessions.values()]


class MultiAgentService:
    """多 Agent 协作门面：分派 → 生成 → 冲突解决 → 归档会话。可插拔可降级。"""

    def __init__(self) -> None:
        self._store = _SessionStore(settings.MULTI_AGENT_STORE_PATH or None)

    @property
    def available(self) -> bool:
        return settings.MULTI_AGENT_ENABLED

    def list_agents(self) -> list[dict[str, str]]:
        return [dict(a) for a in AGENT_REGISTRY]

    def run(
        self,
        query: str,
        context: str = "",
        agents: list[str] | None = None,
        mode: str = "merge",
    ) -> dict[str, Any]:
        """协调器：把任务分派给选定 Agent，汇总产出并做冲突解决。"""
        known = [a["name"] for a in AGENT_REGISTRY]
        selected = [a for a in (agents or []) if a in known] or known

        # 各 Agent 的输入：qa 用问题，其余优先用上下文文本
        inputs = {
            AGENT_QA: query,
            AGENT_PARSE: context or query,
            AGENT_EXTRACT: context or query,
            AGENT_SUMMARIZE: context or query,
        }

        agent_results: list[dict[str, Any]] = []
        for ag in selected:
            desc = next((a for a in AGENT_REGISTRY if a["name"] == ag), None)
            gen = _generate(ag, inputs.get(ag, query))
            agent_results.append(
                {
                    "agent": ag,
                    "description": desc["description"] if desc else ag,
                    "content": gen.get("content", ""),
                    "items": gen.get("items"),
                    "confidence": gen.get("confidence", 0.5),
                    "backend": gen.get("backend", "builtin"),
                }
            )

        resolved = resolve_conflicts(agent_results, mode)
        session = {
            "session_id": f"ma-{len(self._store.list()) + 1:04d}",
            "query": query,
            "mode": mode,
            "backend": settings.MULTI_AGENT_BACKEND,
            "agents": selected,
            "agent_results": agent_results,
            "conflicts": resolved["conflicts"],
            "resolution": {
                "mode": mode,
                "final_text": resolved["final_text"],
                "final_items": resolved["final_items"],
                "unresolved": resolved["unresolved"],
            },
            "created_at": time.time(),
        }
        return self._store.add(session)

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        return self._store.get(session_id)

    def list_sessions(self) -> list[dict[str, Any]]:
        return self._store.list()


# 全局单例（懒加载，构造时不做计算）
multi_agent_service = MultiAgentService()
