# -*- coding: utf-8 -*-
"""创新点A 冒烟测试：验证本地 moulds/scibert 微调 checkpoint 能对英文科学文本抽取出非0真实实体。
直接调用 ner_service（不依赖后端进程），可插拔：NER_DEVICE 默认 cpu，预留 cuda。
输出：非0实体列表 + 节点类型分布（供写入 Neo4j 前人工核对）。
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.core.config import settings
from app.services.ner_service import ner_service

print(f"[env] NER_ENABLED={settings.NER_ENABLED} NER_DEVICE={settings.NER_DEVICE}")
print(f"[env] NER_MODEL_PATH={settings.NER_MODEL_PATH}")

TEXTS = {
    "perovskite": (
        "Methylammonium lead iodide (MAPbI3) perovskite solar cells exhibit high "
        "power conversion efficiency. The perovskite film was fabricated by a "
        "one-step spin-coating method using a solvent-engineering approach."
    ),
    "graphene": (
        "Graphene is a two-dimensional carbon material with exceptional electrical "
        "conductivity. We synthesized graphene oxide by the Hummers method and "
        "confirmed its structure by X-ray diffraction characterization."
    ),
}

ner_service._load()
print(f"[ner] backend={ner_service.backend} available={ner_service.available} "
      f"load_error={ner_service._load_error}")

total = 0
by_type: dict = {}
for name, text in TEXTS.items():
    entities = ner_service.extract(text)
    print(f"\n=== [{name}] ===")
    if not entities:
        print("  (0 entities)")
        continue
    for e in entities:
        print(f"  {e['type']:<16} conf={e['confidence']:.3f}  {e['text']}")
        total += 1
        by_type[e["type"]] = by_type.get(e["type"], 0) + 1

print("\n=== 汇总 ===")
print(f"total_entities={total}")
print(f"node_type_distribution={by_type}")
if total == 0:
    print("RESULT: FAIL (0 entities)")
    sys.exit(1)
print("RESULT: PASS (non-zero entities from local SciBERT)")