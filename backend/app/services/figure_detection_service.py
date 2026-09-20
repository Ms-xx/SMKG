# -*- coding: utf-8 -*-
"""
图表/公式检测服务（YOLOv8 / ultralytics）

用于在文档页面图像上检测 figure / table / formula 等区域，输出边界框，
供后续「公式识别（`formula_service`）」「图表描述（`chart_description_service`）」裁剪使用。

依赖策略（可插拔、可降级）：
- 已安装 `ultralytics` 且 `moulds/yolov8` 下存在 `*.pt` 权重时，加载 YOLOv8；
- 权重/依赖缺失时自动降级，`detect` 返回空列表，不影响解析主流程；
- 权重可用 YOLOv8 官方预训练权重，或用 DocLayNet 预训练权重（含 figure/table/formula 等类别）。
"""
from __future__ import annotations

import os
from typing import Any

from loguru import logger

from app.core.config import settings


class FigureDetectionService:
    """YOLOv8 图表/公式区域检测，延迟加载、可降级。"""

    def __init__(self):
        self.backend = "none"
        self._model = None
        self._names: dict[int, str] = {}
        self._load_error: str | None = None

    @property
    def available(self) -> bool:
        return self._model is not None

    def _find_weights(self) -> str | None:
        """在 `moulds/yolov8` 下查找第一个 `.pt`/`.pth` 权重文件。"""
        directory = settings.FIGURE_DETECT_MODEL_PATH
        if not directory or not os.path.isdir(directory):
            return None
        for name in sorted(os.listdir(directory)):
            lower = name.lower()
            if lower.endswith(".pt") or lower.endswith(".pth"):
                return os.path.join(directory, name)
        return None

    def _load(self) -> None:
        if self._model is not None or self.backend == "unavailable":
            return
        weights = self._find_weights()
        if not weights:
            self.backend = "unavailable"
            self._load_error = f"未在 {settings.FIGURE_DETECT_MODEL_PATH} 找到 YOLOv8 权重（*.pt）"
            logger.warning("YOLOv8 检测不可用，图表/公式检测将跳过：%s", self._load_error)
            return
        try:
            from ultralytics import YOLO  # type: ignore

            self._model = YOLO(weights)
            self._names = {int(k): str(v) for k, v in (self._model.names or {}).items()}
            self.backend = "yolov8"
            logger.info("YOLOv8 已加载：%s", weights)
        except Exception as e:  # pragma: no cover - 依赖缺失
            self.backend = "unavailable"
            self._load_error = str(e)
            logger.warning(
                "YOLOv8 不可用（`pip install ultralytics` 并将 *.pt 放到 %s）：%s",
                settings.FIGURE_DETECT_MODEL_PATH,
                e,
            )

    def detect(self, image_path: str) -> list[dict[str, Any]]:
        """
        检测图像中的图表/公式区域。

        Args:
            image_path: 页面（或区域）图像路径。

        Returns:
            [{"class": str, "class_id": int, "confidence": float, "bbox": [x0, y0, x1, y1]}]
        """
        self._load()
        if self._model is None:
            return []
        try:
            results = self._model.predict(
                source=image_path, conf=settings.FIGURE_DETECT_CONF, verbose=False
            )
            detections: list[dict[str, Any]] = []
            for r in results:
                boxes = getattr(r, "boxes", None)
                if boxes is None:
                    continue
                for box in boxes:
                    xyxy = box.xyxy[0].tolist()
                    cls_id = int(box.cls[0])
                    detections.append(
                        {
                            "class": self._names.get(cls_id, str(cls_id)),
                            "class_id": cls_id,
                            "confidence": round(float(box.conf[0]), 4),
                            "bbox": [round(float(v), 1) for v in xyxy],
                        }
                    )
            return detections
        except Exception as e:  # pragma: no cover
            logger.warning("YOLOv8 推理失败：%s", e)
            return []


# 全局单例（懒加载，构造时不触发模型加载）
figure_detection_service = FigureDetectionService()
