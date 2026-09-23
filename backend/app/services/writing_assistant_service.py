# -*- coding: utf-8 -*-
"""
写作辅助与可视化 Copilot 服务（对应 XiangMu 10.2 模块六）

职责：
1. 论文框架生成：基于 idea + 真实参考文献（无幻觉：仅使用传入的真实条目，不编造）；
2. 拓扑图脚本生成：TikZ / Graphviz / Mermaid / Matplotlib 脚本字符串模板；
3. CSV 可视化：纯 Python 解析 CSV，生成零依赖 SVG（折线/柱状/雷达/表格）+ 学术图注。

依赖策略（可插拔、可降级）：
- 纯 Python（csv + 字符串模板）零第三方依赖，永远可用；
- 中英学术翻译与真实 LLM 生成预留，未接入时降级模板。
"""
from __future__ import annotations

import csv
import html
import io
import json
import logging
import urllib.request
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


def generate_outline(idea: str, references: list[dict[str, Any]]) -> dict[str, Any]:
    idea = (idea or "").strip() or "（未提供主题）"
    sections = [
        {
            "title": "Abstract",
            "content": f"围绕「{idea}」的动机、方法、主要结果与结论（摘要要点占位）。",
        },
        {
            "title": "Introduction",
            "content": f"研究背景与动机：{idea}。问题定义与本文贡献（占位）。",
        },
        {
            "title": "Related Work",
            "content": "相关工作综述，需与参考文献条目一一对应（见 References）。",
        },
        {"title": "Method", "content": "方法框架与实现要点（占位）。"},
        {"title": "Experiments", "content": "实验设置、数据集、基线对比与消融（占位）。"},
        {"title": "Conclusion", "content": "结论与后续工作（Future Work 占位）。"},
    ]
    ref_items = [
        {"index": r.get("index"), "text": r.get("raw") or r.get("title")} for r in references or []
    ]
    return {
        "backend": "rule",
        "idea": idea,
        "sections": sections,
        # 无幻觉：只回显真实传入的参考文献，不生成不存在的引用
        "references": ref_items,
        "reference_count": len(ref_items),
        "note": "本输出为规则模板；接入 LLM 后可生成成段正文，但 References 仍仅限真实条目。",
    }


def generate_diagram_script(diagram_type: str, spec: dict[str, Any]) -> dict[str, Any]:
    """spec: {title, nodes: [...], edges: [[a,b], ...]}，生成脚本字符串。"""
    diagram_type = (diagram_type or "mermaid").lower()
    title = spec.get("title") or "Architecture"
    nodes = spec.get("nodes") or []
    edges = spec.get("edges") or []

    if diagram_type == "mermaid":
        lines = ["graph TD;"]
        for i, n in enumerate(nodes):
            lines.append(f"    n{i}[{n}];")
        for a, b in edges:
            lines.append(f"    n{a} --> n{b};")
        script = "\n".join(lines)
    elif diagram_type == "graphviz":
        lines = ["digraph G {"]
        for i, n in enumerate(nodes):
            lines.append(f'    n{i} [label="{n}"];')
        for a, b in edges:
            lines.append(f"    n{a} -> n{b};")
        lines.append("}")
        script = "\n".join(lines)
    elif diagram_type == "tikz":
        lines = ["\\begin{tikzpicture}[auto, node distance=2cm]"]
        for i, n in enumerate(nodes):
            lines.append(f"    \\node[draw] (n{i}) {{{n}}};")
        for a, b in edges:
            lines.append(f"    \\draw[->] (n{a}) -- (n{b});")
        lines.append("\\end{tikzpicture}")
        script = "\n".join(lines)
    elif diagram_type == "matplotlib":
        lines = [
            "import matplotlib.pyplot as plt",
            "import networkx as nx",
            "",
            "G = nx.DiGraph()",
            f"G.add_nodes_from(range({len(nodes)}))",
        ]
        for a, b in edges:
            lines.append(f"G.add_edge({a}, {b})")
        lines.append("nx.draw(G, with_labels=True)")
        lines.append("plt.show()")
        script = "\n".join(lines)
    else:
        script = f"# unsupported diagram_type: {diagram_type}"

    return {"backend": "rule", "diagram_type": diagram_type, "title": title, "script": script}


def parse_csv(csv_text: str) -> tuple[list[str], list[list[str]]]:
    reader = csv.reader(io.StringIO(csv_text or ""))
    rows = [row for row in reader if any((c or "").strip() for c in row)]
    if not rows:
        return [], []
    return rows[0], rows[1:]


def _numbers(row: list[str]) -> list[float]:
    out: list[float] = []
    for c in row:
        try:
            out.append(float(c))
        except (TypeError, ValueError):
            out.append(0.0)
    return out


def csv_to_chart(
    csv_text: str, chart_type: str = "bar", width: int = 600, height: int = 320
) -> dict[str, Any]:
    header, data = parse_csv(csv_text)
    chart_type = (chart_type or "bar").lower()
    if not data:
        return {"backend": "rule", "chart_type": chart_type, "error": "CSV 无有效数据行", "svg": ""}

    labels = [row[0] for row in data]
    values = _numbers([row[1] if len(row) > 1 else "0" for row in data])

    pad_l, pad_b, pad_t, pad_r = 50, 40, 20, 20
    plot_w = max(100, width - pad_l - pad_r)
    plot_h = max(100, height - pad_t - pad_b)
    vmax = max(values) if values else 1.0
    vmin = min(values + [0.0])

    def _x(i: int) -> float:
        return pad_l + plot_w * (i + 0.5) / max(1, len(labels))

    def _y(v: float) -> float:
        span = (vmax - vmin) or 1.0
        return pad_t + plot_h * (1 - (v - vmin) / span)

    # 坐标轴
    axis = [
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+plot_h}" stroke="#888"/>',
        f'<line x1="{pad_l}" y1="{pad_t+plot_h}" x2="{pad_l+plot_w}" y2="{pad_t+plot_h}" stroke="#888"/>',
    ]
    marks = []
    for i, label in enumerate(labels):
        label = html.escape(str(label)[:12])
        marks.append(
            f'<text x="{_x(i):.1f}" y="{pad_t+plot_h+16}" font-size="10" text-anchor="middle">{label}</text>'
        )

    if chart_type == "bar":
        bw = plot_w / max(1, len(labels)) * 0.6
        shapes = []
        for i, v in enumerate(values):
            y = _y(v)
            y0 = _y(0)
            shapes.append(
                f'<rect x="{_x(i)-bw/2:.1f}" y="{min(y,y0):.1f}" width="{bw:.1f}" height="{abs(y0-y):.1f}" fill="#3b82f6"/>'
            )
    elif chart_type == "line":
        pts = " ".join(f"{_x(i):.1f},{_y(v):.1f}" for i, v in enumerate(values))
        shapes = [f'<polyline points="{pts}" fill="none" stroke="#3b82f6" stroke-width="2"/>']
        for i, v in enumerate(values):
            shapes.append(f'<circle cx="{_x(i):.1f}" cy="{_y(v):.1f}" r="3" fill="#3b82f6"/>')
    elif chart_type == "radar":
        cx, cy, r = pad_l + plot_w / 2, pad_t + plot_h / 2, min(plot_w, plot_h) / 2 * 0.8
        import math

        n = max(1, len(values))
        pts = []
        for i, v in enumerate(values):
            ang = -math.pi / 2 + 2 * math.pi * i / n
            ratio = (v - vmin) / ((vmax - vmin) or 1.0)
            pts.append(f"{cx + r*ratio*math.cos(ang):.1f},{cy + r*ratio*math.sin(ang):.1f}")
        shapes = [
            f'<polygon points="{" ".join(pts)}" fill="rgba(59,130,246,0.3)" stroke="#3b82f6"/>'
        ]
        marks = marks  # 复用标签
    elif chart_type == "table":
        # 表格型 SVG：直接渲染 header + data
        cells = []
        all_rows = [header] + data
        row_h = 24
        for ri, row in enumerate(all_rows):
            for ci, cell in enumerate(row[:4]):
                cells.append(
                    f'<text x="{60+ci*130}" y="{40+ri*row_h}" font-size="11">{html.escape(str(cell)[:20])}</text>'
                )
        return {
            "backend": "rule",
            "chart_type": chart_type,
            "svg": _svg(width, max(100, 40 + len(all_rows) * row_h), "".join(cells)),
        }
    else:
        shapes = []

    body = "".join(axis + marks + shapes)
    return {"backend": "rule", "chart_type": chart_type, "svg": _svg(width, height, body)}


def _svg(width: int, height: int, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="sans-serif">{body}</svg>'
    )


def figure_caption(chart_meta: dict[str, Any]) -> str:
    title = chart_meta.get("title") or "Figure"
    x = chart_meta.get("x_label") or "X"
    y = chart_meta.get("y_label") or "Y"
    n = chart_meta.get("series_count") or chart_meta.get("point_count") or 1
    return f"Figure: {title}. {y} 随 {x} 的变化，共 {n} 个数据点。"


def _chat_completion(
    endpoint: str, model: str, messages: list[dict[str, str]], timeout: float
) -> str:
    """调用 OpenAI 兼容 /v1/chat/completions，返回回复文本。失败抛异常由调用方降级。"""
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


def translate_text(text: str, target: str = "zh") -> dict[str, Any]:
    """中英学术翻译（9.1，可插拔）。

    配置 TRANSLATION_ENABLED + TRANSLATION_ENDPOINT 时调用 OpenAI 兼容端点；
    否则降级回显原文并标注 backend=rule。
    """
    text = (text or "").strip()
    backend = "rule"
    translated = text
    note = "未配置翻译端点（TRANSLATION_ENABLED/TRANSLATION_ENDPOINT），已降级回显原文。"
    if settings.TRANSLATION_ENABLED and settings.TRANSLATION_ENDPOINT:
        try:
            direction = "将英文翻译为中文" if target != "zh" else "将中文翻译为英文"
            if target != "zh":
                direction = "将中文翻译为学士英文学术用语"
            messages = [
                {
                    "role": "system",
                    "content": "你是学术翻译助手。保持术语准确、句式正式，仅输出译文。",
                },
                {"role": "user", "content": f"{direction}：\n{text}"},
            ]
            translated = _chat_completion(
                settings.TRANSLATION_ENDPOINT,
                settings.TRANSLATION_MODEL,
                messages,
                settings.LLM_TIMEOUT,
            ).strip()
            backend = "llm"
            note = ""
        except Exception as e:  # noqa: BLE001
            logger.warning(f"翻译服务不可用，降级回显: {e}")
            backend = "rule"
            note = f"翻译端点调用失败，已降级回显原文。"

    return {"backend": backend, "text": translated, "target": target, "note": note}


def llm_generate(prompt: str, max_tokens: int = 500) -> dict[str, Any]:
    """真实 LLM 文本生成（9.2，可插拔）。

    配置 LLM_ENABLED + LLM_ENDPOINT 时调用 OpenAI 兼容端点；
    否则降级为规则注释占位，标注 backend=rule。
    """
    prompt = (prompt or "").strip()
    if settings.LLM_ENABLED and settings.LLM_ENDPOINT:
        try:
            content = _chat_completion(
                settings.LLM_ENDPOINT,
                settings.LLM_MODEL,
                [
                    {"role": "system", "content": "你是学术写作助手。依据用户输入给出严谨、可用的正文。",},
                    {"role": "user", "content": prompt,},
                ],
                settings.LLM_TIMEOUT,
            )
            return {"backend": "llm", "model": settings.LLM_MODEL, "content": content}
        except Exception as e:  # noqa: BLE001
            logger.warning(f"LLM 服务不可用，降级为规则占位: {e}")
            return {
                "backend": "rule",
                "note": "LLM 端点（LLM_ENABLE/LLM_ENDPOINT）调用失败或未配置，已降级为规则占位。",
                "content": f"【规则占位】{prompt[:300]}",
            }
    return {
        "backend": "rule",
        "note": "未配置 LLM 端点（LLM_ENABLED/LLM_ENDPOINT），已降级为规则占位。",
        "content": f"【规则占位】{prompt[:300]}",
    }


class WritingAssistantService:
    @property
    def available(self) -> bool:
        return settings.WRITING_ASSISTANT_ENABLED

    def outline(self, idea: str, references: list[dict[str, Any]]) -> dict[str, Any]:
        return generate_outline(idea, references)

    def diagram(self, diagram_type: str, spec: dict[str, Any]) -> dict[str, Any]:
        return generate_diagram_script(diagram_type, spec)

    def csv_chart(self, csv_text: str, chart_type: str = "bar") -> dict[str, Any]:
        return csv_to_chart(csv_text, chart_type)

    def translate(self, text: str, target: str = "zh") -> dict[str, Any]:
        return translate_text(text, target)

    def llm_generate(self, prompt: str, max_tokens: int = 500) -> dict[str, Any]:
        return llm_generate(prompt, max_tokens)


# 全局单例
writing_assistant_service = WritingAssistantService()
