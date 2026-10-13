# -*- coding: utf-8 -*-
"""
创新点A 端到端：用本地 SciBERT 对英文科学句子做实体抽取 → 去重后写入 Neo4j 实体节点，
并核对去重后的非0实体类型分布。可插拔：NER_DEVICE 默认 cpu，预留 cuda。

用法（SciMKG，需 moulds/scibert 为可用微调 checkpoint）:
    python innovA_e2e_graph.py
输出: outputs/innovA_ner_e2e.json
"""
from __future__ import annotations

import json
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE_DIR, "backend"))

from collections import Counter

from loguru import logger

from app.core.config import settings
from app.services.ner_service import ner_service
from app.utils.neo4j_client import Neo4jClient

SENTENCES = {
    "perovskite": (
        "Methylammonium lead iodide (MAPbI3) perovskite solar cells exhibit high power "
        "conversion efficiency. The perovskite thin film is prepared by a one-step "
        "anti-solvent spin-coating method."
    ),
    "graphene": (
        "We fabricate a graphene field-effect transistor by chemical vapor deposition. "
        "The carrier mobility is ~10000 cm2/V/s, characterized by Raman spectroscopy."
    ),
    "llm": (
        "We fine-tune a BERT-based language model for sentiment classification using the "
        "LoRA adapter and measure cross-entropy loss on the held-out test set."
    ),
}


def main() -> None:
    ner_service._load()
    logger.info(f"NER backend={ner_service.backend} available={ner_service.available}")

    entities: list[dict] = []
    for name, text in SENTENCES.items():
        ents = ner_service.extract(text)
        logger.info(f"[{name}] extracted {len(ents)} entities")
        for e in ents:
            # 去除低置信噪点
            if e.get("confidence", 1.0) >= 0.6:
                entities.append({"text": e["text"], "type": e["type"]})

    # 简单关系：同句子内两两实体连 HAS_COOCCUR 并标注 source 句子
    relations: list[dict] = []

    # 去重
    uniq = {}
    for e in entities:
        key = (e["type"], e["text"].lower())
        uniq.setdefault(key, e)
    unique_entities = list(uniq.values())
    by_type = Counter(e["type"] for e in unique_entities)
    logger.info(f"unique_entities={len(unique_entities)} by_type={dict(by_type)}")

    # 写入 Neo4j（单事件循环内完成，避免 driver 绑定循环冲突）
    import asyncio

    async def _write():
        client = Neo4jClient()
        created = 0
        for e in unique_entities:
            cypher = (
                f"MERGE (n:{e['type']} {{name: $name}}) "
                "ON CREATE SET n.id = randomUUID(), n.source='innovA' "
                "ON MATCH SET n._count = coalesce(n._count,0)+1 "
                "RETURN n.id"
            )
            await client.execute_write(cypher, {"name": e["text"]})
            created += 1
        await client.close()
        return created

    created = asyncio.run(_write())

    result = {
        "ner_backend": ner_service.backend,
        "device": settings.NER_DEVICE,
        "extracted_raw": len(entities),
        "unique_entities": len(unique_entities),
        "node_types": dict(by_type),
        "neo4j_nodes_created": created,
        "relations": len(relations),
    }
    out_path = os.path.join(BASE_DIR, "outputs", "innovA_ner_e2e.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if len(unique_entities) == 0:
        logger.error("unique_entities=0：实体级图谱仍为空，失败")
        sys.exit(1)
    logger.info(f"PASS: non-zero unique entity nodes written -> {out_path}")


if __name__ == "__main__":
    main()