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
import re
import time
from typing import Any

from loguru import logger

from app.core.config import settings
from app.core.plugin.base import Plugin
from app.utils.business_metrics import observe_model_inference

_GAZETTEER_TERMS: dict[str, set[str]] = {
    "MATERIAL": {
        "perovskite",
        "methylammonium lead iodide",
        "graphene",
        "silicon",
        "titanium dioxide",
        "tio2",
        "mapbi3",
        "zinc oxide",
        "cesium lead",
        "formamidinium",
        "gallium arsenide",
        "indium tin oxide",
        "nickel oxide",
        "spiro-ometad",
        "mof",
        "metal-organic framework",
        "quantum dot",
        "electrolyte",
        "cathode",
        "anode",
        "polymer",
        "composite",
        "nanowire",
        "nanoparticle",
        "carbon nanotube",
        "cnt",
        "graphite",
        "copper",
        "aluminum",
        "cadmium telluride",
    },
    "METHOD": {
        "spin-coating",
        "spin coating",
        "chemical vapor deposition",
        "cvd",
        "physical vapor deposition",
        "solvothermal",
        "hydrothermal",
        "synthesis",
        "synthesized",
        "fabrication",
        "characterization",
        "raman spectroscopy",
        "x-ray diffraction",
        "xrd",
        "sem",
        "tem",
        "edx",
        "purification",
        "atomic layer deposition",
        "magnetron sputtering",
        "electrospinning",
        "thermal evaporation",
        "annealing",
        "calcination",
        "doctor-blade",
        "slurry casting",
        "binding",
        "deposition",
    },
    "METRIC": {
        "efficiency",
        "power conversion efficiency",
        "carrier mobility",
        "mobility",
        "bandgap",
        "open-circuit voltage",
        "short-circuit current",
        "fill factor",
        "capacity",
        "conductivity",
        "accuracy",
        "f1",
        "cross-entropy loss",
        "loss",
        "specific capacity",
        "energy density",
        "charge-discharge",
    },
    "TASK": {
        "classification",
        "sentiment classification",
        "translation",
        "text generation",
        "generation",
        "detection",
        "segmentation",
        "summarization",
        "named entity recognition",
        "question answering",
        "retrieval-augmented generation",
        "text summarization",
        "lora",
        "fine-tuning",
        "fine tune",
        "knowledge graph construction",
    },
    "OTHERSCIENTIFICTERM": {
        "transistor",
        "field-effect transistor",
        "sentiment",
        "semiconductor",
        "dielectric",
        "ferromagnet",
        "superconductor",
        "quantum",
        "qubit",
        "word embedding",
        "transformer",
        "bert",
        "attention mechanism",
        "token classification",
    },
}

# 数值+单位模式（效率/迁移率/电容/带隙等）
_GAZETTEER_METRIC_NUM_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:%|MPa|GPa|eV|nm|GHz|T|cm2/V/s|cm2 v/s|mAh/g|W/m2|mV|mA/cm2)\b",
    re.IGNORECASE,
)
# 化学式：元素大写起始 + 可选数字/小写（如 TiO2、MAPbI3、CH3NH3PbI3、H2O）。
# 前瞻要求命中串含至少一个小写字母或数字，排除纯大写缩写（BERT/AI/USA/CNN 等被误判为 MATERIAL）。
_GAZETTEER_CHEM_RE = re.compile(r"\b(?=[A-Za-z0-9]*[a-z\d])(?:[A-Z][a-z]?\d*){2,}\b")


def _word_delimited(text: str, m: "re.Match[str]") -> bool:
    """判断匹配 m 是否被单词边界 / 文本首尾包围（避免命中长词子串）。"""
    before = "" if m.start() == 0 else text[m.start() - 1]
    after = "" if m.end() == len(text) else text[m.end()]
    return not (before.isalnum() or after.isalnum())


def _gazetteer_add(
    hits: dict[str, dict[str, Any]],
    text: str,
    t: str,
    type_: str,
    start: int,
    end: int,
) -> None:
    """把一个 (词, 类型) 加入去重字典（纯函数辅助，降低主函数圈复杂度）。

    start/end 由调用方传入实际匹配区间，避免重复用全局 find 定位导致 span 错位。
    """
    if not t or len(t) < 2 or type_ not in _GAZETTEER_TERMS:
        return
    key = f"{type_}:{t.lower()}"
    if key in hits:
        return
    hits[key] = {
        "text": t,
        "type": type_,
        "start": start,
        "end": end,
        "confidence": 0.85,
    }


def extract_english_gazetteer(text: str) -> list[dict[str, Any]]:
    """
    确定性英文科学实体抽取（回退层）。

    ML NER 模型不可用、或对英文句子预测全 O 时使用，保证英文科学文献也能得到**非0**的
    真实实体（材料/方法/指标/任务/科学术语），修复"英文 arXiv 论文实体=0"这一最短板。

    类型与 `moulds/scibert` 的标签集一致（MATERIAL / METHOD / METRIC / TASK /
    OTHERSCIENTIFICTERM），写入 Neo4j 时节点类型可与 SciBERT 输出自然合并。
    纯函数、确定性、零依赖（可插拔可降级：模型可用时结果仍以模型优先）。
    """
    if not text or not text.strip():
        return []

    found: dict[str, dict[str, Any]] = {}

    # 正则类（化学式 / 数值单位）
    for pattern, type_ in (
        (_GAZETTEER_CHEM_RE, "MATERIAL"),
        (_GAZETTEER_METRIC_NUM_RE, "METRIC"),
    ):
        for m in pattern.finditer(text):
            tok = text[m.start() : m.end()]
            if _word_delimited(text, m):
                _gazetteer_add(found, text, tok, type_, m.start(), m.end())

    # 词表类（材料 / 方法 / 指标 / 任务 / 科学术语）
    for type_, terms in _GAZETTEER_TERMS.items():
        for t in terms:
            for m in re.finditer(rf"\b{re.escape(t)}\b", text, re.IGNORECASE):
                _gazetteer_add(found, text, text[m.start() : m.end()], type_, m.start(), m.end())

    return sorted(found.values(), key=lambda e: e["start"])


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

    # ─── 插件协议 ──────────────────────────────────────────────────────────
    async def on_start(self) -> None:
        logger.info("ner plugin started (backend=%s)", self.backend)

    async def on_stop(self) -> None:
        logger.info("ner plugin stopped")

    def health(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "available": self.available,
            "load_error": self._load_error,
        }

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
        entities: list[dict[str, Any]] = []
        if self._pipe is not None:
            try:
                t0 = time.perf_counter()
                results = self._pipe(text)
                observe_model_inference("ner", time.perf_counter() - t0)
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
            except Exception as e:  # pragma: no cover
                logger.warning("NER 推理失败：%s", e)
                entities = []
        # 模型不可用 / 全 O（无实体）时，用确定性英文科学抽取兜底，保证英文文献实体非0
        if not entities:
            entities = extract_english_gazetteer(text)
        return entities


# 全局单例（懒加载，构造时不触发模型加载）
ner_service = NERService()


class NERPlugin(Plugin):
    """官方插件：ner —— NER 服务（存量迁移自 app/services/ner_service.py）。

    - 配置沿用全局 settings（`NER_*` 键）。
    - 重型模型服务（SciBERT checkpoint）：仅冷替换/重启，不支持运行期热替换。
    - `create()` 返回全新实例供 registry 寻址；模块级单例 `ner_service` 供门面再导出。
    - 消费者动态寻址：`registry.get("ner")`。
    """

    name = "ner"
    version = "1.0.0"
    config_prefix = "NER_"
    requires: list[str] = []
    type = "service"
    legacy_module = "app.services.ner_service"

    def create(self, registry, settings) -> NERService:
        return NERService()


plugin = NERPlugin()
