# -*- coding: utf-8 -*-
"""
OCR 服务单元测试
覆盖：PaddleOCR 缺失时安全降级、扫描件/图片页 OCR 回退、结果归一化（2.x / 3.x）。
在无 paddleocr / paddlepaddle 的环境下自动验证降级路径，不依赖真实模型。
"""
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import fitz  # PyMuPDF

from app.services.parsing_service import ParsingService
from app.services.ocr_service import OCRService


class FakeOCR:
    """伪造 OCR，用于在不装 PaddleOCR 时验证回退逻辑。"""

    def __init__(self, text: str):
        self._text = text
        self.calls = 0
        self.backend = "fake"

    def recognize(self, image_path: str) -> str:
        self.calls += 1
        return self._text


def _make_blank_pdf(path):
    """生成无文本层的「扫描件」样式 PDF（空白页，get_text() 为空）。"""
    doc = fitz.open()
    doc.new_page()
    doc.save(path)
    doc.close()


def _make_text_pdf(path):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello OCR", fontsize=12)
    doc.save(path)
    doc.close()


def test_ocr_service_degrades_without_paddleocr(tmp_path, monkeypatch):
    # 强制 paddleocr 导入失败，模拟未安装场景（CI 会真实安装 paddleocr）
    monkeypatch.setitem(sys.modules, "paddleocr", None)
    svc = OCRService()
    # paddleocr 未安装时应安全降级，返回空串而非抛异常
    text = svc.recognize(str(tmp_path / "none.png"))
    assert text == ""
    assert svc.backend in {"none", "unavailable"}


def test_parsing_service_ocr_fallback_scanned(tmp_path):
    pdf = tmp_path / "scan.pdf"
    _make_blank_pdf(pdf)

    fake = FakeOCR("扫描件识别出的中文文本")
    svc = ParsingService(ocr=fake)
    result = svc.extract_text_with_pymupdf(str(pdf))

    assert fake.calls >= 1  # 空文本页触发了 OCR
    assert result["pages"][0]["text"] == "扫描件识别出的中文文本"
    assert result["pages"][0]["ocr_used"] is True
    assert result["metadata"]["ocr_pages"] == 1


def test_parsing_service_skips_ocr_on_text_pdf(tmp_path):
    pdf = tmp_path / "text.pdf"
    _make_text_pdf(pdf)

    fake = FakeOCR("不应被调用")
    svc = ParsingService(ocr=fake)
    result = svc.extract_text_with_pymupdf(str(pdf))

    assert fake.calls == 0  # 有文本层不触发 OCR
    assert "Hello OCR" in result["pages"][0]["text"]
    assert result["pages"][0]["ocr_used"] is False


def test_ocr_extract_lines_normalization():
    svc = OCRService()

    # PaddleOCR 2.x 格式：[[[box], (text, conf)], ...]
    v2 = [
        [[[0, 0], [10, 0], [10, 10], [0, 10]], ("你好", 0.99)],
        [[[0, 0], [10, 0], [10, 10], [0, 10]], ("世界", 0.98)],
    ]
    assert svc._extract_lines(v2) == ["你好", "世界"]

    # PaddleOCR 3.x 格式：OCRResult 对象带 .json -> [{"rec_texts": [...]}]
    class _Res:
        def __init__(self, texts):
            self._texts = texts

        @property
        def json(self):
            return [{"rec_texts": self._texts, "rec_scores": [0.9, 0.9]}]

    assert svc._extract_lines([_Res(["中文", "识别"])]) == ["中文", "识别"]


def test_ocr_extract_words_with_boxes():
    svc = OCRService()

    # PaddleOCR 2.x 格式：[box(四点), (text, conf)]
    v2 = [
        [[[0, 0], [100, 0], [100, 50], [0, 50]], ("你好", 0.99)],
        [[[0, 60], [80, 60], [80, 100], [0, 100]], ("世界", 0.98)],
    ]
    items = svc._extract_words_with_boxes(v2)
    assert items[0] == {"text": "你好", "bbox": [0, 0, 100, 50]}
    assert items[1] == {"text": "世界", "bbox": [0, 60, 80, 100]}

    # PaddleOCR 3.x 格式：OCRResult.json -> {"res": {"rec_texts", "rec_polys"}}
    class _Res:
        @property
        def json(self):
            return {
                "res": {
                    "rec_texts": ["中文", "识别"],
                    "rec_polys": [
                        [[0, 0], [10, 0], [10, 5], [0, 5]],
                        [[0, 6], [20, 6], [20, 12], [0, 12]],
                    ],
                }
            }

    items3 = svc._extract_words_with_boxes([_Res()])
    assert items3[0] == {"text": "中文", "bbox": [0, 0, 10, 5]}
    assert items3[1] == {"text": "识别", "bbox": [0, 6, 20, 12]}