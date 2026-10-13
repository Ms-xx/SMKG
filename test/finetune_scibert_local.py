# -*- coding: utf-8 -*-
"""
创新点A 本地重微调：用 SciERC 真实英文样本在 CPU 上 LoRA 微调 SciBERT，
解决 moulds/scibert 退化成全 O 的问题。

用法（SciMKG 环境）:
    python finetune_scibert_local.py [epochs] [lr] [lora_r] [outdir]
默认: epochs=5 lr=3e-4 lora_r=8 outdir=moulds/scibert-v2（先验证非0，再人工替换 moulds/scibert）

判定：在 dev 上 token 级 F1（非 O）> 0 才视为可用并落盘；否则报告失败、不动 moulds。
"""
from __future__ import annotations

import json
import os
import sys
import time

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE_DIR, "backend"))

from collections import Counter

import torch
from loguru import logger

from app.core.config import settings
from app.services import finetune_service as fs

TRAIN = r"D:\work\VSCodeWork\LX\download_data\SciERC\data\samples\train.jsonl"
DEV = r"D:\work\VSCodeWork\LX\download_data\SciERC\data\samples\dev.jsonl"


def load_samples(path: str) -> list[dict]:
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            rows.append(json.loads(ln))
    return rows


def _tokenize_align(tokenizer, texts, char_tags_list, label2id, max_length=256):
    input_ids, masks, labels = [], [], []
    for text, char_tags in zip(texts, char_tags_list):
        enc = tokenizer(
            text,
            truncation=True,
            max_length=max_length,
            padding="max_length",
            return_offsets_mapping=True,
        )
        labs = []
        for s, e in enc["offset_mapping"]:
            if s == e == 0:
                labs.append(-100)
            else:
                c = char_tags[s] if s < len(char_tags) else fs.O_LABEL
                labs.append(label2id.get(c, label2id[fs.O_LABEL]))
        input_ids.append(list(enc["input_ids"]))
        masks.append(list(enc["attention_mask"]))
        labels.append(labs)
    return (
        torch.tensor(input_ids, dtype=torch.long),
        torch.tensor(masks, dtype=torch.long),
        torch.tensor(labels, dtype=torch.long),
    )


def build_dataset(tokenizer, samples, label2id):
    examples = fs.build_bio_examples(samples)
    texts = [e["text"] for e in examples]
    tags = [e["char_tags"] for e in examples]
    return _tokenize_align(tokenizer, texts, tags, label2id)


def predict_gold(model, loader, device, id2label):
    from app.services.finetune_service import token_level_metrics

    model.eval()
    golds, preds = [], []
    with torch.no_grad():
        for batch in loader:
            b_ids, b_mask, b_lab = [b.to(device) for b in batch]
            logits = model(input_ids=b_ids, attention_mask=b_mask).logits
            pred = torch.argmax(logits, dim=-1)
            active = b_lab != -100
            for i in range(b_ids.size(0)):
                m = active[i]
                if not m.any():
                    continue
                preds.extend(id2label[x] for x in pred[i][m].tolist())
                golds.extend(id2label[x] for x in b_lab[i][m].tolist())
    return token_level_metrics(golds, preds)


def main() -> None:
    epochs = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    lr = float(sys.argv[2]) if len(sys.argv) > 2 else 3e-4
    lora_r = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    outdir = sys.argv[4] if len(sys.argv) > 4 else os.path.join(BASE_DIR, "moulds", "scibert-v2")

    train = load_samples(TRAIN)
    dev = load_samples(DEV)
    logger.info(f"train={len(train)} dev={len(dev)} epochs={epochs} lr={lr} lora_r={lora_r}")

    all_tags = [t for e in fs.build_bio_examples(train) for t in e["char_tags"]]
    label2id, id2label = fs.label_index(all_tags)
    logger.info(f"labels={list(label2id.keys())}")

    base = settings.NER_BASE_MODEL_PATH
    from transformers import AutoModelForTokenClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(base)
    model = AutoModelForTokenClassification.from_pretrained(
        base,
        num_labels=len(label2id),
        id2label=id2label,
        label2id=label2id,
        ignore_mismatched_sizes=True,
    )

    train_ids, train_mask, train_lab = build_dataset(tokenizer, train, label2id)
    dev_ids, dev_mask, dev_lab = build_dataset(tokenizer, dev, label2id)

    from torch.utils.data import DataLoader, TensorDataset

    device = "cuda" if settings.NER_DEVICE == "cuda" and torch.cuda.is_available() else "cpu"
    model.to(device)
    train_loader = DataLoader(
        TensorDataset(train_ids, train_mask, train_lab), batch_size=8, shuffle=True
    )
    dev_loader = DataLoader(TensorDataset(dev_ids, dev_mask, dev_lab), batch_size=16)

    from peft import LoraConfig, get_peft_model

    lora = LoraConfig(
        r=lora_r,
        lora_alpha=lora_r * 4,
        target_modules=["query", "value"],
        lora_dropout=0.1,
        bias="none",
        task_type="TOKEN_CLS",
    )
    model = get_peft_model(model, lora)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    loss_fn = torch.nn.CrossEntropyLoss(ignore_index=-100)

    model.train()
    t0 = time.perf_counter()
    for ep in range(1, epochs + 1):
        total = 0.0
        for b_ids, b_mask, b_lab in train_loader:
            b_ids, b_mask, b_lab = b_ids.to(device), b_mask.to(device), b_lab.to(device)
            optimizer.zero_grad()
            logits = model(input_ids=b_ids, attention_mask=b_mask).logits
            loss = loss_fn(logits.view(-1, logits.size(-1)), b_lab.view(-1))
            loss.backward()
            optimizer.step()
            total += loss.item()
        dev_metrics = predict_gold(model, dev_loader, device, id2label)
        logger.info(
            f"[epoch {ep}/{epochs}] train_loss={total/len(train_loader):.4f} "
            f"dev_f1={dev_metrics['f1']:.4f} dev_support={dev_metrics['support']}"
        )
    logger.info(f"finished in {time.perf_counter()-t0:.1f}s")

    dev_metrics = predict_gold(model, dev_loader, device, id2label)
    logger.info(f"final dev metrics: {dev_metrics}")
    if dev_metrics["f1"] <= 0:
        logger.error("dev F1=0：模型退化，未落盘；请增大 epochs / 样本或调整 lr")
        sys.exit(1)

    os.makedirs(outdir, exist_ok=True)
    merged = model.merge_and_unload()
    merged.save_pretrained(outdir)
    tokenizer.save_pretrained(outdir)
    with open(os.path.join(outdir, "label_map.json"), "w", encoding="utf-8") as f:
        json.dump({"label2id": label2id, "id2label": id2label}, f, ensure_ascii=False)
    logger.info(f"saved non-zero NER checkpoint -> {outdir}")
    print(json.dumps({"outdir": outdir, "dev_f1": dev_metrics["f1"],
                      "labels": list(label2id.keys())}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()