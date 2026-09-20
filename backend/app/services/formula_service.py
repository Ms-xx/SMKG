# -*- coding: utf-8 -*-
"""
公式识别服务（LaTeX-OCR / pix2tex）

把「公式图像」识别为 LaTeX 源码；前端已集成 KaTeX（`katex` / `react-markdown` +
`remark-math` / `rehype-katex`），拿到 LaTeX 即可直接渲染。

依赖策略（可插拔、可降级）：
- 已安装 `pix2tex` 时，加载 LaTeX-OCR 模型识别公式图像；
- 优先使用本地 `moulds/latex-ocr` 目录下的 `weights.pth` checkpoint，
  不存在时由 pix2tex 自动下载默认权重；
- 未安装 / 模型缺失时自动降级，`recognize` 返回空串，不影响解析主流程。

说明：公式「区域定位」依赖步骤 3.4 的 YOLOv8 公式检测（尚未集成）；本服务只负责
「图 → LaTeX」，输入为已裁剪的单个公式图像。
"""
from __future__ import annotations

import os
from typing import Any

from loguru import logger

from app.core.config import settings

# pix2tex 旧版/新版可能残留的特殊 token，识别后统一清理
_PIX2TEX_TOKENS = (
    "[[START_SOLUTION]]",
    "[[END_SOLUTION]]",
    "\\begin{align*}",
    "\\end{align*}",
    "\\[",
    "\\]",
    "\\(",
    "\\)",
    "$$",
)


class FormulaRecognitionService:
    """LaTeX-OCR（pix2tex）封装，延迟加载、可降级。"""

    def __init__(self):
        self.backend = "none"
        self._model = None
        self._load_error: str | None = None

    @property
    def available(self) -> bool:
        return self._model is not None

    def _find_checkpoint(self) -> str | None:
        """在 `moulds/latex-ocr` 下查找本地 `weights.pth`。"""
        directory = settings.FORMULA_MODEL_PATH
        if not directory or not os.path.isdir(directory):
            return None
        for name in ("weights.pth", "pix2tex_model_checkpoint.pth"):
            path = os.path.join(directory, name)
            if os.path.isfile(path):
                return path
        return None

    def _build_arguments(self) -> Any | None:
        """构造 pix2tex `LatexOCR` 的初始化参数；无本地 checkpoint 时返回 None（走默认下载）。"""
        checkpoint = self._find_checkpoint()
        if not checkpoint:
            return None
        try:
            import pix2tex  # 用于定位包内默认 config.yaml
            from munch import Munch

            pkg_dir = os.path.dirname(os.path.abspath(pix2tex.__file__))
            config_path = os.path.join(pkg_dir, "settings", "config.yaml")
            return Munch(
                {
                    "config": config_path,
                    "checkpoint": checkpoint,
                    "no_cuda": settings.FORMULA_DEVICE != "cuda",
                    "device": settings.FORMULA_DEVICE,
                }
            )
        except Exception:  # pragma: no cover - 缺少 munch / pix2tex
            return None

    def _load(self) -> None:
        if self._model is not None or self.backend == "unavailable":
            return
        try:
            from pix2tex.cli import LatexOCR  # type: ignore

            self._model = LatexOCR(self._build_arguments())
            self.backend = "latex-ocr"
            logger.info("LaTeX-OCR 已加载（checkpoint=%s）", self._find_checkpoint() or "默认下载")
        except Exception as e:  # pragma: no cover - 依赖/模型缺失
            self.backend = "unavailable"
            self._load_error = str(e)
            logger.warning(
                "LaTeX-OCR 不可用，公式识别将跳过（放置 weights.pth 到 %s 或 `pip install pix2tex`）：%s",
                settings.FORMULA_MODEL_PATH,
                e,
            )

    @staticmethod
    def _clean_latex(latex: str) -> str:
        """去除 pix2tex 可能残留的特殊 token / 包裹符，返回干净 LaTeX。"""
        s = (latex or "").strip()
        for token in _PIX2TEX_TOKENS:
            s = s.replace(token, "")
        return s.strip()

    def recognize(self, image_path: str) -> str:
        """
        识别单张公式图像，返回 LaTeX 源码；不可用或识别失败时返回空串。

        Args:
            image_path: 公式区域图像路径（PNG/JPEG）。

        Returns:
            LaTeX 字符串（如 ``E=mc^{2}``）。
        """
        self._load()
        if self._model is None:
            return ""
        try:
            from PIL import Image

            image = Image.open(image_path).convert("RGB")
            latex = str(self._model(image))
            return self._clean_latex(latex)
        except Exception as e:  # pragma: no cover
            logger.warning("LaTeX-OCR 识别失败：%s", e)
            return ""

    def recognize_batch(self, image_paths: list[str]) -> list[str]:
        """批量识别公式图像，返回与输入对齐的 LaTeX 列表。"""
        return [self.recognize(p) for p in image_paths]


# 全局单例（懒加载，构造时不触发模型加载）
formula_service = FormulaRecognitionService()
