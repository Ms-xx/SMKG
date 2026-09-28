# -*- coding: utf-8 -*-
"""LaTeX 公式统一格式化纯函数层单测。

覆盖缺陷修复的核心口径：**不同来源与类型的公式统一为同一 LaTeX 表示**，
包含定界符/数学环境统一、Unicode 符号转换、纯文本写法归一、编号与标签抽取、
异常兜底（不抛异常且标注失败原因）、行内误判过滤与正文公式抽取。
"""
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.latex_format import (  # noqa: E402
    MAX_LATEX_LENGTH,
    NormalizedFormula,
    brace_shorthand,
    extract_formulas_from_text,
    is_latex_like,
    is_plausible_inline,
    normalize_latex,
    strip_delimiters,
    to_metadata,
    unicode_to_latex,
    wrap_latex,
)

# ── 定界符与数学环境统一 ────────────────────────────────────────────────────


def test_strip_delimiters_all_forms():
    assert strip_delimiters("$$E=mc^{2}$$") == ("E=mc^{2}", True)
    assert strip_delimiters("$E=mc^{2}$") == ("E=mc^{2}", False)
    assert strip_delimiters("\\[E=mc^{2}\\]") == ("E=mc^{2}", True)
    # strip_delimiters 只负责剥离，不做花括号补全（由 normalize_latex 统一处理）
    assert strip_delimiters("\\(a_i\\)") == ("a_i", False)
    assert strip_delimiters("E=mc^{2}") == ("E=mc^{2}", None)


def test_strip_delimiters_math_environments():
    assert strip_delimiters("\\begin{equation}x+y=z\\end{equation}") == ("x+y=z", True)
    assert strip_delimiters("\\begin{align*}a&=b\\end{align*}") == ("a&=b", True)
    assert strip_delimiters("\\begin{gather*}u=v\\end{gather*}") == ("u=v", True)
    assert strip_delimiters("\\begin{math}m\\end{math}") == ("m", False)


def test_strip_delimiters_handles_pix2tex_residue():
    """pix2tex 常产出多重残留，须迭代剥离至稳定。"""
    raw = "[[START_SOLUTION]]\\[E=mc^{2}\\]$$"
    assert strip_delimiters(raw) == ("E=mc^{2}", True)
    assert strip_delimiters("[[START_SOLUTION]]E=mc^{2}[[END_SOLUTION]]") == (
        "E=mc^{2}",
        None,
    )


def test_identical_body_regardless_of_source_format():
    """同一公式的四种写法必须收敛到**完全相同**的 LaTeX 主体。"""
    bodies = {
        normalize_latex("$$E=mc^{2}$$").latex,
        normalize_latex("$E=mc^{2}$").latex,
        normalize_latex("\\[E=mc^{2}\\]").latex,
        normalize_latex("\\begin{equation}E=mc^{2}\\end{equation}").latex,
        normalize_latex("E=mc^2").latex,
    }
    assert bodies == {"E=mc^{2}"}


# ── Unicode → LaTeX ─────────────────────────────────────────────────────────


def test_unicode_to_latex_greek_operators_and_arrows():
    assert unicode_to_latex("α") == "\\alpha"
    assert unicode_to_latex("Ω") == "\\Omega"
    assert unicode_to_latex("×") == "\\times"
    assert unicode_to_latex("≤") == "\\leq"
    assert unicode_to_latex("→") == "\\to"
    assert unicode_to_latex("∑") == "\\sum"


def test_unicode_superscript_subscript_normalized():
    assert unicode_to_latex("x²") == "x^{2}"
    assert unicode_to_latex("y₁") == "y_{1}"
    assert unicode_to_latex("−3") == "-3"


def test_normalize_latex_converts_unicode_formula():
    nf = normalize_latex("α ≤ β × γ")
    assert nf.latex == "\\alpha \\leq \\beta \\times \\gamma"
    assert nf.normalized is True


# ── 纯文本写法归一 ──────────────────────────────────────────────────────────


def test_brace_shorthand_scope_rules():
    # 上标只吃前导数字，避免把后面的变量吞进指数
    assert brace_shorthand("x^2y") == "x^{2}y"
    assert brace_shorthand("x^12") == "x^{12}"
    assert brace_shorthand("x^n") == "x^{n}"
    # 下标吃整个字母数字串（a_ij 常见写法）
    assert brace_shorthand("a_ij") == "a_{ij}"
    # 已带花括号不动
    assert brace_shorthand("x^{2}y") == "x^{2}y"


def test_normalize_latex_operator_aliases():
    assert normalize_latex("a<=b").latex == "a \\leq b"
    assert normalize_latex("a>=b").latex == "a \\geq b"
    assert normalize_latex("a!=b").latex == "a \\neq b"
    assert normalize_latex("f: a->b").latex == "f: a \\to b"


# ── 编号与标签 ──────────────────────────────────────────────────────────────


def test_number_from_tag_and_trailing_paren():
    assert normalize_latex("\\begin{equation}\\tag{7}x=1\\end{equation}").number == "7"
    assert normalize_latex("E=mc^{2} (3)").number == "3"
    assert normalize_latex("E=mc^{2}").number is None


def test_number_outside_delimiters_keeps_body_clean():
    """`$$E=mc^{2}$$   (3)`：编号在定界符外，须正确摘取且主体不残留 `$$`。"""
    nf = normalize_latex("$$E=mc^{2}$$   (3)")
    assert nf.number == "3"
    assert nf.latex == "E=mc^{2}"
    assert nf.display is True


def test_function_call_not_mistaken_as_number():
    """``f(3)`` 无前置空白，不得被当成公式编号。"""
    nf = normalize_latex("E = f(3)")
    assert nf.number is None
    assert nf.latex == "E = f(3)"


def test_label_extracted_and_removed_from_body():
    """\\label 是 KaTeX 不支持的命令，必须从主体剥离并单独保留。"""
    nf = normalize_latex("\\begin{equation}\\label{eq:energy}E=mc^{2}\\end{equation}")
    assert nf.latex == "E=mc^{2}"
    assert nf.label == "eq:energy"
    assert nf.display is True


def test_unsupported_commands_removed_but_spacing_kept():
    assert normalize_latex("\\begin{align}x&=1\\nonumber\\end{align}").latex == "x&=1"
    # \, \; \quad 承载排版语义且 KaTeX 支持，不得被剥离
    assert "\\," in normalize_latex("\\int_0^1 x\\,dx").latex


# ── 异常兜底：不抛异常、标注原因、保留原文 ──────────────────────────────────


def test_empty_and_none_inputs_degrade():
    for raw in (None, "", "   "):
        nf = normalize_latex(raw)
        assert nf.latex == ""
        assert nf.normalized is False
        assert nf.error == "empty"


def test_prose_is_not_treated_as_latex():
    nf = normalize_latex("What school did burne hogarth establish?")
    assert nf.normalized is False
    assert nf.error == "not_latex_like"
    assert nf.latex  # 原文保留，便于降级展示


def test_chinese_prose_rejected_without_latex_command():
    assert normalize_latex("这是一段中文说明文字").normalized is False
    # 含 LaTeX 命令时允许（如 \text{中文}）
    assert is_latex_like("\\text{中文} x=1") is True


def test_unbalanced_braces_flagged():
    nf = normalize_latex("x^{2")
    assert nf.normalized is False
    assert nf.error == "unbalanced_braces"


def test_too_long_input_truncated_and_flagged():
    nf = normalize_latex("x=" + "1" * (MAX_LATEX_LENGTH + 50))
    assert nf.error == "too_long"
    assert len(nf.latex) <= MAX_LATEX_LENGTH


def test_normalize_latex_never_raises_on_weird_input():
    """任意脏输入都必须安全返回，绝不向解析主流程抛异常。"""
    for raw in ("\\", "{{{", "$$$$", "\\begin{equation}", "\x00\x01", "$" * 50):
        nf = normalize_latex(raw)
        assert isinstance(nf, NormalizedFormula)
        assert isinstance(nf.normalized, bool)


# ── 行内误判过滤与方向 ──────────────────────────────────────────────────────


def test_is_plausible_inline_filters_currency_and_prose():
    assert is_plausible_inline("x") is True
    assert is_plausible_inline("a_i+b") is True
    assert is_plausible_inline("\\alpha") is True
    assert is_plausible_inline("5 and 10") is False
    assert is_plausible_inline("12.50") is False
    assert is_plausible_inline("and then we go") is False
    assert is_plausible_inline("a b c") is False


def test_display_flag_priority_and_default():
    assert normalize_latex("$$x=1$$").display is True
    assert normalize_latex("$x=1$").display is False
    # 无定界符时默认行内；显式指定优先
    assert normalize_latex("x=1").display is False
    assert normalize_latex("x=1", display=True).display is True
    assert normalize_latex("$$x=1$$", display=False).display is False


# ── 定界符包装与元数据 ──────────────────────────────────────────────────────


def test_wrap_latex_uniform_delimiters():
    assert wrap_latex("E=mc^{2}", True) == "$$E=mc^{2}$$"
    assert wrap_latex("a_i", False) == "$a_i$"
    assert wrap_latex("", True) == ""


def test_latex_delimited_and_metadata_shape():
    nf = normalize_latex("$$E=mc^{2}$$", source="image_pix2tex")
    assert nf.latex_delimited == "$$E=mc^{2}$$"
    meta = to_metadata(nf)
    assert set(meta) >= {
        "latex",
        "latex_display",
        "is_display",
        "number",
        "label",
        "source",
        "normalized",
        "error",
        "original",
    }
    assert meta["latex"] == "E=mc^{2}"
    assert meta["source"] == "image_pix2tex"
    assert meta["is_display"] is True
    assert meta["normalized"] is True


# ── 正文文本层抽取 ──────────────────────────────────────────────────────────


def test_extract_formulas_from_text_mixed_forms():
    blob = (
        "Intro. $$\\int_0^1 x\\,dx = 1/2$$ middle $a_i+b$ then "
        "\\begin{equation}y=2\\end{equation} end \\[z=3\\]"
    )
    found = extract_formulas_from_text(blob)
    # 上下标统一补花括号（\int_0^1 → \int_{0}^{1}），语义等价且为规范写法
    assert [f.latex for f in found] == [
        "\\int_{0}^{1} x\\,dx = 1/2",
        "a_{i}+b",
        "y=2",
        "z=3",
    ]
    assert [f.display for f in found] == [True, False, True, True]
    assert all(f.source == "text_layer" for f in found)


def test_extract_formulas_skips_currency_and_prose():
    blob = "The cost is $5 and 10$ dollars, and $x^2$ is a square."
    found = extract_formulas_from_text(blob)
    assert [f.latex for f in found] == ["x^{2}"]


def test_extract_formulas_from_text_empty():
    assert extract_formulas_from_text("") == []
    assert extract_formulas_from_text(None) == []


def test_extract_formulas_no_duplicate_on_nested_delimiters():
    """`$$..$$` 不应同时被行内 `$..$` 重复抽取。"""
    found = extract_formulas_from_text("$$a+b$$")
    assert len(found) == 1
    assert found[0].latex == "a+b"
