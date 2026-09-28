# -*- coding: utf-8 -*-
"""LaTeX 公式统一格式化（纯函数层）。

本模块是**全链路唯一的公式格式口径**：解析（识别/提取）→ 存储 → 接口 → 前端渲染
都从这里取规范结果，避免各处自行 ``strip`` / ``replace`` 造成格式漂移。

统一约定
--------
1. ``latex`` 字段 = **去掉定界符的规范 LaTeX 主体**（如 ``E=mc^{2}``），存储与接口均用此口径；
2. 需要直接渲染或复制时，用 :func:`wrap_latex` 生成带统一定界符的完整串
   （行内 ``$...$``、行间 ``$$...$$``）；
3. 行内 / 行间语义由 ``display`` 布尔值单独承载，不再依赖"有没有定界符"来判断；
4. 编号由 ``number`` 承载（``\\tag{}`` 或行尾 ``(1)``），标签由 ``label`` 承载。

覆盖的"不同来源与类型"
----------------------
- 来源：pix2tex 图像识别输出、PDF 文本层公式、数学环境、用户/上游传入的任意串；
- 类型：行内 ``$...$`` ``\\(...\\)``、行间 ``$$...$$`` ``\\[...\\]``、
  环境 ``equation`` / ``align`` / ``gather`` / ``multline`` / ``displaymath`` / ``math``。

格式兼容与异常处理
------------------
- Unicode 数学符号统一转 LaTeX 命令（希腊字母、运算符、关系符、箭头、上下标等）；
- 纯文本数学写法归一（``x^2`` → ``x^{2}``、``a_ij`` → ``a_{ij}``、``<=`` → ``\\leq``）；
- 任何异常都不外抛：失败时返回 ``normalized=False`` + ``error`` 原因，
  并尽量保留清洗后的原文，保证"不静默丢数据"。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "INLINE_DELIMITER",
    "DISPLAY_DELIMITER",
    "MAX_LATEX_LENGTH",
    "NormalizedFormula",
    "brace_shorthand",
    "extract_formulas_from_text",
    "is_latex_like",
    "is_plausible_inline",
    "looks_like_prose",
    "normalize_latex",
    "strip_delimiters",
    "to_metadata",
    "unicode_to_latex",
    "wrap_latex",
]

# ── 常量 ──────────────────────────────────────────────────────────────────
INLINE_DELIMITER = "$"
DISPLAY_DELIMITER = "$$"

#: 单个公式的合理长度上限（超出者几乎必然是段落误判或 OCR 噪声）
MAX_LATEX_LENGTH = 2000

#: 来源标记（写入 metadata，便于排查"公式从哪来"）
SOURCE_IMAGE = "image_pix2tex"
SOURCE_TEXT_LAYER = "text_layer"
SOURCE_UNKNOWN = "unknown"

#: pix2tex 旧版/新版可能残留的特殊 token
_PIX2TEX_TOKENS = ("[[START_SOLUTION]]", "[[END_SOLUTION]]")

#: 数学环境 → 是否行间（display）
_MATH_ENVIRONMENTS: dict[str, bool] = {
    "equation": True,
    "equation*": True,
    "align": True,
    "align*": True,
    "aligned": True,
    "gather": True,
    "gather*": True,
    "multline": True,
    "multline*": True,
    "eqnarray": True,
    "eqnarray*": True,
    "displaymath": True,
    "math": False,
}

_ENV_RE = re.compile(r"\\begin\{(?P<env>[a-zA-Z*]+)\}(?P<body>.*?)\\end\{(?P=env)\}", re.DOTALL)

#: 部分外部 token 与 \clean 无关的零宽字符
_ZERO_WIDTH_MAP = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"), None)

#: 最多 4 轮剥离（pix2tex 常出现 `\[...\]$$` 这类多重残留）
_MAX_UNWRAP_PASSES = 4

#: 货币 / 数值串（行内 ``$...$`` 的常见误判形态）
_CURRENCY_RE = re.compile(r"\d+(?:[.,]\d+)?(?:\s+(?:and|or|to)\s+\d+(?:[.,]\d+)?)*")

_TAG_RE = re.compile(r"\\tag\*?\{([^{}]*)\}")
_LABEL_RE = re.compile(r"\\label\{([^{}]*)\}")
#: 行尾公式编号。**要求前置空白**：论文排版为「公式 …… (3)」，
#: 而 ``f(3)`` 这类函数调用没有空格，借此避免把函数参数误判为编号。
_TRAILING_NUMBER_RE = re.compile(r"\s+\(\s*(\d{1,3}[a-zA-Z]?)\s*\)\s*$")
#: KaTeX 不支持的排版命令：剥离而非保留，避免前端渲染报错
#: 注意：``\,`` ``\;`` ``\quad`` 等间距命令 KaTeX 支持且承载语义，**不得剥离**。
_UNSUPPORTED_RE = re.compile(r"\\(?:nonumber|notag|hfill|hspace\*?\{[^{}]*\}|vspace\*?\{[^{}]*\})")
_TRAILING_BREAK_RE = re.compile(r"(?:\\\\|\\)+\s*$")
_MULTISPACE_RE = re.compile(r"[ \t]{2,}")
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")

# ── Unicode → LaTeX 映射（格式兼容的核心）──────────────────────────────────
_GREEK_LOWER = {
    "α": r"\alpha",
    "β": r"\beta",
    "γ": r"\gamma",
    "δ": r"\delta",
    "ε": r"\epsilon",
    "ζ": r"\zeta",
    "η": r"\eta",
    "θ": r"\theta",
    "ι": r"\iota",
    "κ": r"\kappa",
    "λ": r"\lambda",
    "μ": r"\mu",
    "ν": r"\nu",
    "ξ": r"\xi",
    "ο": "o",
    "π": r"\pi",
    "ρ": r"\rho",
    "ς": r"\varsigma",
    "σ": r"\sigma",
    "τ": r"\tau",
    "υ": r"\upsilon",
    "φ": r"\phi",
    "χ": r"\chi",
    "ψ": r"\psi",
    "ω": r"\omega",
}
_GREEK_UPPER = {
    "Γ": r"\Gamma",
    "Δ": r"\Delta",
    "Θ": r"\Theta",
    "Λ": r"\Lambda",
    "Ξ": r"\Xi",
    "Π": r"\Pi",
    "Σ": r"\Sigma",
    "Υ": r"\Upsilon",
    "Φ": r"\Phi",
    "Ψ": r"\Psi",
    "Ω": r"\Omega",
}
#: 运算符 / 关系符 / 集合符 / 箭头 / 其他数学符号
_SYMBOLS = {
    "×": r"\times",
    "÷": r"\div",
    "±": r"\pm",
    "∓": r"\mp",
    "⋅": r"\cdot",
    "∗": r"\ast",
    "∘": r"\circ",
    "∙": r"\bullet",
    "√": r"\sqrt{}",
    "∑": r"\sum",
    "∏": r"\prod",
    "∫": r"\int",
    "∬": r"\iint",
    "∮": r"\oint",
    "∂": r"\partial",
    "∇": r"\nabla",
    "∞": r"\infty",
    "∝": r"\propto",
    "≈": r"\approx",
    "≃": r"\simeq",
    "≅": r"\cong",
    "≠": r"\neq",
    "≤": r"\leq",
    "≥": r"\geq",
    "≪": r"\ll",
    "≫": r"\gg",
    "≡": r"\equiv",
    "∼": r"\sim",
    "∈": r"\in",
    "∉": r"\notin",
    "∋": r"\ni",
    "⊂": r"\subset",
    "⊆": r"\subseteq",
    "⊃": r"\supset",
    "⊇": r"\supseteq",
    "∪": r"\cup",
    "∩": r"\cap",
    "∅": r"\emptyset",
    "∀": r"\forall",
    "∃": r"\exists",
    "¬": r"\neg",
    "∧": r"\wedge",
    "∨": r"\vee",
    "⊕": r"\oplus",
    "⊗": r"\otimes",
    "⊥": r"\perp",
    "∠": r"\angle",
    "△": r"\triangle",
    "→": r"\to",
    "←": r"\leftarrow",
    "↔": r"\leftrightarrow",
    "⇒": r"\Rightarrow",
    "⇐": r"\Leftarrow",
    "⇔": r"\Leftrightarrow",
    "↦": r"\mapsto",
    "↑": r"\uparrow",
    "↓": r"\downarrow",
    "ℏ": r"\hbar",
    "ℓ": r"\ell",
    "ℜ": r"\Re",
    "ℑ": r"\Im",
    "ℵ": r"\aleph",
    "ℝ": r"\mathbb{R}",
    "ℕ": r"\mathbb{N}",
    "ℤ": r"\mathbb{Z}",
    "ℚ": r"\mathbb{Q}",
    "ℂ": r"\mathbb{C}",
    "′": "'",
    "″": "''",
    "−": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u00a0": " ",
}
_SUPERSCRIPT_DIGITS = {
    "⁰": "0",
    "¹": "1",
    "²": "2",
    "³": "3",
    "⁴": "4",
    "⁵": "5",
    "⁶": "6",
    "⁷": "7",
    "⁸": "8",
    "⁹": "9",
    "⁺": "+",
    "⁻": "-",
    "⁼": "=",
    "ⁿ": "n",
    "ⁱ": "i",
}
_SUBSCRIPT_CHARS = {
    "₀": "0",
    "₁": "1",
    "₂": "2",
    "₃": "3",
    "₄": "4",
    "₅": "5",
    "₆": "6",
    "₇": "7",
    "₈": "8",
    "₉": "9",
    "₊": "+",
    "₋": "-",
    "₌": "=",
    "ₐ": "a",
    "ₑ": "e",
    "ₕ": "h",
    "ᵢ": "i",
    "ⱼ": "j",
    "ₖ": "k",
    "ₗ": "l",
    "ₘ": "m",
    "ₙ": "n",
    "ₚ": "p",
    "ᵣ": "r",
    "ₛ": "s",
    "ₜ": "t",
    "ₓ": "x",
}
_UNICODE_MAP: dict[str, str] = {**_GREEK_LOWER, **_GREEK_UPPER, **_SYMBOLS}

#: 纯文本运算符别名 → LaTeX（长匹配优先）
_OPERATOR_ALIASES: tuple[tuple[str, str], ...] = (
    ("<=>", r"\Leftrightarrow"),
    ("<->", r"\leftrightarrow"),
    ("=>", r"\Rightarrow"),
    ("<=", r"\leq"),
    (">=", r"\geq"),
    ("!=", r"\neq"),
    ("->", r"\to"),
    ("<-", r"\leftarrow"),
)

#: 判断"像不像公式"的信号（用于剔除段落误判与 OCR 噪声）
_MATH_SIGNAL_RE = re.compile(
    r"\\[a-zA-Z]+"
    r"|[{}\^_]"
    r"|(?<=\S)=(?=\S)"
    r"|[" + re.escape("".join(_SYMBOLS) + "".join(_GREEK_LOWER) + "".join(_GREEK_UPPER)) + r"]"
)
_ALPHA_WORD_RE = re.compile(r"[A-Za-z]{2,}")


@dataclass(frozen=True)
class NormalizedFormula:
    """规范化后的公式（全链路统一结构）。

    Attributes:
        latex: 规范 LaTeX 主体（无定界符）。
        display: ``True`` 表示行间公式，``False`` 表示行内。
        number: 公式编号（来自 ``\\tag{}`` 或行尾 ``(1)``）。
        label: ``\\label{}`` 内容（KaTeX 不渲染，故从主体剥离后单独保留）。
        source: 来源标记（见 ``SOURCE_*``）。
        normalized: 是否成功规范化（``False`` 表示异常/非公式，前端应降级处理）。
        error: 失败原因（``None`` 表示成功）。
        original: 规范化前的原始串（保留以便追溯与重跑）。
    """

    latex: str
    display: bool = False
    number: str | None = None
    label: str | None = None
    source: str = SOURCE_UNKNOWN
    normalized: bool = True
    error: str | None = None
    original: str = ""

    @property
    def latex_delimited(self) -> str:
        """带统一定界符的完整 LaTeX（行内 ``$...$`` / 行间 ``$$...$$``）。"""
        return wrap_latex(self.latex, self.display)

    def as_dict(self) -> dict:
        """转为可 JSON 序列化的 dict。"""
        return {
            "latex": self.latex,
            "latex_display": self.latex_delimited,
            "is_display": self.display,
            "number": self.number,
            "label": self.label,
            "source": self.source,
            "normalized": self.normalized,
            "error": self.error,
            "original": self.original,
        }


def wrap_latex(body: str, display: bool = False) -> str:
    """给规范主体加统一 LaTeX 定界符（行内 ``$`` / 行间 ``$$``）。"""
    text = (body or "").strip()
    if not text:
        return ""
    delimiter = DISPLAY_DELIMITER if display else INLINE_DELIMITER
    return f"{delimiter}{text}{delimiter}"


def _strip_pix2tex_tokens(text: str) -> str:
    """清理 pix2tex 遗留 token 与零宽字符。"""
    s = (text or "").translate(_ZERO_WIDTH_MAP)
    for token in _PIX2TEX_TOKENS:
        s = s.replace(token, "")
    return s


def _unwrap_edges(text: str) -> tuple[str, bool | None] | None:
    """剥离首尾定界符（先成对、后单侧），返回 (主体, 行间提示) 或 None。"""
    s = text
    paired = (
        (DISPLAY_DELIMITER, DISPLAY_DELIMITER, True),
        ("\\[", "\\]", True),
        ("\\(", "\\)", False),
        (INLINE_DELIMITER, INLINE_DELIMITER, False),
    )
    for left, right, hint in paired:
        if s.startswith(left) and s.endswith(right) and len(s) > len(left) + len(right):
            inner = s[len(left) : len(s) - len(right)].strip()
            if inner:
                return inner, hint
    # 单侧残留：pix2tex 可能产出 `\[...\]$$`、`$$...\]` 等混合形态
    for token, hint in (
        (DISPLAY_DELIMITER, True),
        ("\\[", True),
        ("\\]", True),
        ("\\(", False),
        ("\\)", False),
    ):
        if s.startswith(token):
            inner = s[len(token) :].strip()
            if inner:
                return inner, hint
        if s.endswith(token):
            inner = s[: -len(token)].strip()
            if inner:
                return inner, hint
    return None


def strip_delimiters(text: str) -> tuple[str, bool | None]:
    """统一剥离公式定界符与数学环境，返回 ``(主体, 是否行间)``。

    支持 ``$...$`` / ``$$...$$`` / ``\\(...\\)`` / ``\\[...\\]`` 与
    ``equation`` / ``align`` / ``gather`` / ``multline`` / ``displaymath`` / ``math``
    等环境；多重残留（如 ``\\[E=mc^{2}\\]$$``）会迭代剥离至稳定。

    行间提示为 ``None`` 表示"输入未携带任何定界符"，由调用方决定方向。
    """
    s = _strip_pix2tex_tokens(text).strip()
    if not s:
        return "", None
    display: bool | None = None
    for _ in range(_MAX_UNWRAP_PASSES):
        env_match = _ENV_RE.fullmatch(s)
        if env_match:
            env = (env_match.group("env") or "").strip().lower()
            if env in _MATH_ENVIRONMENTS:
                if display is None:
                    display = _MATH_ENVIRONMENTS[env]
                s = env_match.group("body").strip()
                continue
        unwrapped = _unwrap_edges(s)
        if unwrapped is None:
            break
        s, hint = unwrapped
        if display is None and hint is not None:
            display = hint
    return s.strip(), display


def unicode_to_latex(text: str) -> str:
    """把 Unicode 数学符号替换为等价 LaTeX 命令。

    上标/下标数字会转成 ``^{}/_{}`` 形式；映射表未覆盖的字符原样保留，
    交由前端 KaTeX（``throwOnError: false``）兜底，不在此处做有损转义。
    """
    if not text:
        return ""
    out: list[str] = []
    for ch in text:
        if ch in _UNICODE_MAP:
            out.append(_UNICODE_MAP[ch])
        elif ch in _SUPERSCRIPT_DIGITS:
            out.append("^{" + _SUPERSCRIPT_DIGITS[ch] + "}")
        elif ch in _SUBSCRIPT_CHARS:
            out.append("_{" + _SUBSCRIPT_CHARS[ch] + "}")
        else:
            out.append(ch)
    return "".join(out)


def _normalize_operator_aliases(text: str) -> str:
    """把 ``<=`` / ``>=`` / ``->`` 等纯文本写法换成 LaTeX 关系符。"""
    s = text or ""
    for alias, command in _OPERATOR_ALIASES:
        s = s.replace(alias, f" {command} ")
    return _MULTISPACE_RE.sub(" ", s).strip()


def brace_shorthand(text: str) -> str:
    """给裸上下标补花括号，避免 LaTeX 取错作用域。

    - 下标取**整个字母数字串**：``a_ij`` → ``a_{ij}``（下标常为多字符）；
    - 上标取**前导数字串**，无数字时取单个字符：``x^2y`` → ``x^{2}y``、
      ``x^n`` → ``x^{n}``（避免把 ``y`` 误吞进指数）。

    已带花括号或已经是 ``\\命令`` 的上下标不改动。
    """
    if not text:
        return ""
    out: list[str] = []
    i = 0
    length = len(text)
    while i < length:
        ch = text[i]
        if ch in "^_" and i + 1 < length and text[i + 1] not in "{":
            j = i + 1
            while j < length and (text[j].isalnum()):
                j += 1
            token = text[i + 1 : j]
            if token:
                if ch == "^":
                    digits = re.match(r"\d+", token)
                    token = digits.group(0) if digits else token[0]
                    j = i + 1 + len(token)
                out.append(ch + "{" + token + "}")
                i = j
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def _extract_label(body: str) -> tuple[str, str | None]:
    """抽出 ``\\label{}``（KaTeX 不支持该命令，必须从主体剥离）。"""
    match = _LABEL_RE.search(body or "")
    if not match:
        return body, None
    return _LABEL_RE.sub("", body), (match.group(1).strip() or None)


def _extract_number(body: str) -> tuple[str, str | None]:
    """抽出公式编号：优先 ``\\tag{}``，其次行尾 ``(1)`` 形式。"""
    match = _TAG_RE.search(body or "")
    if match:
        return _TAG_RE.sub("", body), (match.group(1).strip() or None)
    match = _TRAILING_NUMBER_RE.search(body or "")
    if match:
        return _TRAILING_NUMBER_RE.sub("", body), match.group(1).strip()
    return body, None


def _split_trailing_number(text: str) -> tuple[str, str | None]:
    """剥离**定界符之外**的行尾编号。

    论文常见排版为 ``$$E=mc^{2}$$      (3)``——编号在定界符之外，若不先摘掉，
    后续解包会因"结尾不是 ``$$``"而失败，导致 ``$$`` 残留在 LaTeX 主体里。
    """
    match = _TRAILING_NUMBER_RE.search(text or "")
    if not match:
        return text, None
    return text[: match.start()].strip(), match.group(1).strip()


def _strip_unsupported(body: str) -> str:
    """剥离 KaTeX 不支持的排版命令与多余空白，降低前端渲染失败率。"""
    s = _UNSUPPORTED_RE.sub("", body or "")
    s = _TRAILING_BREAK_RE.sub("", s)
    return s.strip()


def _braces_balanced(text: str) -> bool:
    """检查花括号是否配对（跳过 ``\\{`` / ``\\}`` 转义）。"""
    depth = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return False
        i += 1
    return depth == 0


def looks_like_prose(text: str) -> bool:
    """判断是否更像自然语言段落（用于排除行内 ``$`` 的货币/正文误判）。"""
    return len(_ALPHA_WORD_RE.findall(text or "")) >= 3


def is_latex_like(text: str) -> bool:
    """判断文本是否具备公式特征（含 LaTeX 命令、上下标、关系符或数学符号）。"""
    body = (text or "").strip()
    if not body:
        return False
    if _MATH_SIGNAL_RE.search(body):
        # 含中文且无任何 LaTeX 命令 → 判定为正文而非公式
        if _CJK_RE.search(body) and not re.search(r"\\[a-zA-Z]+", body):
            return False
        return True
    return False


def is_plausible_inline(body: str) -> bool:
    """判断行内 ``$...$`` 的内容是否像公式（排除货币与正文误判）。

    排除：多词自然语言、``5`` / ``5 and 10`` / ``12.50`` 这类货币数值、
    含空白但无任何数学信号的串（如 ``a b c``）；其余（``x``、``abc``、
    ``a_i+b``、``\\alpha``）视为公式。
    """
    text = (body or "").strip()
    if not text:
        return False
    if looks_like_prose(text):
        return False
    if _CURRENCY_RE.fullmatch(text):
        return False
    if any(ch.isspace() for ch in text) and not is_latex_like(text):
        return False
    return True


def normalize_latex(
    raw: str | None,
    *,
    display: bool | None = None,
    source: str = SOURCE_UNKNOWN,
    number: str | None = None,
    label: str | None = None,
) -> NormalizedFormula:
    """把任意来源的公式统一规范为 LaTeX。

    Args:
        raw: 原始公式串（可含定界符 / 数学环境 / Unicode 符号 / 纯文本写法）。
        display: 显式指定行内/行间；``None`` 时采用输入中探测到的方向，再默认行内。
        source: 来源标记，用于落库后排查。
        number: 显式编号（优先于从主体中抽取）。
        label: 显式标签（优先于从主体中抽取）。

    Returns:
        :class:`NormalizedFormula`。任何异常都会被收敛为 ``normalized=False`` +
        ``error``，不会向上抛出，保证解析主流程安全。
    """
    original = "" if raw is None else str(raw)
    cleaned = _strip_pix2tex_tokens(original).strip()
    if not cleaned:
        return NormalizedFormula(
            latex="",
            display=bool(display),
            source=source,
            normalized=False,
            error="empty",
            original=original.strip(),
        )

    error: str | None = None
    try:
        # 先摘掉定界符之外的编号（如 `$$...$$   (3)`），否则解包会失败并残留 `$$`
        cleaned, outer_number = _split_trailing_number(cleaned)
        body, detected_display = strip_delimiters(cleaned)
        body = body.strip()
        if not body:
            return NormalizedFormula(
                latex="",
                display=bool(display) if display is not None else bool(detected_display),
                source=source,
                normalized=False,
                error="empty_after_strip",
                original=original.strip(),
            )
        if len(body) > MAX_LATEX_LENGTH:
            error = "too_long"
            body = body[:MAX_LATEX_LENGTH]

        body = _normalize_operator_aliases(unicode_to_latex(body))
        body = brace_shorthand(body)
        body, parsed_label = _extract_label(body)
        body, parsed_number = _extract_number(body)
        body = _strip_unsupported(body)

        if not body:
            return NormalizedFormula(
                latex="",
                display=bool(display) if display is not None else bool(detected_display),
                source=source,
                normalized=False,
                error="empty_after_clean",
                original=original.strip(),
            )

        resolved_display = (
            display
            if display is not None
            else (detected_display if detected_display is not None else False)
        )
        normalized = is_latex_like(body)
        if not normalized and error is None:
            error = "not_latex_like"
        if not _braces_balanced(body):
            normalized = False
            error = "unbalanced_braces"

        return NormalizedFormula(
            latex=body,
            display=bool(resolved_display),
            number=(number or parsed_number or outer_number),
            label=(label or parsed_label),
            source=source,
            normalized=normalized,
            error=error,
            original=original.strip(),
        )
    except Exception as e:  # noqa: BLE001 - 规范化绝不允许中断解析主流程
        return NormalizedFormula(
            latex=cleaned,
            display=bool(display),
            source=source,
            normalized=False,
            error=f"normalize_failed: {e}",
            original=original.strip(),
        )


def to_metadata(formula: NormalizedFormula) -> dict:
    """把规范化结果转为落库用 metadata（含统一 LaTeX 口径与来源信息）。"""
    return formula.as_dict()


# ── 正文文本层公式抽取 ────────────────────────────────────────────────────
#: 优先级顺序：行间在前，避免 ``$$..$$`` 被行内 ``$..$`` 抢先匹配
_TEXT_FORMULA_PATTERNS: tuple[tuple[re.Pattern[str], bool | None], ...] = (
    (re.compile(r"\$\$(?P<body>.+?)\$\$", re.DOTALL), True),
    (re.compile(r"\\\[(?P<body>.+?)\\\]", re.DOTALL), True),
    (
        re.compile(
            r"\\begin\{(?P<env>equation\*?|align\*?|aligned|gather\*?|multline\*?"
            r"|eqnarray\*?|displaymath|math)\}(?P<body>.*?)\\end\{(?P=env)\}",
            re.DOTALL,
        ),
        None,
    ),
    (re.compile(r"\\\((?P<body>.+?)\\\)", re.DOTALL), False),
    (re.compile(r"(?<!\$)\$(?!\$)(?P<body>[^$\n]{1,300}?)(?<!\$)\$(?!\$)", re.DOTALL), False),
)


def _spans_overlap(a: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    return any(not (a[1] <= b[0] or a[0] >= b[1]) for b in spans)


def extract_formulas_from_text(
    text: str, *, source: str = SOURCE_TEXT_LAYER
) -> list[NormalizedFormula]:
    """从正文文本中抽取公式并统一规范为 LaTeX。

    覆盖 ``$$...$$``、``\\[...\\]``、``$...$``、``\\(...\\)`` 与常见数学环境；
    按优先级顺序匹配并跳过重叠区间，避免同一公式被重复抽取。
    行内 ``$...$`` 还会做"像不像正文/货币"的过滤，减少误判。

    Args:
        text: 待扫描文本（通常为某页的解析文本）。
        source: 来源标记。

    Returns:
        规范化公式列表，按出现顺序排列。
    """
    if not text:
        return []
    found: list[tuple[int, NormalizedFormula]] = []
    occupied: list[tuple[int, int]] = []
    for pattern, display_hint in _TEXT_FORMULA_PATTERNS:
        for match in pattern.finditer(text):
            span = match.span()
            if _spans_overlap(span, occupied):
                continue
            body = match.group("body")
            if display_hint is None:
                env = (match.groupdict().get("env") or "").strip().lower()
                hint: bool | None = _MATH_ENVIRONMENTS.get(env, True)
            else:
                hint = display_hint
            # 行内公式：排除"多词自然语言 / 货币"误判
            if hint is False and not is_plausible_inline(body):
                continue
            formula = normalize_latex(body, display=hint, source=source)
            if not formula.latex:
                continue
            occupied.append(span)
            found.append((span[0], formula))
    found.sort(key=lambda item: item[0])
    return [formula for _, formula in found]
