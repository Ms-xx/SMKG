# -*- coding: utf-8 -*-
"""
版面分析服务（LayoutLMv3）

对文档页面图像做版面分析，输出元素（标题/段落/列表/表格/图）及其归一化 bbox。

依赖策略（可插拔、可降级）：
- 已安装 `transformers` 且模型可用时，使用 LayoutLMv3（PubLayNet 微调）做 token 级分类；
- 未安装 / 模型缺失时自动降级，返回空结果，不影响解析主流程。

输入说明：
- LayoutLMv3 需要「页面图像 + OCR 词框」一起输入；词框通常来自 PaddleOCR
  （见 `ocr_service.OCRService.recognize_with_boxes`）。
- PubLayNet 微调模型仅覆盖 title/text/list/table/figure 五类；公式由 `formula_service`
  （LaTeX-OCR/pix2tex）处理，页眉页脚由本文档的 `detect_header_footer` 依据纵向位置启发式判定。
- 模型加载优先使用 `moulds/<模型>` 本地目录，缺失时回退 HuggingFace 名称（`resolve_model_source`）。
"""
from __future__ import annotations

import re
from typing import Any

from loguru import logger

from app.core.config import resolve_model_source, settings

# 元素类型（英文 key → 中文名）
ELEMENT_TYPE_ZH = {
    "title": "标题",
    "paragraph": "段落",
    "list": "列表",
    "table": "表格",
    "figure": "图",
    "formula": "公式",
    "header": "页眉",
    "footer": "页脚",
}

# PubLayNet 标签 → 本系统元素类型
DEFAULT_LABEL_MAP = {
    "TITLE": "title",
    "TEXT": "paragraph",
    "LIST": "list",
    "TABLE": "table",
    "FIGURE": "figure",
}


def map_label(raw_label: str, label_map: dict[str, str] | None = None) -> str:
    """把模型标签映射为本系统元素类型；未知标签回退为段落。"""
    label_map = label_map or DEFAULT_LABEL_MAP
    return label_map.get((raw_label or "").upper(), "paragraph")


def normalize_boxes(boxes: list[list[float]], width: float, height: float) -> list[list[int]]:
    """把像素坐标 [x0,y0,x1,y1] 归一化到 LayoutLMv3 要求的 0-1000 尺度。"""
    if not width or not height:
        return [[0, 0, 0, 0] for _ in boxes]
    out: list[list[int]] = []
    for x0, y0, x1, y1 in boxes:
        out.append(
            [
                max(0, min(1000, int(x0 / width * 1000))),
                max(0, min(1000, int(y0 / height * 1000))),
                max(0, min(1000, int(x1 / width * 1000))),
                max(0, min(1000, int(y1 / height * 1000))),
            ]
        )
    return out


def map_token_labels_to_words(
    word_ids: list[int | None],
    token_predictions: list[int],
    id2label: dict[int, str],
    label_map: dict[str, str] | None = None,
) -> list[str]:
    """把 token 级预测映射到 word 级标签（取每个词首个 token 的预测）。"""
    word_labels: list[str] = []
    last_word: int | None = None
    for wid, pred_id in zip(word_ids, token_predictions, strict=False):
        if wid is None or wid == last_word:
            continue
        raw = id2label.get(int(pred_id), "TEXT")
        word_labels.append(map_label(raw, label_map))
        last_word = wid
    return word_labels


def group_blocks(
    words: list[str], boxes: list[list[float]], labels: list[str]
) -> list[dict[str, Any]]:
    """将同一标签的相邻词合并为块，输出元素 + 合并 bbox。"""
    elements: list[dict[str, Any]] = []
    if not words:
        return elements

    cur_label = labels[0]
    cur_words = [words[0]]
    cur_box = list(boxes[0])
    for i in range(1, len(words)):
        b = boxes[i]
        if labels[i] == cur_label:
            cur_words.append(words[i])
            cur_box[0] = min(cur_box[0], b[0])
            cur_box[1] = min(cur_box[1], b[1])
            cur_box[2] = max(cur_box[2], b[2])
            cur_box[3] = max(cur_box[3], b[3])
        else:
            elements.append({"type": cur_label, "text": " ".join(cur_words), "bbox": cur_box})
            cur_label = labels[i]
            cur_words = [words[i]]
            cur_box = list(b)

    elements.append({"type": cur_label, "text": " ".join(cur_words), "bbox": cur_box})
    return elements


def is_page_number(text: str) -> bool:
    """判断文本是否纯页码（如 "5"、"1/12"、"第 3 页"、"Page 5"）。"""
    t = re.sub(r"[\s·\-—（）()]", "", (text or "").strip().lower())
    if not t:
        return False
    t = re.sub(r"^page", "", t)
    t = re.sub(r"^第|页$", "", t)
    t = re.sub(r"^(p\.?|no\.?)", "", t)
    return bool(re.fullmatch(r"\d+(/\d+)?", t))


def detect_header_footer(
    elements: list[dict[str, Any]],
    page_height: float,
    header_ratio: float = 0.12,
    footer_ratio: float = 0.88,
) -> list[dict[str, Any]]:
    """
    依据纵向位置，把位于页面顶部 / 底部的文本块标记为页眉 / 页脚。

    - bbox 形如 [x0, y0, x1, y1]（像素）。
    - 元素整体位于 y1 <= header_ratio*page_height → 页眉（header）。
    - 元素整体位于 y0 >= footer_ratio*page_height → 页脚（footer）；纯页码额外标记 is_page_number。
    """
    header_y = header_ratio * page_height
    footer_y = footer_ratio * page_height
    out: list[dict[str, Any]] = []
    for el in elements:
        bbox = el.get("bbox") or [0.0, 0.0, 0.0, 0.0]
        y0, y1 = float(bbox[1]), float(bbox[3])
        new_el = dict(el)
        if y1 <= header_y:
            new_el["type"] = "header"
        elif y0 >= footer_y:
            new_el["type"] = "footer"
            if is_page_number(str(el.get("text", ""))):
                new_el["is_page_number"] = True
        out.append(new_el)
    return out


class LayoutAnalysisService:
    """LayoutLMv3 封装，延迟加载、可降级。"""

    def __init__(self):
        self.backend = "none"
        self._processor = None
        self._model = None
        self._id2label: dict[int, str] = {}
        self._load_error: str | None = None

    @property
    def available(self) -> bool:
        return self._model is not None

    def _load(self) -> None:
        if self._model is not None or self.backend == "unavailable":
            return
        try:
            from transformers import AutoModelForTokenClassification, AutoProcessor

            model_source = resolve_model_source(settings.LAYOUT_MODEL, settings.LAYOUT_MODEL_PATH)
            self._processor = AutoProcessor.from_pretrained(model_source, apply_ocr=False)
            self._model = AutoModelForTokenClassification.from_pretrained(model_source)
            self._model.to(settings.LAYOUT_DEVICE)
            self._model.eval()
            cfg = getattr(self._model, "config", None)
            self._id2label = getattr(cfg, "id2label", None) or {}
            self.backend = "layoutlmv3"
            logger.info("LayoutLMv3 已加载：%s", model_source)
        except Exception as e:  # pragma: no cover - 依赖/模型缺失
            self.backend = "unavailable"
            self._load_error = str(e)
            logger.warning(
                "LayoutLMv3 不可用，版面分析将跳过（放置模型到 %s 或 `pip install transformers` 并下载 %s）：%s",
                settings.LAYOUT_MODEL_PATH,
                settings.LAYOUT_MODEL,
                e,
            )

    def analyze(
        self,
        image_path: str,
        words: list[str],
        boxes: list[list[float]],
        page_height: float | None = None,
    ) -> dict[str, Any]:
        """
        版面分析。

        Args:
            image_path: 页面图像路径。
            words: OCR 逐词文本（与 boxes 对齐）。
            boxes: 逐词像素 bbox [x0, y0, x1, y1]（与 words 对齐）。
            page_height: 页面像素高度；传入时对结果做页眉/页脚启发式标记。

        Returns:
            {"elements": [{"type", "text", "bbox"}], "backend"}
        """
        self._load()
        if self._model is None or not words:
            return {"elements": [], "backend": self.backend}
        try:
            elements, image_height = self._infer(image_path, words, boxes)
            # 页眉页脚阈值基于像素高度：优先显式传入，否则用渲染图像实际高度
            ref_height = page_height or image_height
            if ref_height:
                elements = detect_header_footer(elements, float(ref_height))
            return {"elements": elements, "backend": self.backend}
        except Exception as e:  # pragma: no cover
            logger.warning("LayoutLMv3 推理失败：%s", e)
            return {"elements": [], "backend": self.backend}

    def _infer(
        self, image_path: str, words: list[str], boxes: list[list[float]]
    ) -> tuple[list[dict[str, Any]], float]:
        from PIL import Image

        image = Image.open(image_path).convert("RGB")
        width, height = image.size
        norm_boxes = normalize_boxes(boxes, width, height)

        encoding = self._processor(  # type: ignore[misc]
            image,
            words=words,
            boxes=norm_boxes,
            return_tensors="pt",
            truncation=True,
        )
        outputs = self._model(**encoding)  # type: ignore[misc]
        predictions = outputs.logits.argmax(-1).squeeze().tolist()
        if isinstance(predictions, int):  # 单 token 时 squeeze 成标量
            predictions = [predictions]

        word_ids = encoding.word_ids()
        labels = map_token_labels_to_words(word_ids, predictions, self._id2label)
        return group_blocks(words, boxes, labels), float(height)


# 全局单例（懒加载，构造时不触发模型加载）
layout_service = LayoutAnalysisService()
