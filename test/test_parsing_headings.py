# -*- coding: utf-8 -*-
"""标题层级抽取纯函数单测（步骤 18.3 补强）。"""
from app.services.parsing_service import ParsingService


class TestBodyFontSize:
    def test_most_common_size(self):
        lines = [
            {"size": 10.0, "bold": False, "text": "a"},
            {"size": 10.0, "bold": False, "text": "b"},
            {"size": 16.0, "bold": True, "text": "Title"},
        ]
        assert ParsingService._body_font_size(lines) == 10.0

    def test_empty(self):
        assert ParsingService._body_font_size([]) == 0.0


class TestClassifyHeading:
    def test_level1(self):
        line = {"text": "3 Model Architecture", "size": 15.0, "bold": True}
        assert ParsingService._classify_heading(line, 10.0) == 1

    def test_level2(self):
        line = {"text": "3.1 Encoder and Decoder Stacks", "size": 13.0, "bold": True}
        assert ParsingService._classify_heading(line, 10.0) == 2

    def test_level3_by_bold_body_size(self):
        line = {"text": "Scaled Dot-Product Attention", "size": 10.0, "bold": True}
        assert ParsingService._classify_heading(line, 10.0) == 3

    def test_body_text_is_not_heading(self):
        line = {"text": "a" * 200, "size": 10.0, "bold": False}
        assert ParsingService._classify_heading(line, 10.0) is None

    def test_plain_short_body_not_heading(self):
        line = {"text": "Figure 1", "size": 10.0, "bold": False}
        assert ParsingService._classify_heading(line, 10.0) is None

    def test_zero_body_size(self):
        assert (
            ParsingService._classify_heading(
                {"text": "x", "size": 0, "bold": True}, 0.0
            )
            is None
        )
