# -*- coding: utf-8 -*-
"""
图表描述服务（BLIP-2）

对「图表区域图像」生成自然语言文本描述，用于辅助图表理解与检索。

依赖策略（可插拔、可降级）：
- 已安装 `transformers`/`torch` 且能加载 BLIP-2 时，生成图表描述；
- 优先使用本地 `moulds/blip2`，缺失时回退 HF 名称（`CHART_CAPTION_MODEL`）自动下载；
- 依赖/模型缺失时自动降级，`describe` 返回空串，不影响解析主流程。
"""
from __future__ import annotations

from loguru import logger

from app.core.config import resolve_model_source, settings


class ChartDescriptionService:
    """BLIP-2 图像描述，延迟加载、可降级。"""

    def __init__(self):
        self.backend = "none"
        self._processor = None
        self._model = None
        self._load_error: str | None = None

    @property
    def available(self) -> bool:
        return self._model is not None

    @staticmethod
    def _clean_caption(text: str) -> str:
        return (text or "").strip()

    def _load(self) -> None:
        if self._model is not None or self.backend == "unavailable":
            return
        try:
            from transformers import Blip2ForConditionalGeneration, Blip2Processor  # type: ignore

            model_source = resolve_model_source(
                settings.CHART_CAPTION_MODEL, settings.CHART_CAPTION_MODEL_PATH
            )
            self._processor = Blip2Processor.from_pretrained(model_source)
            self._model = Blip2ForConditionalGeneration.from_pretrained(model_source)
            self._model.to(settings.CHART_CAPTION_DEVICE)
            self._model.eval()
            self.backend = "blip2"
            logger.info("BLIP-2 已加载：%s", model_source)
        except Exception as e:  # pragma: no cover - 依赖/模型缺失
            self.backend = "unavailable"
            self._load_error = str(e)
            logger.warning(
                "BLIP-2 不可用，图表描述将跳过（放置模型到 %s 或下载 %s）：%s",
                settings.CHART_CAPTION_MODEL_PATH,
                settings.CHART_CAPTION_MODEL,
                e,
            )

    def describe(
        self, image_path: str, prompt: str = "Summarize this figure from a scientific paper."
    ) -> str:
        """
        生成图表图像的自然语言描述；不可用或失败时返回空串。

        Args:
            image_path: 图表区域图像路径。
            prompt: 文本引导（BLIP-2 支持带前缀的条件生成）。

        Returns:
            描述文本。
        """
        self._load()
        if self._model is None or self._processor is None:
            return ""
        try:
            import torch
            from PIL import Image

            image = Image.open(image_path).convert("RGB")
            inputs = self._processor(images=image, text=prompt, return_tensors="pt").to(
                settings.CHART_CAPTION_DEVICE
            )
            with torch.no_grad():
                generated = self._model.generate(**inputs, max_new_tokens=64)
            caption = self._processor.batch_decode(generated, skip_special_tokens=True)[0]
            return self._clean_caption(caption)
        except Exception as e:  # pragma: no cover
            logger.warning("BLIP-2 描述失败：%s", e)
            return ""


# 全局单例（懒加载，构造时不触发模型加载）
chart_description_service = ChartDescriptionService()
