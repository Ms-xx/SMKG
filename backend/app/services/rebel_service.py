# -*- coding: utf-8 -*-
"""
REBEL / OpenIE 关系抽取服务（seq2seq 关系分类）

用 transformers 加载 REBEL 模型（Babelscape/rebel-large）做关系三元组抽取，
替代/补充原有「规则 + LLM」关系抽取。

依赖策略（可插拔、可降级）：
- 安装 `transformers` 且 `moulds/rebel` 下存在 checkpoint（或可从 HF 加载）时，生成三元组；
- 未安装依赖 / 模型缺失 / 未启用时自动降级，`extract` 返回空列表，关系抽取回退到规则/LLM。
"""
from __future__ import annotations

import re
from typing import Any

from loguru import logger

from app.core.config import resolve_model_source, settings


def parse_rebel_output(text: str) -> list[dict[str, str]]:
    """
    解析 REBEL seq2seq 输出为三元组列表（纯函数，供测试与降级解码使用）。

    REBEL 输出形如：
    `<triplet> head <subj> tail <obj> relation <triplet> head2 <subj> tail2 <obj> relation2 </s>`

    Returns:
        [{"head", "tail", "type"}]
    """
    triplets: list[dict[str, str]] = []
    subject, object_, relation = "", "", ""
    text = text.replace("<s>", "").replace("<pad>", "").replace("</s>", "").strip()
    current = "x"
    for token in text.split():
        if token == "<triplet>":
            current = "head"
            if relation != "":
                triplets.append(
                    {
                        "head": subject.strip(),
                        "tail": object_.strip(),
                        "type": relation.strip(),
                    }
                )
                relation = ""
            subject = ""
        elif token == "<subj>":
            current = "tail"
            if relation != "":
                triplets.append(
                    {
                        "head": subject.strip(),
                        "tail": object_.strip(),
                        "type": relation.strip(),
                    }
                )
            object_ = ""
        elif token == "<obj>":
            current = "rel"
            relation = ""
        else:
            if current == "head":
                subject += " " + token
            elif current == "tail":
                object_ += " " + token
            elif current == "rel":
                relation += " " + token
    if subject != "" and object_ != "" and relation != "":
        triplets.append(
            {
                "head": subject.strip(),
                "tail": object_.strip(),
                "type": relation.strip(),
            }
        )
    return [t for t in triplets if t["head"] and t["tail"] and t["type"]]


def normalize_relation_type(raw: str) -> str:
    """
    将 REBEL 自然语言关系类型规范为 SCREAMING_SNAKE_CASE（可安全用作 Neo4j 关系类型）。

    例："located in the administrative territorial entity" ->
        "LOCATED_IN_THE_ADMINISTRATIVE_TERRITORIAL_ENTITY"
    """
    cleaned = re.sub(r"[^A-Za-z0-9]+", " ", raw or "").strip()
    return "_".join(cleaned.upper().split())


class RebelService:
    """REBEL 关系抽取服务（延迟加载、可降级）。"""

    def __init__(self) -> None:
        self.backend = "none"
        self._model = None
        self._tokenizer = None
        self._load_error: str | None = None

    @property
    def available(self) -> bool:
        return self._model is not None

    def _load(self) -> None:
        if self._model is not None or self.backend == "unavailable":
            return
        if not settings.RELATION_EXTRACTION_ENABLED:
            self.backend = "unavailable"
            self._load_error = "RELATION_EXTRACTION_ENABLED 为 False"
            logger.warning("REBEL 未启用，关系抽取将回退到规则/LLM")
            return
        model_source = resolve_model_source(
            settings.REBEL_MODEL, settings.REBEL_MODEL_PATH
        )
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(model_source)
            self._model = AutoModelForSeq2SeqLM.from_pretrained(model_source)
            if settings.REBEL_DEVICE == "cuda":
                self._model.to("cuda")
            self.backend = "rebel-seq2seq"
            logger.info("REBEL 关系抽取模型已加载：%s", model_source)
        except Exception as e:  # pragma: no cover - 依赖/模型缺失
            self.backend = "unavailable"
            self._load_error = str(e)
            logger.warning(
                "REBEL 不可用，关系抽取将回退到规则/LLM（放置 checkpoint 到 %s）：%s",
                settings.REBEL_MODEL_PATH,
                e,
            )

    def extract(
        self, text: str, entities: list[dict[str, Any]] | None = None
    ) -> list[dict[str, Any]]:
        """
        抽取文本中的关系三元组。

        Args:
            text: 待抽取文本。
            entities: 已提取的实体列表（用于对齐 source_type/target_type，可选）。

        Returns:
            [{"source", "source_type", "target", "target_type", "relation_type",
              "confidence", "context"}]
        """
        if not text or not text.strip():
            return []
        self._load()
        if self._model is None:
            return []

        try:
            model_inputs = self._tokenizer(
                text,
                max_length=512,
                padding=True,
                truncation=True,
                return_tensors="pt",
            )
            device = self._model.device
            generated = self._model.generate(
                model_inputs["input_ids"].to(device),
                attention_mask=model_inputs["attention_mask"].to(device),
                max_length=settings.REBEL_MAX_LENGTH,
                length_penalty=0,
                num_beams=settings.REBEL_NUM_BEAMS,
            )
            decoded = self._tokenizer.batch_decode(generated, skip_special_tokens=False)

            relations: list[dict[str, Any]] = []
            seen: set[tuple[str, str, str]] = set()
            for d in decoded:
                for triplet in parse_rebel_output(d):
                    source = triplet["head"]
                    target = triplet["tail"]
                    rel_type = normalize_relation_type(triplet["type"])
                    key = (source.lower(), target.lower(), rel_type)
                    if key in seen:
                        continue
                    seen.add(key)
                    relations.append(
                        {
                            "source": source,
                            "source_type": self._match_entity_type(source, entities),
                            "target": target,
                            "target_type": self._match_entity_type(target, entities),
                            "relation_type": rel_type,
                            "confidence": settings.REBEL_CONFIDENCE,
                            "context": text,
                        }
                    )
            return relations
        except Exception as e:  # pragma: no cover
            logger.warning("REBEL 推理失败：%s", e)
            return []

    @staticmethod
    def _match_entity_type(text: str, entities: list[dict[str, Any]] | None) -> str:
        """将 REBEL 实体对齐到 NER 输出，返回对应类型；未命中返回 "ENTITY"。"""
        if not entities:
            return "ENTITY"
        tl = text.lower()
        for e in entities:
            ent_text = (e.get("text") or "").lower()
            if ent_text and (ent_text in tl or tl in ent_text):
                return e.get("type") or "ENTITY"
        return "ENTITY"


# 全局单例（懒加载，构造时不触发模型加载）
rebel_service = RebelService()
