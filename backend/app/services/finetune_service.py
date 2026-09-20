# -*- coding: utf-8 -*-
"""
领域微调服务（PEFT LoRA/QLoRA 再训练闭环）

打通「标注数据 → 领域微调 → 模型注册 → 部署」的核心训练能力，具体承担：

1. 训练集导出（2.1）：把数据库标注（NER/关系/分类）转换为 BIO 训练样本与 CoNLL 文本，
   纯 Python、确定性、零依赖；
2. 微调（2.2）：优先用 PEFT（LoRA，可选 QLoRA 4bit 量化）微调 SciBERT token classification；
   依赖（torch/transformers/peft）或模型缺失、训练异常时自动降级为「多数类基线」，
   保证流程永不中断；
3. 评估（2.3）：token 级精确率/召回率/F1 纯 Python 实现，全 O 预测返回 f1=0；
4. 产物（2.4/2.5）：peft 路径把 LoRA 权重合并回基座并保存为可直接被 `ner_service` 加载的
   完整 checkpoint（含 id2label/label2id）；基线路径仅记录确定性指标与标签映射。

设计约定（与项目「可插拔、可降级」一致）：
- 全部纯函数（导出/评估/BIO 映射）无第三方依赖，可独立单测；
- 训练仅在使用时懒加载 torch/transformers/peft，失败即降级；
- 微调产物落到 `moulds/scibert`（`NER_MODEL_PATH`）后，`ner_service` 自动在下次推理时加载。
"""
from __future__ import annotations

import json
import os
from collections import Counter
from typing import Any

from loguru import logger

from app.core.config import resolve_model_source, settings

# 默认 label（非实体）
O_LABEL = "O"


# ── 纯函数：训练集导出与标注转换 ───────────────────────────────
def entities_to_char_bio(text: str, entities: list[dict[str, Any]]) -> list[str]:
    """
    把实体区间映射为逐字符 BIO 标签序列（纯函数、确定性）。

    Args:
        text: 原始文本。
        entities: 实体列表，每项需含 `start`/`end`（字符区间）与可选的 `type`。

    Returns:
        与 `text` 等长的标签列表，值为 "O" / "B-TYPE" / "I-TYPE"。
    """
    tags = [O_LABEL] * len(text)
    for ent in entities or []:
        start = int(ent.get("start", 0))
        end = int(ent.get("end", start))
        etype = (ent.get("type") or "ENTITY").strip().upper()
        if not etype:
            continue
        if 0 <= start < end <= len(text):
            tags[start] = f"B-{etype}"
            for i in range(start + 1, end):
                tags[i] = f"I-{etype}"
    return tags


def _coerce_content(record: Any) -> dict[str, Any] | None:
    """把 Annotation 行（dict 或 ORM 对象）规整为 content dict。"""
    if isinstance(record, dict):
        content = record.get("content", record)
    else:
        content = getattr(record, "content", None)
        if content is None:
            content = record
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except (TypeError, ValueError):
            return None
    return content if isinstance(content, dict) else None


def _extract_sample(content: dict[str, Any]) -> dict[str, Any] | None:
    """从 content dict 提取一条 NER 训练样本 {"text", "entities"}。"""
    text = content.get("text") or content.get("sentence") or content.get("raw_text")
    entities = content.get("entities") or content.get("labels") or content.get("spans") or []
    if not isinstance(text, str) or not text.strip():
        return None
    valid_entities: list[dict[str, Any]] = []
    for ent in entities:
        if not isinstance(ent, dict):
            continue
        if "start" not in ent or "end" not in ent:
            continue
        valid_entities.append(ent)
    return {"text": text, "entities": valid_entities}


def export_ner_training_set(records: list[Any]) -> list[dict[str, Any]]:
    """
    把 DB 标注（Annotation 行或 dict）导出为 NER 训练样本列表（2.1，格式转换）。

    约定 content 结构：`{"text": str, "entities": [{"text","type","start","end"}]}`。
    无法解析为有效样本的记录被静默跳过。
    """
    samples: list[dict[str, Any]] = []
    for record in records or []:
        content = _coerce_content(record)
        if content is None:
            continue
        sample = _extract_sample(content)
        if sample is not None:
            samples.append(sample)
    return samples


def build_bio_examples(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    把训练样本转换为 BIO 示例（含逐字符标签），供训练与 CoNLL 导出使用。

    Returns:
        [{"text", "char_tags": [str, ...]}]
    """
    examples: list[dict[str, Any]] = []
    for s in samples or []:
        text = s.get("text", "")
        if not text:
            continue
        examples.append({"text": text, "char_tags": entities_to_char_bio(text, s.get("entities"))})
    return examples


def label_index(tags: list[str]) -> tuple[dict[str, int], dict[int, str]]:
    """由标签序列生成 label2id / id2label（"O" 固定为 0，其余按字典序）。"""
    labels = [O_LABEL] + sorted({t for t in tags if t and t != O_LABEL})
    id2label = dict(enumerate(labels))
    label2id = {label: idx for idx, label in id2label.items()}
    return label2id, id2label


def to_conll(examples: list[dict[str, Any]]) -> str:
    """把 BIO 示例导出为 CoNLL-2003 风格文本（逐字符一行：字\tTAG，样本间空行）。"""
    lines: list[str] = []
    for ex in examples or []:
        text = ex.get("text", "")
        tags = ex.get("char_tags") or []
        for ch, tag in zip(text, tags, strict=False):
            lines.append(f"{ch}\t{tag}")
        lines.append("")
    return "\n".join(lines)


def token_level_metrics(
    y_true: list[str],
    y_pred: list[str],
    ignore: str = O_LABEL,
) -> dict[str, Any]:
    """
    token 级精确率/召回率/F1（纯 Python，2.3）。

    约定：忽略位（默认 "O"）不计入正例；全 O 预测在非空真实标注上 f1=0。
    类型不一致但均为非 O 时，同时计一次 FP 与一次 FN。
    """
    if len(y_true) != len(y_pred):
        raise ValueError("y_true 与 y_pred 长度不一致")
    tp = fp = fn = 0
    for gt, pr in zip(y_true, y_pred, strict=True):
        gt = gt or ignore
        pr = pr or ignore
        if gt == ignore and pr == ignore:
            continue
        if gt == pr:
            tp += 1
        elif gt == ignore:
            fp += 1
        elif pr == ignore:
            fn += 1
        else:
            fp += 1
            fn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "support": tp + fn,
    }


# ── 微调服务 ───────────────────────────────────────────────
class FinetuneService:
    """领域微调门面：优先 PEFT LoRA/QLoRA，缺失依赖时降级为多数类基线。"""

    def __init__(self) -> None:
        self.backend = "none"  # none | baseline | peft

    def _probe_peft(self) -> bool:
        try:
            import peft  # noqa: F401
            import torch  # noqa: F401
            import transformers  # noqa: F401

            return True
        except Exception:  # pragma: no cover - 依赖缺失
            return False

    def _baseline_metrics(self, examples: list[dict[str, Any]]) -> tuple[dict[str, Any], str]:
        """多数类基线：预测出现频次最高的非 O 标签，返回确定性指标与标签映射。"""
        all_tags: list[str] = []
        for ex in examples:
            all_tags.extend(ex.get("char_tags") or [])
        label2id, id2label = label_index(all_tags)
        counter = Counter(t for t in all_tags if t and t != O_LABEL)
        majority = counter.most_common(1)[0][0] if counter else O_LABEL
        pred = [majority] * len(all_tags)
        metrics = token_level_metrics(all_tags, pred)
        artifacts = {
            "backend": "baseline",
            "majority_label": majority,
            "label_map": {"label2id": label2id, "id2label": id2label},
            "note": "依赖/模型缺失或数据不足，使用多数类基线（未产出可加载模型）",
        }
        return metrics, artifacts

    def train_ner(
        self,
        records: list[Any],
        output_dir: str | None = None,
        base_model: str | None = None,
        epochs: int = 3,
        lr: float = 2e-4,
        lora_r: int = 8,
        lora_alpha: int = 32,
        quantize: bool = False,
    ) -> dict[str, Any]:
        """
        微调 NER 模型（2.2）。返回 {"backend", "samples", "labels", "metrics", "artifacts"}。

        Args:
            records: DB 标注行或 dict 列表（见 `export_ner_training_set`）。
            output_dir: 微调产物目录（缺省 `settings.NER_MODEL_PATH`，即 `moulds/scibert`）。
            base_model: 基座（缺省 `settings.NER_MODEL`）。
            quantize: 是否尝试 QLoRA 4bit（需 bitsandbytes，缺失时自动退回标准 LoRA）。
        """
        samples = export_ner_training_set(records)
        examples = build_bio_examples(samples)
        if not examples:
            self.backend = "baseline"
            label2id, id2label = label_index([])
            return {
                "backend": "baseline",
                "samples": 0,
                "labels": [O_LABEL],
                "metrics": token_level_metrics([], []),
                "artifacts": {
                    "backend": "baseline",
                    "note": "无有效训练样本",
                    "label_map": {"label2id": label2id, "id2label": id2label},
                },
            }

        base_model = base_model or resolve_model_source(
            settings.NER_BASE_MODEL, settings.NER_BASE_MODEL_PATH
        )
        output_dir = output_dir or settings.NER_MODEL_PATH

        if self._probe_peft():
            try:
                metrics, artifacts = self._train_peft(
                    examples=examples,
                    output_dir=output_dir,
                    base_model=base_model,
                    epochs=epochs,
                    lr=lr,
                    lora_r=lora_r,
                    lora_alpha=lora_alpha,
                    quantize=quantize,
                )
                self.backend = "peft"
                return {
                    "backend": "peft",
                    "samples": len(samples),
                    "labels": list(artifacts["label_map"]["label2id"].keys()),
                    "metrics": metrics,
                    "artifacts": artifacts,
                }
            except Exception as e:  # 训练异常 → 降级基线
                logger.warning(f"PEFT 微调失败，降级为多数类基线：{e}")

        self.backend = "baseline"
        metrics, artifacts = self._baseline_metrics(examples)
        return {
            "backend": "baseline",
            "samples": len(samples),
            "labels": list(artifacts["label_map"]["label2id"].keys()),
            "metrics": metrics,
            "artifacts": artifacts,
        }

    def _train_peft(
        self,
        examples: list[dict[str, Any]],
        output_dir: str,
        base_model: str,
        epochs: int,
        lr: float,
        lora_r: int,
        lora_alpha: int,
        quantize: bool,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        import torch
        from peft import LoraConfig, get_peft_model
        from torch.utils.data import DataLoader, TensorDataset
        from transformers import AutoModelForTokenClassification, AutoTokenizer

        # 标签映射（含 O，>2 表示有真实 NER 类别）
        all_tags = [t for ex in examples for t in ex["char_tags"]]
        label2id, id2label = label_index(all_tags)

        tokenizer = AutoTokenizer.from_pretrained(base_model)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token if tokenizer.eos_token else "[PAD]"

        # QLoRA（4bit）：需 bitsandbytes，缺失时静默回退标准 LoRA（项目依赖未含 bitsandbytes）
        four_bit = False
        if quantize:
            try:
                import bitsandbytes  # noqa: F401
                from transformers import BitsAndBytesConfig

                quant_kwargs: dict[str, Any] = {
                    "quantization_config": BitsAndBytesConfig(load_in_4bit=True)
                }
                four_bit = True
            except Exception:
                logger.warning("QLoRA 依赖（bitsandbytes）缺失，退回标准 LoRA")
                quant_kwargs = {}
        else:
            quant_kwargs = {}

        model = AutoModelForTokenClassification.from_pretrained(
            base_model,
            num_labels=len(label2id),
            id2label=id2label,
            label2id=label2id,
            ignore_mismatched_sizes=True,
            **quant_kwargs,
        )

        input_ids, attention_masks, label_ids = self._tokenize_align(tokenizer, examples, label2id)

        dataset = TensorDataset(
            torch.tensor(input_ids, dtype=torch.long),
            torch.tensor(attention_masks, dtype=torch.long),
            torch.tensor(label_ids, dtype=torch.long),
        )
        loader = DataLoader(dataset, batch_size=4, shuffle=True)

        device = "cuda" if settings.NER_DEVICE == "cuda" and torch.cuda.is_available() else "cpu"
        model.to(device)

        lora_config = LoraConfig(
            r=lora_r,
            lora_alpha=lora_alpha,
            target_modules=["query", "value"],
            lora_dropout=0.1,
            bias="none",
            task_type="TOKEN_CLS",
        )
        model = get_peft_model(model, lora_config)

        optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
        loss_fn = torch.nn.CrossEntropyLoss(ignore_index=-100)

        model.train()
        for _ in range(max(1, epochs)):
            for batch in loader:
                b_input_ids, b_mask, b_labels = [b.to(device) for b in batch]
                optimizer.zero_grad()
                outputs = model(input_ids=b_input_ids, attention_mask=b_mask)
                logits = outputs.logits
                loss = loss_fn(logits.view(-1, logits.size(-1)), b_labels.view(-1))
                loss.backward()
                optimizer.step()

        # 评估（同训练集 token 级）
        golds, preds = self._evaluate(model, loader, device, id2label)
        metrics = token_level_metrics(golds, preds)

        # 合并 LoRA 回基座并保存完整 checkpoint（ner_service 可直接加载）。
        # 4bit 量化模型无法 merge，届时仅保存 adapter（需配基座加载）。
        os.makedirs(output_dir, exist_ok=True)
        saved_full = False
        if not four_bit:
            try:
                merged = model.merge_and_unload()
                merged.save_pretrained(output_dir)
                saved_full = True
            except Exception as e:  # merge 失败退化为仅保存 adapter
                logger.warning(f"LoRA 权重合并失败，仅保存 adapter：{e}")
        if not saved_full:
            model.save_pretrained(output_dir)
        tokenizer.save_pretrained(output_dir)
        with open(os.path.join(output_dir, "label_map.json"), "w", encoding="utf-8") as f:
            json.dump({"label2id": label2id, "id2label": id2label}, f, ensure_ascii=False)

        artifacts = {
            "backend": "peft",
            "output_dir": output_dir,
            "base_model": base_model,
            "label_map": {"label2id": label2id, "id2label": id2label},
            "epochs": epochs,
            "lr": lr,
            "lora_r": lora_r,
            "lora_alpha": lora_alpha,
            "quantize": four_bit,
        }
        return metrics, artifacts

    @staticmethod
    def _tokenize_align(
        tokenizer: Any,
        examples: list[dict[str, Any]],
        label2id: dict[str, int],
        max_length: int = 128,
    ) -> tuple[list[list[int]], list[list[int]], list[list[int]]]:
        """把逐字符 BIO 标签对齐到子词 token（特殊/pad 用 -100 忽略）。"""
        input_ids: list[list[int]] = []
        masks: list[list[int]] = []
        labels: list[list[int]] = []
        for ex in examples:
            enc = tokenizer(
                ex["text"],
                truncation=True,
                max_length=max_length,
                padding="max_length",
                return_offsets_mapping=True,
            )
            offsets = [tuple(o) for o in enc["offset_mapping"]]
            char_tags = ex["char_tags"]
            labs: list[int] = []
            for s, e in offsets:
                if s == e == 0:  # 特殊 token / padding
                    labs.append(-100)
                else:
                    c = char_tags[s] if s < len(char_tags) else O_LABEL
                    labs.append(label2id.get(c, label2id[O_LABEL]))
            input_ids.append(list(enc["input_ids"]))
            masks.append(list(enc["attention_mask"]))
            labels.append(labs)
        return input_ids, masks, labels

    @staticmethod
    def _evaluate(
        model: Any,
        loader: Any,
        device: str,
        id2label: dict[int, str],
    ) -> tuple[list[str], list[str]]:
        import torch

        model.eval()
        golds: list[str] = []
        preds: list[str] = []
        with torch.no_grad():
            for batch in loader:
                b_input_ids, b_mask, b_labels = [b.to(device) for b in batch]
                logits = model(input_ids=b_input_ids, attention_mask=b_mask).logits
                pred = torch.argmax(logits, dim=-1)
                active = b_labels != -100
                for i in range(b_input_ids.size(0)):
                    mask = active[i]
                    if not mask.any():
                        continue
                    preds.extend(id2label[x] for x in pred[i][mask].tolist())
                    golds.extend(id2label[x] for x in b_labels[i][mask].tolist())
        return golds, preds


# 全局单例（懒加载）
finetune_service = FinetuneService()
