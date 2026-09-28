# -*- coding: utf-8 -*-
"""parsing_service 补充测试：OCR 回退、OCR 页、版面分析、公式/图表/裁剪、图片检测。"""
import os

import pytest
import fitz

from app.services.latex_format import SOURCE_IMAGE, normalize_latex
from app.services.parsing_service import ParsingService


# ── OCR 回退（扫描件/空白页）─────────────────────────────────────────────
def test_extract_text_with_ocr_fallback(tmp_path):
    pdf = tmp_path / "blank.pdf"
    doc = fitz.open()
    doc.new_page()  # 空白页，无文本层
    doc.save(str(pdf))
    doc.close()

    class FakeOCR:
        def recognize(self, path):
            return "SCANNED TEXT"

    svc = ParsingService(ocr=FakeOCR())
    res = svc.extract_text_with_pymupdf(str(pdf), enable_ocr=True)

    assert res["pages"][0]["ocr_used"] is True
    assert "SCANNED TEXT" in res["pages"][0]["text"]
    assert res["metadata"]["ocr_pages"] == 1


def test_ocr_page_with_fake_ocr():
    doc = fitz.open()
    page = doc.new_page()

    class FakeOCR:
        def recognize(self, path):
            return "OCR TEXT"

    svc = ParsingService(ocr=FakeOCR())
    assert svc._ocr_page(page, dpi=30) == "OCR TEXT"
    doc.close()


# ── 页面渲染 ────────────────────────────────────────────────────────────
def test_render_page():
    doc = fitz.open()
    page = doc.new_page()
    svc = ParsingService()
    out = svc._render_page(page, dpi=30)
    assert out is not None
    os.remove(out)
    doc.close()


# ── 版面分析 ────────────────────────────────────────────────────────────
def test_extract_page_elements(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.layout_service.layout_service.analyze",
        lambda img, words, boxes: {
            "elements": [{"type": "text", "text": "hi", "bbox": [0, 0, 1, 1]}]
        },
    )

    class FakeOCR:
        def recognize_with_boxes(self, path):
            return [{"text": "hi", "bbox": [0, 0, 1, 1]}]

    pdf = tmp_path / "s.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "hello")
    doc.save(str(pdf))
    doc.close()

    svc = ParsingService(ocr=FakeOCR())
    res = svc.extract_page_elements(str(pdf))
    assert res["metadata"]["page_count"] == 1
    assert res["pages"][0]["elements"] == [
        {"type": "text", "text": "hi", "bbox": [0, 0, 1, 1]}
    ]


def test_extract_page_elements_no_boxes(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.layout_service.layout_service.analyze",
        lambda img, words, boxes: {"elements": []},
    )

    class FakeOCRNoBoxes:
        pass  # 无 recognize_with_boxes

    pdf = tmp_path / "s.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf))
    doc.close()

    svc = ParsingService(ocr=FakeOCRNoBoxes())
    res = svc.extract_page_elements(str(pdf))
    assert res["pages"][0]["elements"] == []


# ── 公式 / 图表 / 图像描述（委托）─────────────────────────────────────────
def test_recognize_formula(monkeypatch):
    # 公式识别结果统一经 LaTeX 规范化：`E=mc^2` → `E=mc^{2}`
    monkeypatch.setattr(
        "app.services.formula_service.formula_service.recognize_detail",
        lambda p, display=None: normalize_latex(
            "E=mc^2", display=display, source=SOURCE_IMAGE
        ),
    )
    assert ParsingService().recognize_formula("img.png") == "E=mc^{2}"


def test_recognize_formula_detail_returns_structured_latex(monkeypatch):
    monkeypatch.setattr(
        "app.services.formula_service.formula_service.recognize_detail",
        lambda p, display=None: normalize_latex(
            "$$α \\leq β$$", display=display, source=SOURCE_IMAGE
        ),
    )
    detail = ParsingService().recognize_formula_detail("img.png")
    assert detail.latex == "\\alpha \\leq \\beta"
    assert detail.display is True
    assert detail.normalized is True
    assert detail.source == SOURCE_IMAGE


def test_extract_text_formulas_uses_uniform_latex():
    svc = ParsingService()
    items = svc.extract_text_formulas("text $$a_ij + x^2$$ and $b_k$")
    assert [i["latex"] for i in items] == ["a_{ij} + x^{2}", "b_{k}"]
    assert all(i["source"] == "text_layer" for i in items)


def test_extract_formulas_by_page_attaches_page_number():
    svc = ParsingService()
    items = svc.extract_formulas_by_page(
        {
            "pages": [
                {"page_number": 2, "text": "$$y=2$$"},
                {"page_number": 3, "text": "no math"},
            ]
        }
    )
    assert len(items) == 1
    assert items[0]["page_number"] == 2
    assert items[0]["latex"] == "y=2"


def test_detect_figures(monkeypatch):
    monkeypatch.setattr(
        "app.services.figure_detection_service.figure_detection_service.detect",
        lambda p: [{"class": "figure"}],
    )
    assert ParsingService().detect_figures("img.png") == [{"class": "figure"}]


def test_describe_chart(monkeypatch):
    monkeypatch.setattr(
        "app.services.chart_description_service.chart_description_service.describe",
        lambda p, *a: "caption",
    )
    svc = ParsingService()
    assert svc.describe_chart("img.png") == "caption"
    assert svc.describe_chart("img.png", "prompt") == "caption"


# ── 区域裁剪 ────────────────────────────────────────────────────────────
def test_crop_region(tmp_path):
    from PIL import Image

    img = tmp_path / "a.png"
    Image.new("RGB", (100, 100), "white").save(img)
    out = ParsingService()._crop_region(str(img), [10, 10, 50, 50])
    assert out is not None
    assert Image.open(out).size == (40, 40)
    os.remove(out)


def test_crop_region_invalid():
    assert ParsingService()._crop_region("missing.png", [0, 0, 1, 1]) is None


# ── 图表抽取（公式 + 图表描述两条分支）────────────────────────────────────
def test_extract_figures(tmp_path, monkeypatch):
    pdf = tmp_path / "s.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf))
    doc.close()

    monkeypatch.setattr(
        ParsingService,
        "detect_figures",
        lambda self, p: [
            {"class": "formula", "confidence": 0.9, "bbox": [0, 0, 40, 40]},
            {"class": "chart", "confidence": 0.8, "bbox": [10, 10, 30, 30]},
        ],
    )
    monkeypatch.setattr(
        ParsingService,
        "recognize_formula_detail",
        lambda self, p, display=True: normalize_latex(
            "x^2", display=display, source=SOURCE_IMAGE
        ),
    )
    monkeypatch.setattr(ParsingService, "describe_chart", lambda self, p, *a: "caption")

    svc = ParsingService()
    res = svc.extract_figures(str(pdf))
    assert res["metadata"]["page_count"] == 1
    # 公式统一为规范 LaTeX，并携带方向/来源/规范化状态
    formula = next(f for f in res["figures"] if f.get("class") == "formula")
    assert formula["latex"] == "x^{2}"
    assert formula["latex_display"] == "$$x^{2}$$"
    assert formula["is_display"] is True
    assert formula["source"] == SOURCE_IMAGE
    assert formula["normalized"] is True
    assert any(f.get("caption") == "caption" for f in res["figures"])
