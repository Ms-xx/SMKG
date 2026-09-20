# -*- coding: utf-8 -*-
"""
公式识别服务单元测试
覆盖：pix2tex 缺失时安全降级、LaTeX 清理、本地 checkpoint 查找。
在无 pix2tex / 模型的环境下验证降级路径，不依赖真实模型下载。
"""
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.formula_service import FormulaRecognitionService


def test_formula_service_degrades_without_pix2tex(tmp_path):
    svc = FormulaRecognitionService()
    # pix2tex 未安装时应安全降级，返回空串而非抛异常
    assert svc.recognize(str(tmp_path / "formula.png")) == ""
    assert svc.backend in {"none", "unavailable"}


def test_clean_latex_strips_tokens():
    latex = "[[START_SOLUTION]]\\[E=mc^{2}\\]$$"
    assert FormulaRecognitionService._clean_latex(latex) == "E=mc^{2}"

    latex2 = "\\begin{align*}x+y=z\\end{align*}"
    assert FormulaRecognitionService._clean_latex(latex2) == "x+y=z"


def test_find_checkpoint_empty_dir(tmp_path):
    svc = FormulaRecognitionService()
    # 默认 moulds/latex-ocr 为空目录时返回 None
    assert svc._find_checkpoint() is None


def test_find_checkpoint_with_weights(tmp_path):
    svc = FormulaRecognitionService()
    weights = tmp_path / "weights.pth"
    weights.write_bytes(b"dummy")

    from app.core import config

    original = config.settings.FORMULA_MODEL_PATH
    config.settings.FORMULA_MODEL_PATH = str(tmp_path)
    try:
        assert svc._find_checkpoint() == str(weights)
    finally:
        config.settings.FORMULA_MODEL_PATH = original