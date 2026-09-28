# -*- coding: utf-8 -*-
"""公式 LaTeX 统一化「存储 → 接口」链路测试。

覆盖缺陷修复的两个关键回归：
1. 落库：不同来源/格式的公式统一存为规范 LaTeX，且**识别失败不再被静默丢弃**；
2. 接口：元素响应能正确映射 ORM（含历史 `bbox` 双重编码）并暴露 LaTeX 字段
   ——修复前该接口只要页面有元素就 500，导致公式在结果页永远显示不出来。
"""
import os
import sys
from types import SimpleNamespace

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.schemas.document import PageElementResponse  # noqa: E402
from app.workers import parsing_tasks as pt  # noqa: E402


class _FakeResult:
    def __init__(self, one=None):
        self._one = one

    def scalar_one_or_none(self):
        return self._one


class _FakeSession:
    """只关心 add 收集到的元素，execute 一律返回预设页面。"""

    def __init__(self, page):
        self._page = page
        self.added: list = []

    def execute(self, stmt):  # noqa: ARG002
        return _FakeResult(self._page)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        return None


def _page():
    return SimpleNamespace(id="page-1")


# ── 落库：图表 / 公式元素 ───────────────────────────────────────────────────


def test_save_figure_elements_unifies_formula_latex():
    db = _FakeSession(_page())
    figures = {
        "figures": [
            {
                "page_number": 1,
                "class": "formula",
                "confidence": 0.9,
                "bbox": [1, 2, 3, 4],
                "latex": "$$E=mc^2$$",
                "is_display": True,
                "source": "image_pix2tex",
            },
            {
                "page_number": 1,
                "class": "chart",
                "confidence": 0.8,
                "bbox": [5, 6, 7, 8],
                "caption": "图 1 折线图",
            },
        ]
    }
    figure_count, formula_count = pt._save_figure_elements(db, "d1", figures)

    assert (figure_count, formula_count) == (1, 1)
    formula = [e for e in db.added if e.element_type == "formula"][0]
    # 统一口径：content = 规范 LaTeX 主体（无定界符）
    assert formula.content == "E=mc^{2}"
    assert formula.element_metadata["latex"] == "E=mc^{2}"
    assert formula.element_metadata["latex_display"] == "$$E=mc^{2}$$"
    assert formula.element_metadata["is_display"] is True
    assert formula.element_metadata["source"] == "image_pix2tex"
    assert formula.element_metadata["normalized"] is True
    # bbox 以坐标列表落库（不再二次 json 编码）
    assert formula.bbox == [1, 2, 3, 4]

    figure = [e for e in db.added if e.element_type == "figure"][0]
    assert figure.content == "图 1 折线图"


def test_save_figure_elements_does_not_silently_drop_failed_formula():
    """识别失败（无 LaTeX）也必须落库并标注原因——原实现直接 continue 丢弃。"""
    db = _FakeSession(_page())
    figures = {
        "figures": [
            {
                "page_number": 1,
                "class": "formula",
                "confidence": 0.7,
                "bbox": [0, 0, 1, 1],
                "latex": "",
                "normalized": False,
                "error": "backend_unavailable",
                "source": "image_pix2tex",
            }
        ]
    }
    _figure_count, formula_count = pt._save_figure_elements(db, "d1", figures)

    assert formula_count == 1
    formula = db.added[0]
    assert formula.element_type == "formula"
    assert formula.element_metadata["normalized"] is False
    assert formula.element_metadata["error"] == "backend_unavailable"


def test_save_figure_elements_normalizes_plain_latex_from_any_source():
    """上游只给裸 LaTeX（或 Uni 码写法）时，落库仍统一为规范形式。"""
    db = _FakeSession(_page())
    figures = {
        "figures": [
            {"page_number": 1, "class": "formula", "bbox": [], "latex": "a_ij + α ≤ β"},
        ]
    }
    pt._save_figure_elements(db, "d1", figures)
    assert db.added[0].content == "a_{ij} + \\alpha \\leq \\beta"


def test_save_figure_elements_skips_figure_without_caption():
    db = _FakeSession(_page())
    figures = {"figures": [{"page_number": 1, "class": "chart", "bbox": []}]}
    assert pt._save_figure_elements(db, "d1", figures) == (0, 0)
    assert db.added == []


# ── 落库：文本层公式 ────────────────────────────────────────────────────────


def test_save_text_formula_elements_extracts_from_body_text():
    db = _FakeSession(_page())
    text_result = {
        "pages": [
            {
                "page_number": 1,
                "text": "Body. $$E=mc^{2}$$ inline $a_i$ and \\begin{equation}y=2\\end{equation}",
            }
        ]
    }
    added = pt._save_text_formula_elements(db, "d1", text_result)

    assert added == 3
    contents = [e.content for e in db.added]
    assert contents == ["E=mc^{2}", "a_{i}", "y=2"]
    assert all(e.element_type == "formula" for e in db.added)
    assert all(e.element_metadata["source"] == "text_layer" for e in db.added)
    assert all(e.element_metadata["class"] == "text_formula" for e in db.added)
    assert [e.element_metadata["is_display"] for e in db.added] == [True, False, True]


def test_save_text_formula_elements_noop_without_formula():
    db = _FakeSession(_page())
    assert (
        pt._save_text_formula_elements(
            db, "d1", {"pages": [{"page_number": 1, "text": "纯正文"}]}
        )
        == 0
    )
    assert db.added == []


# ── 接口：ORM → 响应（修复前恒 500）────────────────────────────────────────


def _orm_element(**kwargs):
    """模拟 DocumentElement ORM 对象。"""
    defaults = {
        "id": "el-1",
        "element_type": "formula",
        "bbox": [0, 0, 10, 10],
        "content": "E=mc^{2}",
        "element_metadata": {
            "latex": "E=mc^{2}",
            "latex_display": "$$E=mc^{2}$$",
            "is_display": True,
            "number": "3",
            "source": "image_pix2tex",
            "normalized": True,
        },
        "confidence": 0.9,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_page_element_response_maps_orm_formula():
    resp = PageElementResponse.model_validate(_orm_element())
    assert resp.element_type == "formula"
    assert resp.bbox == [0, 0, 10, 10]
    assert resp.metadata["source"] == "image_pix2tex"
    assert resp.latex == "E=mc^{2}"
    assert resp.latex_display == "$$E=mc^{2}$$"
    assert resp.is_display is True
    assert resp.formula_number == "3"
    assert resp.formula_source == "image_pix2tex"
    assert resp.formula_normalized is True


def test_page_element_response_accepts_legacy_double_encoded_bbox():
    """历史数据把 bbox 存成了 JSON 字符串，读取时必须兼容而非 500。"""
    resp = PageElementResponse.model_validate(_orm_element(bbox='"[1, 2, 3, 4]"'))
    assert resp.bbox == [1, 2, 3, 4]


def test_page_element_response_handles_broken_bbox_gracefully():
    resp = PageElementResponse.model_validate(
        _orm_element(bbox="not-json", element_type="text")
    )
    assert resp.bbox == []
    assert resp.latex is None


def test_page_element_response_non_formula_has_no_latex_fields():
    resp = PageElementResponse.model_validate(
        _orm_element(element_type="text", content="正文", element_metadata={})
    )
    assert resp.content == "正文"
    assert resp.latex is None
    assert resp.latex_display is None
    assert resp.formula_normalized is None


def test_page_element_response_derives_latex_display_when_missing():
    """旧公式元素没有 latex_display 时，按 is_display 现场补齐统一定界符。"""
    resp = PageElementResponse.model_validate(
        _orm_element(
            content="x=1", element_metadata={"is_display": False, "normalized": True}
        )
    )
    assert resp.latex == "x=1"
    assert resp.latex_display == "$x=1$"
    assert resp.is_display is False
