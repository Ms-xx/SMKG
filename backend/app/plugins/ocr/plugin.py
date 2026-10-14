# -*- coding: utf-8 -*-
"""官方插件：ocr —— PaddleOCR 封装（存量迁移自 app/services/ocr_service.py）。

- 配置沿用全局 settings（`OCR_*` 键，存量兼容迁移；config_prefix 仅作标注）。
- 轻量/懒加载（构造不触发 PaddleOCR 加载）→ 可运行期热替换。
- `create()` 返回全新实例供 registry 热替换；模块级单例 `ocr_service` 供门面静态再导出。
- 消费者动态寻址：`registry.get("ocr")`。
"""
from __future__ import annotations

import os
from typing import Any

from loguru import logger

from app.core.config import settings
from app.core.plugin.base import Plugin


class OCRService:
    """PaddleOCR 封装，延迟加载，可降级。"""

    def __init__(self):
        self._ocr = None
        self.backend = "none"
        self._load_error: str | None = None

    # ─── 插件协议 ──────────────────────────────────────────────────────────
    async def on_start(self) -> None:
        logger.info("ocr plugin started (backend=%s)", self.backend)

    async def on_stop(self) -> None:
        logger.info("ocr plugin stopped")

    def health(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "available": self.available,
            "load_error": self._load_error,
        }

    @property
    def available(self) -> bool:
        """PaddleOCR 是否可用（已尝试加载成功）。"""
        return self._ocr is not None

    # ─── 加载 ───────────────────────────────────────────────────────────────
    def _local_model_kwargs(self) -> dict[str, str]:
        """若 `moulds/paddleocr` 下存在标准 PaddleOCR 检测/识别模型，则指定本地模型目录。"""
        kwargs: dict[str, str] = {}
        d = settings.OCR_MODEL_PATH
        if not d or not os.path.isdir(d):
            return kwargs
        det = os.path.join(d, "ch_PP-OCRv3_det_infer")
        rec = os.path.join(d, "ch_PP-OCRv3_rec_infer")
        if os.path.isdir(det):
            kwargs["det_model_dir"] = det
        if os.path.isdir(rec):
            kwargs["rec_model_dir"] = rec
        return kwargs

    def _load(self) -> None:
        """延迟加载 PaddleOCR；失败则记录并保持不可用。"""
        if self._ocr is not None or self.backend == "unavailable":
            return
        try:
            from paddleocr import PaddleOCR  # type: ignore

            self._ocr = PaddleOCR(
                lang=settings.OCR_LANGUAGE,
                use_angle_cls=settings.OCR_USE_ANGLE_CLS,
                show_log=False,
                **self._local_model_kwargs(),
            )
            self.backend = "paddleocr"
            logger.info(
                "PaddleOCR 已加载（lang=%s, use_angle_cls=%s）",
                settings.OCR_LANGUAGE,
                settings.OCR_USE_ANGLE_CLS,
            )
        except Exception as e:  # pragma: no cover - 依赖缺失
            self.backend = "unavailable"
            self._load_error = str(e)
            logger.warning(
                "PaddleOCR 不可用，扫描件 OCR 将跳过（安装 `pip install paddleocr paddlepaddle`）：%s",
                e,
            )

    # ─── 识别 ───────────────────────────────────────────────────────────────
    def recognize(self, image_path: str) -> str:
        """
        识别单张图片中的文字，返回按行拼接的文本。

        Args:
            image_path: 图片文件路径（PNG/JPEG 等）。

        Returns:
            识别出的文本（多行用换行分隔）；PaddleOCR 不可用或识别失败时返回空串。
        """
        self._load()
        if self._ocr is None:
            return ""

        try:
            if hasattr(self._ocr, "predict"):
                # PaddleOCR 3.x
                raw = self._ocr.predict(image_path)
            else:
                # PaddleOCR 2.x
                raw = self._ocr.ocr(image_path, cls=settings.OCR_USE_ANGLE_CLS)
        except TypeError:
            try:
                raw = self._ocr.ocr(image_path)
            except Exception as e:  # pragma: no cover
                logger.warning("PaddleOCR 识别失败：%s", e)
                return ""
        except Exception as e:  # pragma: no cover
            logger.warning("PaddleOCR 识别失败：%s", e)
            return ""

        lines = self._extract_lines(raw)
        return "\n".join(lines)

    def recognize_with_boxes(self, image_path: str) -> list[dict]:
        """
        识别单张图片中的文字，返回逐词文本 + 像素矩形 bbox（供版面分析使用）。

        Returns:
            [{"text": str, "bbox": [x0, y0, x1, y1]}, ...]；不可用时返回空列表。
        """
        self._load()
        if self._ocr is None:
            return []

        try:
            if hasattr(self._ocr, "predict"):
                raw = self._ocr.predict(image_path)  # PaddleOCR 3.x
            else:
                raw = self._ocr.ocr(image_path, cls=settings.OCR_USE_ANGLE_CLS)  # 2.x
        except TypeError:
            try:
                raw = self._ocr.ocr(image_path)
            except Exception:  # pragma: no cover
                return []
        except Exception:  # pragma: no cover
            return []

        return self._extract_words_with_boxes(raw)

    # ─── 结果归一化 ─────────────────────────────────────────────────────────
    @staticmethod
    def _box_to_rect(box: Any) -> list[float] | None:
        """四点 [x0,y0],[x1,y1],[x2,y2],[x3,y3] → 矩形 [x0,y0,x1,y1]。"""
        try:
            points = [p for p in box if isinstance(p, (list, tuple)) and len(p) >= 2]
            if not points:
                return None
            xs = [float(p[0]) for p in points]
            ys = [float(p[1]) for p in points]
            return [min(xs), min(ys), max(xs), max(ys)]
        except Exception:  # pragma: no cover
            return None

    @staticmethod
    def _normalize_ocr_result(item: Any) -> Any:
        """处理 3.x OCRResult 对象带 .json 属性/方法归一化。"""
        if hasattr(item, "json"):
            try:
                return item.json if not callable(item.json) else item.json()
            except Exception:
                return item
        return item

    @classmethod
    def _collect_words(cls, item: Any, items: list[dict]) -> None:
        """递归收集词条（None guard→归一化→按 isinstance 分派）。"""
        if item is None:
            return
        item = cls._normalize_ocr_result(item)
        if isinstance(item, dict):
            cls._collect_words_from_dict(item, items)
        elif isinstance(item, (list, tuple)):
            cls._collect_words_from_sequence(item, items)

    @classmethod
    def _collect_words_from_dict(cls, item: dict, items: list[dict]) -> None:
        """处理 dict（rec_texts 或递归 values）。"""
        texts = item.get("rec_texts")
        if texts is not None:
            polys = item.get("rec_polys") or item.get("dt_polys") or []
            for i, t in enumerate(texts):
                bbox = cls._box_to_rect(polys[i]) if polys and i < len(polys) else None
                items.append({"text": str(t), "bbox": bbox})
            return
        for v in item.values():
            cls._collect_words(v, items)

    @classmethod
    def _collect_words_from_sequence(cls, item: list | tuple, items: list[dict]) -> None:
        """处理 list/tuple（2.x 词条或递归）。"""
        if (
            len(item) == 2
            and isinstance(item[0], (list, tuple))
            and isinstance(item[1], (list, tuple))
            and item[1]
            and isinstance(item[1][0], str)
        ):
            items.append(
                {
                    "text": item[1][0],
                    "bbox": cls._box_to_rect(item[0]),
                }
            )
            return
        for sub in item:
            cls._collect_words(sub, items)

    @classmethod
    def _extract_words_with_boxes(cls, raw: Any) -> list[dict]:
        """从 PaddleOCR 2.x / 3.x 返回结构里提取 [(text, rect_bbox)]。"""
        items: list[dict] = []
        cls._collect_words(raw, items)
        return items

    @classmethod
    def _collect_lines(cls, item: Any, lines: list[str]) -> None:
        """递归收集文本行（None guard→归一化→按 isinstance 分派）。"""
        if item is None:
            return
        if isinstance(item, str):
            lines.append(item)
            return
        item = cls._normalize_ocr_result(item)
        if isinstance(item, str):
            lines.append(item)
            return
        if isinstance(item, dict):
            cls._collect_lines_from_dict(item, lines)
        elif isinstance(item, (list, tuple)):
            cls._collect_lines_from_sequence(item, lines)

    @classmethod
    def _collect_lines_from_dict(cls, item: dict, lines: list[str]) -> None:
        """处理 dict（rec_texts 或递归 values）。"""
        texts = item.get("rec_texts")
        if texts:
            for t in texts:
                if isinstance(t, str):
                    lines.append(t)
            return
        for v in item.values():
            cls._collect_lines(v, lines)

    @classmethod
    def _collect_lines_from_sequence(cls, item: list | tuple, lines: list[str]) -> None:
        """处理 list/tuple 递归。"""
        for sub in item:
            cls._collect_lines(sub, lines)

    @staticmethod
    def _deduplicate_lines(lines: list[str]) -> list[str]:
        """strip + 去重 + 过滤空行。"""
        seen: set[str] = set()
        out: list[str] = []
        for line in lines:
            line = line.strip()
            if line and line not in seen:
                seen.add(line)
                out.append(line)
        return out

    @staticmethod
    def _extract_lines(raw: Any) -> list[str]:
        """从 PaddleOCR 2.x / 3.x 的返回结构里提取文本行（容忍不同版本格式）。"""
        lines: list[str] = []
        OCRService._collect_lines(raw, lines)
        return OCRService._deduplicate_lines(lines)


class OCRPlugin(Plugin):
    name = "ocr"
    version = "1.0.0"
    config_prefix = "OCR_"  # 存量沿用全局 settings（OCR_* 键），settings_cls 为 None
    requires: list[str] = []
    type = "service"
    legacy_module = "app.services.ocr_service"

    def create(self, registry, settings) -> OCRService:
        return OCRService()


# 全局单例（懒加载，构造时不触发 PaddleOCR 加载）；供 app/services/ocr_service 门面再导出
ocr_service = OCRService()

plugin = OCRPlugin()
