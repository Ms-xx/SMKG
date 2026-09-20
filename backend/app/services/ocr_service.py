"""
OCR 服务（PaddleOCR，中文优先）

处理扫描版 PDF 与图片文字页：将页面渲染为图片后调用 PaddleOCR 识别文字。

依赖策略（可插拔、可降级）：
- 已安装 `paddleocr`（及其依赖 `paddlepaddle`）时，真实调用 PaddleOCR 识别；
- 未安装 / 加载失败时自动降级为「返回空文本」，保证解析主流程不受影响。
"""

from __future__ import annotations

import os
from typing import Any

from loguru import logger

from app.core.config import settings


class OCRService:
    """PaddleOCR 封装，延迟加载，可降级。"""

    def __init__(self):
        self._ocr = None
        self.backend = "none"
        self._load_error: str | None = None

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

    @classmethod
    def _extract_words_with_boxes(cls, raw: Any) -> list[dict]:
        """从 PaddleOCR 2.x / 3.x 返回结构里提取 [(text, rect_bbox)]。"""
        items: list[dict] = []

        def collect(item: Any) -> None:
            if item is None:
                return
            # 3.x OCRResult 对象带 .json
            if hasattr(item, "json"):
                try:
                    item = item.json if not callable(item.json) else item.json()
                except Exception:
                    pass
            if isinstance(item, dict):
                texts = item.get("rec_texts")
                if texts is not None:
                    polys = item.get("rec_polys") or item.get("dt_polys") or []
                    for i, t in enumerate(texts):
                        bbox = cls._box_to_rect(polys[i]) if polys and i < len(polys) else None
                        items.append({"text": str(t), "bbox": bbox})
                    return
                for v in item.values():
                    collect(v)
                return
            if isinstance(item, (list, tuple)):
                # 2.x 的 [box, (text, conf)] 词条
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
                    collect(sub)

        collect(raw)
        return items

    @staticmethod
    def _extract_lines(raw: Any) -> list[str]:
        """从 PaddleOCR 2.x / 3.x 的返回结构里提取文本行（容忍不同版本格式）。"""
        lines: list[str] = []

        def collect(item: Any) -> None:
            if item is None:
                return
            if isinstance(item, str):
                lines.append(item)
                return
            # PaddleOCR 3.x 的 OCRResult 对象带 .json（字段或方法）
            if hasattr(item, "json"):
                try:
                    item = item.json if not callable(item.json) else item.json()
                except Exception:
                    pass
            if isinstance(item, str):
                lines.append(item)
                return
            if isinstance(item, dict):
                texts = item.get("rec_texts")
                if texts:
                    for t in texts:
                        if isinstance(t, str):
                            lines.append(t)
                    return
                for v in item.values():
                    collect(v)
                return
            if isinstance(item, (list, tuple)):
                for sub in item:
                    collect(sub)

        collect(raw)

        seen: set[str] = set()
        out: list[str] = []
        for line in lines:
            line = line.strip()
            if line and line not in seen:
                seen.add(line)
                out.append(line)
        return out


# 全局单例（懒加载，构造时不触发 PaddleOCR 加载）
ocr_service = OCRService()
