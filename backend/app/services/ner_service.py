# -*- coding: utf-8 -*-
"""
命名实体识别服务（NER，SciBERT 微调 token classification）

用 transformers + 微调后的 SciBERT（或领域模型）做 token 级分类，替换/增强原有「规则 + LLM」抽取。

依赖策略（可插拔、可降级）：
- 已安装 `transformers` 且 `moulds/scibert` 下存在**微调后含 id2label** 的 NER checkpoint 时，加载并抽取；
- 未放置微调 checkpoint / 未安装依赖时自动降级，`extract` 返回空列表，抽取回退到规则/LLM；
- 基座 `scibert_scivocab_uncased` 是掩码语言模型（无 id2label），不可直接做 NER，需在标注集上微调后放入 moulds/scibert。
"""
from __future__ import annotations

import os
import time
from typing import Any

from loguru import logger

from app.core.config import settings
from app.utils.business_metrics import observe_model_inference


def merge_bio_spans(
    words: list[str],
    tags: list[str],
    starts: list[int],
    ends: list[int],
) -> list[dict[str, Any]]:
    """
    把 BIO/IOB2 标签序列合并为实体（纯函数，供测试与降级解码使用）。

    Args:
        words: token 文本列表。
        tags: 与 words 对齐的 BIO 标签（如 "B-Material"/"I-Property"/"O"）。
        starts/ends: 每个 token 在原文本中的字符区间。

    Returns:
        [{"text", "type", "start", "end"}]
    """
    entities: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for word, tag, s, e in zip(words, tags, starts, ends, strict=False):
        t = (tag or "").strip().upper()
        if t.startswith("B-"):
            if current:
                entities.append(current)
            current = {"text": word, "type": t[2:], "start": s, "end": e}
        elif t.startswith("I-") and current is not None and current["type"] == t[2:]:
            current["text"] = current["text"] + word
            current["end"] = e
        else:
            if current:
                entities.append(current)
            current = None
    if current:
        entities.append(current)
    return entities


class NERService:
    """SciBERT 微调 NER，延迟加载、可降级。"""

    def __init__(self):
        self.backend = "none"
        self._pipe = None
        self._load_error: str | None = None

    @property
    def available(self) -> bool:
        return self._pipe is not None

    def _load(self) -> None:
        if self._pipe is not None or self.backend == "unavailable":
            return
        # NER 仅使用本地「微调后」checkpoint（基座 SciBERT 是 MLM，无 id2label，不可直接做 NER）
        model_source = settings.NER_MODEL_PATH
        if not model_source or not os.path.isdir(model_source) or not os.listdir(model_source):
            self.backend = "unavailable"
            self._load_error = f"未在 {model_source} 找到微调后的 NER checkpoint（含 id2label）"
            logger.warning("NER 不可用，抽取将回退到规则/LLM：%s", self._load_error)
            return
        try:
            from transformers import (
                AutoModelForTokenClassification,
                AutoTokenizer,
                pipeline,
            )

            tokenizer = AutoTokenizer.from_pretrained(model_source)
            model = AutoModelForTokenClassification.from_pretrained(model_source)

            id2label = getattr(model.config, "id2label", None)
            if not id2label or len(id2label) <= 2:
                # 基座模型无 id2label 或仅有 O/通用标签，无法做有效 NER
                self.backend = "unavailable"
                self._load_error = (
                    f"{model_source} 不是有效的 NER checkpoint（缺少 id2label）；请使用微调后的模型"
                )
                logger.warning("NER 不可用：%s", self._load_error)
                return

            self._pipe = pipeline(
                "ner",
                model=model,
                tokenizer=tokenizer,
                device=0 if settings.NER_DEVICE == "cuda" else -1,
                aggregation_strategy=settings.NER_AGGREGATION,
            )
            self.backend = "scibert-ner"
            logger.info("SciBERT NER 已加载：%s", model_source)
        except Exception as e:  # pragma: no cover - 依赖/模型缺失
            self.backend = "unavailable"
            self._load_error = str(e)
            logger.warning(
                "NER 不可用，抽取将回退到规则/LLM（放置微调 checkpoint 到 %s）：%s",
                settings.NER_MODEL_PATH,
                e,
            )

    def extract(self, text: str) -> list[dict[str, Any]]:
        """
        抽取文本中的命名实体。

        Args:
            text: 待抽取文本。

        Returns:
            [{"text", "type", "start", "end", "confidence"}]
        """
        if not text or not text.strip():
            return []
        self._load()
        if self._pipe is None:
            return []
        try:
            t0 = time.perf_counter()
            results = self._pipe(text)
            observe_model_inference("ner", time.perf_counter() - t0)
            entities: list[dict[str, Any]] = []
            for r in results:
                entity_type = r.get("entity_group") or r.get("entity") or "ENTITY"
                start = int(r.get("start", 0))
                end = int(r.get("end", start))
                entities.append(
                    {
                        "text": text[start:end],
                        "type": entity_type,
                        "start": start,
                        "end": end,
                        "confidence": round(float(r.get("score", 1.0)), 4),
                    }
                )
            return entities
        except Exception as e:  # pragma: no cover
            logger.warning("NER 推理失败：%s", e)
            return []


# 全局单例（懒加载，构造时不触发模型加载）
ner_service = NERService()
