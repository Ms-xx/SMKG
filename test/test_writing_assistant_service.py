# -*- coding: utf-8 -*-
"""写作辅助与可视化 Copilot 测试：框架无幻觉、图脚本、CSV→SVG、图注。"""
from app.services.writing_assistant_service import (
    WritingAssistantService,
    csv_to_chart,
    figure_caption,
    generate_diagram_script,
    generate_outline,
)


def test_generate_outline_no_hallucination():
    refs = [{"index": 1, "title": "Real paper one", "raw": "Author. Real paper one."}]
    out = generate_outline("graph neural networks", refs)
    assert out["reference_count"] == 1
    assert out["references"][0]["text"].startswith("Author")
    # 无幻觉：不额外编造不在输入中的文献
    assert len(out["references"]) == 1


def test_generate_diagram_script_mermaid():
    out = generate_diagram_script("mermaid", {"title": "Arch", "nodes": ["A", "B"], "edges": [[0, 1]]})
    assert "graph TD" in out["script"]
    assert "n0 --> n1" in out["script"]


def test_generate_diagram_script_graphviz():
    out = generate_diagram_script("graphviz", {"nodes": ["A", "B"], "edges": [[0, 1]]})
    assert "digraph G {" in out["script"]


def test_csv_to_chart_bar():
    csv_text = "name,value\nA,10\nB,20\n"
    out = csv_to_chart(csv_text, "bar")
    assert out["chart_type"] == "bar"
    assert out["svg"].startswith('<svg')
    assert "<rect" in out["svg"]


def test_csv_to_chart_table():
    csv_text = "name,value\nA,10\nB,20\n"
    out = csv_to_chart(csv_text, "table")
    assert "<text" in out["svg"]


def test_figure_caption():
    cap = figure_caption({"title": "Latency", "x_label": "time", "y_label": "ms", "point_count": 5})
    assert "Latency" in cap


def test_service_csv_chart():
    svc = WritingAssistantService()
    out = svc.csv_chart("a,b\n1,2\n", "line")
    assert out["backend"] == "rule"
    assert "<polyline" in out["svg"]