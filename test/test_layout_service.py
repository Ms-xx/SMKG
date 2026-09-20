# -*- coding: utf-8 -*-
"""
版面分析服务单元测试
覆盖：标签映射、bbox 归一化、token→word 标签映射、block 合并、模型缺失降级。
纯函数测试，不依赖 LayoutLMv3 模型下载。
"""
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.layout_service import (
    LayoutAnalysisService,
    detect_header_footer,
    group_blocks,
    is_page_number,
    map_label,
    map_token_labels_to_words,
    normalize_boxes,
)


def test_map_label():
    assert map_label("TITLE") == "title"
    assert map_label("text") == "paragraph"
    assert map_label("LIST") == "list"
    assert map_label("TABLE") == "table"
    assert map_label("FIGURE") == "figure"
    # 未知标签回退为段落
    assert map_label("FORMULA") == "paragraph"


def test_normalize_boxes():
    boxes = [[0, 0, 500, 1000], [500, 0, 1000, 1000]]
    norm = normalize_boxes(boxes, width=1000, height=1000)
    assert norm == [[0, 0, 500, 1000], [500, 0, 1000, 1000]]

    # 非 1000 尺寸按比例缩放
    norm2 = normalize_boxes([[0, 0, 100, 200]], width=200, height=400)
    assert norm2 == [[0, 0, 500, 500]]


def test_map_token_labels_to_words():
    id2label = {0: "TEXT", 1: "TITLE", 2: "LIST"}
    word_ids = [0, 0, 1, 2]          # word0, word0(子词), word1, word2
    preds = [0, 0, 1, 2]            # TEXT, TEXT, TITLE, LIST
    labels = map_token_labels_to_words(word_ids, preds, id2label)
    assert labels == ["paragraph", "title", "list"]


def test_group_blocks():
    words = ["钙钛矿", "太阳能", "电池", "Fig1", "效率"]
    boxes = [
        [0, 0, 10, 10],
        [12, 0, 22, 10],
        [24, 0, 34, 10],
        [0, 20, 10, 30],
        [12, 20, 22, 30],
    ]
    labels = ["paragraph", "paragraph", "paragraph", "figure", "paragraph"]

    elements = group_blocks(words, boxes, labels)
    assert len(elements) == 3

    assert elements[0]["type"] == "paragraph"
    assert elements[0]["text"] == "钙钛矿 太阳能 电池"
    assert elements[0]["bbox"] == [0, 0, 34, 10]

    assert elements[1]["type"] == "figure"
    assert elements[1]["bbox"] == [0, 20, 10, 30]

    assert elements[2]["type"] == "paragraph"
    assert elements[2]["text"] == "效率"


def test_layout_service_degrades_without_model():
    svc = LayoutAnalysisService()
    svc.backend = "unavailable"  # 模拟模型缺失，避免网络下载
    res = svc.analyze("page.png", ["词"], [[0, 0, 10, 10]])
    assert res["elements"] == []
    assert res["backend"] == "unavailable"


def test_is_page_number():
    assert is_page_number("5") is True
    assert is_page_number("1/12") is True
    assert is_page_number("第 3 页") is True
    assert is_page_number("Page 5") is True
    assert is_page_number("摘要") is False
    assert is_page_number("") is False


def test_detect_header_footer():
    # 页面高度 1000px：顶部 <120 为页眉，底部 >880 为页脚
    elements = [
        {"type": "paragraph", "text": "正文", "bbox": [0, 200, 100, 220]},
        {"type": "paragraph", "text": "钙钛矿材料", "bbox": [0, 10, 50, 25]},      # 页眉
        {"type": "paragraph", "text": "5", "bbox": [0, 950, 20, 970]},            # 页脚页码
    ]
    out = detect_header_footer(elements, page_height=1000)
    assert out[0]["type"] == "paragraph"  # 正文不变
    assert out[1]["type"] == "header"
    assert out[2]["type"] == "footer"
    assert out[2].get("is_page_number") is True
    assert out[0].get("is_page_number") is None