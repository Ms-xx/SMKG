# -*- coding: utf-8 -*-
"""
跨文献结构化演进对比服务（步骤 19【P0】模块二）

职责：
在既有 `/source-anchor/compare`（多文档聚合 + LLM 自由文本结论）之上，新增
**维度化、可核查的对比矩阵**：行 = 演化维度（架构 / 参数量 / Context Window /
LayerNorm 位置 / 注意力类型 / 位置编码 …，默认 ≥ 6），列 = 论文；每个矩阵单元
**必须携带出处锚点**（document_id / page_number / chunk / 原文片段），
做到「无锚点不出结论」，杜绝 LLM 编造数值。

依赖策略（可插拔、可降级）：
- `build_compare_matrix` 为纯 Python 确定性函数，从文档结构化元数据 + 正文中
  按规则抽取维度值与锚点，永远可用、可复现；
- LLM 仅作可选的「维度洞察润色」增强路径（`enhance_insights`），未配置或失败时
  降级规则模板（backend=auto/rule），接口不报错。

锚点约定：一个矩阵单元 `anchors[]` 非空时才允许出结论；若某篇文档对某维度
无任何可定位原文锚点，则该单元置 `anchored=false`、`value=None`，并注明
「无锚点，不出结论」。
"""
from __future__ import annotations

import json
import re
import urllib.request
from typing import Any

from loguru import logger

from app.core.config import settings
from app.core.plugin.base import Plugin


def _core():
    import app.services.multi_paper_compare_service as m

    return m


# ── 默认演化维度（≥5），顺序即矩阵行序 ────────────────────────────────
DEFAULT_DIMENSIONS = [
    "architecture",  # 架构承袭与抛弃（Bidirectional Encoder / Causal Decoder / Encoder-Decoder）
    "model_type",  # 模型族（Transformer / BERT / GPT …）
    "parameter_count",  # 参数量演化
    "context_window",  # Context Window 递增
    "layer_norm_position",  # LayerNorm 位置（post-norm ↔ pre-norm）
    "attention_type",  # 注意力类型（self/cross/causal multicast）
    "positional_encoding",  # 位置编码（sinusoidal / learned / rotary …）
]


# ── 每维度的取值规则（确定性，从原文抽取，不编造） ────────────────────
# 每个规则：keywords 判定该维度相关，value_regex / taxonomy 提取具体取值，
# snippet_context 决定锚点原文片段长度。
_DIMENSION_RULES: dict[str, dict[str, Any]] = {
    "architecture": {
        "keywords": [
            "architecture",
            "encoder",
            "decoder",
            "ecoder",
            "架构",
            "编码器",
            "解码器",
        ],
        "taxonomy": {
            "encoder-decoder": ["encoder-decoder", "encoder–decoder"],
            "bidirectional encoder": [
                "bidirectional encoder",
                "biencoder",
                "bidir",
                "bidirectional",
            ],
            "causal decoder": [
                "causal decoder",
                "causal lm",
                "auto-regressive",
                "autoregressive",
                "left-to-right",
            ],
            "encoder": ["encoder-only", "stack of encoder", "encoder layer"],
            "decoder": ["decoder-only", "decoder layer"],
        },
    },
    "model_type": {
        "keywords": ["bert", "gpt", "transformer", "model", "模型"],
        "taxonomy": {
            "BERT": ["bert", "bidirectional encoder representations"],
            "GPT": ["gpt-", "generative pre-trained transformer", "gpt"],
            "Transformer": ["transformer"],
        },
    },
    "parameter_count": {
        "keywords": ["parameter", "parameters", "params", "参数量", "参数"],
        "value_regex": (
            r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>B|billion|M|million|百万|亿|"
            r"b|m)\s*(?:parameters|params|参|parameter|参数)?"
        ),
    },
    "context_window": {
        "keywords": [
            "context",
            "token",
            "tokens",
            "sequence",
            "上下文",
            "序列",
            "长度",
        ],
        "value_regex": (
            r"(?P<num>\d+(?:,\d{3})*(?:\.\d+)?)\s*(?P<unit>tokens?|token|序列|上下文|字符|"
            r"word|words)?\s*(?:context|sequence|窗口|长度|输入)?|"
            r"(?:context|sequence|窗口|长度|输入)\s*(?:of|为)?\s*(?P<num2>\d+(?:,\d{3})*)"
            r"\s*(?P<unit2>tokens?)?"
        ),
    },
    "layer_norm_position": {
        "keywords": [
            "layer norm",
            "layernorm",
            "layer normalization",
            "pre-norm",
            "pre norm",
            "post-norm",
            "post norm",
            "归一化",
            "层归一化",
        ],
        "taxonomy": {
            "post-norm (LN after sublayer)": [
                "post-norm",
                "post norm",
                "layer norm applied after",
                "normalization layer after",
                "apply layer norm after",
            ],
            "pre-norm (LN before sublayer)": [
                "pre-norm",
                "pre norm",
                "normalization layer before",
                "apply layer norm before",
                "pre-layer",
                "prenorm",
            ],
            "norm-first": ["norm first", "norm-first"],
        },
    },
    "attention_type": {
        "keywords": [
            "attention",
            "self-attention",
            "social attention",
            "causal mask",
            "注意力",
        ],
        "taxonomy": {
            "self-attention": ["self-attention", "self attention"],
            "masked self-attention (causal)": [
                "masked self-attention",
                "causal attention",
                "masked attention",
                "autoregressive attention",
            ],
            "cross-attention": ["cross-attention", "cross attention"],
            "multi-head attention": [
                "multi-head attention",
                "multi-headed attention",
                "multinomial head attention",
            ],
        },
    },
    "positional_encoding": {
        "keywords": [
            "positional",
            "position encoding",
            "positional encoding",
            "positional embedding",
            "sinusoidal",
            "rotary",
            "位置编码",
            "旋转位置",
        ],
        "taxonomy": {
            "sinusoidal positional encoding": ["sinusoidal positional", "sinusoidal"],
            "learned positional embedding": [
                "learned positional",
                "learned embedding",
                "learned position",
            ],
            "rotary positional encoding (RoPE)": ["rotary", "rope", "rotary position"],
            "absolute positional encoding": [
                "absolute positional",
                "absolute position",
            ],
        },
    },
}


def _norm(text: str) -> str:
    """空白折叠 + 小写，用于宽松子串匹配。"""
    return " ".join(str(text).split()).lower()


def _first_keyword_hit(text_norm: str, keywords: list[str]) -> str | None:
    for kw in keywords:
        if kw in text_norm:
            return kw
    return None


def _find_anchor_snippet(raw_text: str, needle: str, radius: int = 120) -> str:
    """在原文里定位 needle 首次出现位置，返回带上下文（默认前后 120 字符）的片段。"""
    idx = (raw_text or "").lower().find(needle.lower())
    if idx < 0:
        return ""
    start = max(0, idx - radius)
    end = min(len(raw_text), idx + len(needle) + radius)
    return raw_text[start:end].strip()


def _extract_numeric(raw_text: str, value_regex: str) -> tuple[str, str | None]:
    """按 value_regex 抽取数值，规整为『数值+单位』，返回 (raw_text_value, anchor_needle)。"""
    m = re.search(value_regex, raw_text, re.IGNORECASE)
    if not m:
        return "", None
    d = m.groupdict()
    num = d.get("num") or d.get("num2")
    unit = d.get("unit") or d.get("unit2") or ""
    unit_norm = {
        "b": "B",
        "billion": "B",
        "m": "M",
        "million": "M",
        "百万": "M",
        "亿": "亿",
    }.get(unit.rstrip("."), unit)
    if unit == "tokens" or unit == "token" or unit.startswith("tok"):
        value = f"{num} tokens"
    elif num and unit:
        value = f"{num} {unit_norm}"
    elif num:
        value = num
    else:
        value = ""
    needle = m.group(0)
    return value, needle


def _doc_pages_text(doc: dict[str, Any]) -> str:
    """规整文档 pages 为拼接全文（支持 str 列表或 [{text, page_number}]）。"""
    pages = doc.get("pages") or []
    if isinstance(pages, list) and pages and isinstance(pages[0], dict):
        pages = [p.get("text") or "" for p in pages]
    return "\n".join(str(p) for p in pages)


def _metadata_value_for(dim: str, doc: dict[str, Any]) -> str | None:
    """从 doc 顶层结构化元数据取该维度取值（作为优先锚定源）。"""
    if dim == "parameter_count":
        mc = doc.get("param_count")
        return str(mc) if mc is not None else None
    if dim == "context_window":
        cw = doc.get("context_window")
        return str(cw) if cw is not None else None
    if dim == "model_type" and doc.get("model_type"):
        return str(doc["model_type"])
    return None


def _match_taxonomy(text: str, text_norm: str, taxonomy: dict) -> tuple[str | None, str]:
    """按 taxonomy 声明顺序首中匹配，返回 (label, snippet)；无命中返回 (None, "")。"""
    pairs = [(label, nd) for label, needles in taxonomy.items() for nd in needles]
    for label, nd in pairs:
        if nd in text_norm:
            snippet = _find_anchor_snippet(text, nd)
            if snippet:
                return label, snippet
    return None, ""


def _match_numeric(text: str, value_regex: str) -> tuple[str | None, str]:
    """数值正则抽取，命中且可定位原文时返回 (value, snippet)。"""
    value, needle = _extract_numeric(text, value_regex)
    if not value:
        return None, ""
    snippet = _find_anchor_snippet(text, needle or "")
    if snippet:
        return value, snippet
    return None, ""


def _cell_for_dimension(dim: str, doc: dict[str, Any]) -> dict[str, Any]:
    """为单个 (维度, 文档) 生成矩阵单元：确定性抽取取值 + 锚点。

    元数据优先（document 顶层参数如 param_count / context_window 直接采用，
    但仅当能匹配到原文锚点才视为已锚定）。否则做全文扫描。
    """
    rule = _DIMENSION_RULES.get(dim) or {"keywords": [dim]}
    title = doc.get("title") or doc.get("document_id") or ""
    doc_id = str(doc.get("document_id") or doc.get("id") or "")
    page_number = doc.get("page_number")
    chunk_index = doc.get("chunk_index")
    text = _doc_pages_text(doc)
    text_norm = _norm(text)

    anchors: list[dict[str, Any]] = []
    value: str | None = None
    anchored = False

    # 规则 1：metadata 提供了该维度取值，且能在原文找到锚点 → 采用并锚定
    if meta := _metadata_value_for(dim, doc):
        snippet = _find_anchor_snippet(text, meta[:24])
        if snippet:
            value, anchored = meta, True
            anchors.append(_anchor(doc_id, page_number, chunk_index, snippet))

    # 规则 2：全文规则抽取（taxonomy 或数值），命中即锚定
    if not anchored:
        taxonomy = rule.get("taxonomy")
        if taxonomy:
            val, snip = _match_taxonomy(text, text_norm, taxonomy)
            if val:
                value, anchored = val, True
                anchors.append(_anchor(doc_id, page_number, chunk_index, snip))
        elif rule.get("value_regex"):
            val, snip = _match_numeric(text, rule["value_regex"])
            if val:
                value, anchored = val, True
                anchors.append(_anchor(doc_id, page_number, chunk_index, snip))

    cell: dict[str, Any] = {
        "document_id": doc_id,
        "title": title,
        "value": value if anchored else None,
        "anchored": anchored,
        "anchors": anchors[:3],
    }
    if not anchored:
        cell["note"] = "无锚点，不出结论（原文未定位到该维度的可核查证据）。"
    return cell


def _anchor(doc_id: str, page: Any, chunk: Any, snippet: str) -> dict[str, Any]:
    return {
        "document_id": doc_id,
        "page": (int(page) if isinstance(page, int) and not isinstance(page, bool) else None),
        "chunk": (int(chunk) if isinstance(chunk, int) and not isinstance(chunk, bool) else None),
        "snippet": snippet[:300],
    }


def build_compare_matrix(
    documents: list[dict[str, Any]], dimensions: list[str] | None = None
) -> dict[str, Any]:
    """构建维度化对比矩阵（确定性纯函数）。

    documents: list[{document_id, title, pages: [str] 或 [{text,page_number}],
                     param_count?, context_window?, model_type?, page_number?, chunk_index?}]
    dimensions: 维度列表（缺省 DEFAULT_DIMENSIONS）；至少取前 5 个为显式维度。

    返回：
      backend: "auto"（确定性抽取）
      document_columns: [{index, document_id, title}]
      rows: [{dimension, cells: [{document_id, value, anchored, anchors, note}]}]
      每个单元 anchors[] 非空才算有结论（anchored=true）。
    """
    dims = [d for d in (dimensions or DEFAULT_DIMENSIONS) if d]
    if len(dims) < 1:
        dims = DEFAULT_DIMENSIONS
    columns = [
        {
            "index": i,
            "document_id": str(d.get("document_id") or d.get("id") or ""),
            "title": d.get("title"),
        }
        for i, d in enumerate(documents or [])
    ]
    rows = []
    total_cells = 0
    anchored_cells = 0
    for dim in dims:
        cells = [_cell_for_dimension(dim, doc) for doc in documents or []]
        total_cells += len(cells)
        anchored_cells += sum(1 for c in cells if c["anchored"])
        rows.append({"dimension": dim, "cells": cells})
    coverage = (anchored_cells / total_cells * 100) if total_cells else 0.0
    return {
        "backend": "auto",
        "dimension_count": len(dims),
        "document_count": len(documents or []),
        "dimensions": dims,
        "document_columns": columns,
        "rows": rows,
        "anchor_coverage": {
            "total_cells": total_cells,
            "anchored_cells": anchored_cells,
            "coverage_pct": round(coverage, 2),
        },
    }


# ── 可选的 LLM 洞察增强（可插拔、失败降级规则模板） ──────────────────


def _llm_chat_completion(
    endpoint: str, model: str, messages: list[dict[str, str]], timeout: float
) -> str:
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


def enhance_insights(matrix: dict[str, Any]) -> dict[str, Any]:
    """对矩阵生成维度洞察（可选增强）。LLM 未配置/失败 → 降级规则模板。

    不改动矩阵本体数值与锚点，只附加 `insights` 文本；backend 标注 llm/rule。
    """
    rows = matrix.get("rows", [])
    brief = []
    for row in rows[:6]:
        vals = [(c["value"] if c["anchored"] else "—") for c in row.get("cells", [])]
        brief.append(f"{row['dimension']}: " + " | ".join(vals))
    prompt = (
        "基于以下跨文献『演化对比矩阵』各维度的取值，用中文写一段 3-5 句的"
        "演化脉络洞察（架构承袭/参数量/Context Window/LayerNorm 位置等趋势）。"
        "只依据给定取值，不得编造新的数值或结论。只输出洞察正文，不要前缀。\n\n" + "\n".join(brief)
    )
    backend = "rule"
    insight = ""
    note = "未配置 LLM 端点（LLM_ENABLED/LLM_ENDPOINT）或调用失败，已降级规则模板洞察。"
    if settings.LLM_ENABLED and settings.LLM_ENDPOINT:
        try:
            insight = (
                _core()
                ._llm_chat_completion(
                    settings.LLM_ENDPOINT,
                    settings.LLM_MODEL,
                    [
                        {
                            "role": "system",
                            "content": "你是科学文献演进对比助手，只依据给定取值给出严谨洞察，不编造。",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    settings.LLM_TIMEOUT,
                )
                .strip()
            )
            if insight:
                backend = "llm"
                note = ""
        except Exception as e:  # noqa: BLE001
            logger.warning(f"LLM 矩阵洞察不可用，降级规则模板: {e}")
    if not insight:
        covered = sum(1 for row in rows for c in row.get("cells", []) if c.get("anchored"))
        insight = (
            f"规则洞察：矩阵覆盖 {matrix.get('document_count', 0)} 篇文献 × "
            f"{matrix.get('dimension_count', 0)} 个维度，共 {covered} 个已锚定的比较结论。"
            "（LLM 洞察未接入或调用失败，已降级为规则模板。）"
        )
    return {
        "backend": backend,
        "matrix_backend": matrix.get("backend"),
        "insight": insight,
        "note": note,
    }


class MultiPaperCompareService:
    # ─── 插件协议 ──────────────────────────────────────────────────────────
    async def on_start(self) -> None:
        logger.info("multi_paper_compare plugin started")

    async def on_stop(self) -> None:
        logger.info("multi_paper_compare plugin stopped")

    def health(self):
        return {"backend": "multi_paper_compare", "available": self.available}

    @property
    def available(self) -> bool:
        return settings.SOURCE_ANCHOR_ENABLED

    def build_matrix(
        self, documents: list[dict[str, Any]], dimensions: list[str] | None = None
    ) -> dict[str, Any]:
        return build_compare_matrix(documents, dimensions)

    def enhance(self, matrix: dict[str, Any]) -> dict[str, Any]:
        return enhance_insights(matrix)


# 全局单例
multi_paper_compare_service = MultiPaperCompareService()


class MultiPaperComparePlugin(Plugin):
    """官方插件：multi_paper_compare —— 跨文献结构化演进对比服务（存量迁移自 app/services/multi_paper_compare_service.py）。

    - 配置沿用全局 settings（`SOURCE_ANCHOR_*` / `LLM_*` 键）。
    - 纯函数矩阵构建 + 可选 LLM 洞察增强（失败降级规则模板），无重型运行时资源；
      `create()` 返回全新实例供 registry 寻址，模块级单例 `multi_paper_compare_service` 供门面再导出。
    - 消费者动态寻址：`registry.get("multi_paper_compare")`。
    """

    name = "multi_paper_compare"
    version = "1.0.0"
    config_prefix = ""
    requires: list[str] = []
    type = "service"
    legacy_module = "app.services.multi_paper_compare_service"

    def create(self, registry, settings) -> MultiPaperCompareService:
        return MultiPaperCompareService()


plugin = MultiPaperComparePlugin()
