#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RotatE / TransE / GNN / 统计 四类打分器在真实图谱上的对比评测（步骤 17.4）。

用法：
    python test/rotate_inference_eval.py [--relation CITES] [--holdout 0.3] [--seed 42] [--out PATH]

评测协议：
    - 三元组取自 Neo4j 真实图谱（默认 CITES 关系，由步骤 16 回填产生）；
    - 按 seed 固定划分 train / test（默认 30% 留出）；
    - 对每个测试三元组做「过滤式尾实体排序」（filtered tail ranking）：
      排除训练集中同一 (head, relation) 下的其它正例，避免把已知正例算作假阴性；
    - 指标：MRR、Hit@1、Hit@3、Hit@5、Hit@10，并给出随机基线期望作为参照。

输出：outputs/rotate_inference_eval.json
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "GraphRAGTest"))
sys.path.insert(0, str(_REPO_ROOT / "backend"))


def load_triples(relation: str, limit: int = 5000) -> list[tuple[str, str, str]]:
    """从 Neo4j 拉取真实三元组 [(head_id, relation, tail_id)]。"""
    import asyncio

    from config import settings as gr_settings
    from neo4j_client import neo4j_client

    async def run() -> list[tuple[str, str, str]]:
        driver = await neo4j_client.get_driver()
        query = (
            "MATCH (a:Document)-[r]->(b) "
            "WHERE (a.id IS NOT NULL AND b.id IS NOT NULL) AND type(r) = $rel "
            "RETURN a.id AS h, type(r) AS rel, b.id AS t LIMIT $limit"
        )
        async with driver.session(database=gr_settings.NEO4J_DATABASE) as session:
            res = await session.run(query, rel=relation, limit=limit)
            return [(rec["h"], rec["rel"], rec["t"]) async for rec in res]

    return asyncio.run(run())


def split_facts(
    facts: list[tuple[str, str, str]], holdout: float, seed: int
) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    """固定随机种子的 train/test 划分；测试集三元组涉及的实体必须在训练集中出现过。"""
    shuffled = list(facts)
    random.Random(seed).shuffle(shuffled)
    n_test = max(1, int(round(len(shuffled) * holdout)))
    test_raw = shuffled[:n_test]
    train_raw = shuffled[n_test:]
    train_entities = {h for h, _, t in train_raw} | {t for h, _, t in train_raw}
    train: list[tuple[str, str, str]] = []
    test: list[tuple[str, str, str]] = []
    for triple in train_raw:
        train.append(triple)
    for triple in test_raw:
        h, r, t = triple
        if h in train_entities and t in train_entities:
            test.append(triple)
        else:
            train.append(triple)
    return train, test


def _eval_transductive(
    predictor: Any, facts: list[tuple[str, str, str]]
) -> dict[str, Any]:
    """Transductive 尾实体排序：在完整真实图上训练后，对每个真实尾实体做全实体排序。

    说明：本口径只用于横向对比各打分器的「排序一致性」，**不代表归纳泛化能力**。
    星状/小规模图谱（如单一施引文献）无法做实体留出，必须以本口径如实呈现。
    """
    entities = sorted({h for h, _, t in facts} | {t for h, _, t in facts})
    hits = {1: 0, 3: 0, 5: 0, 10: 0}
    reciprocal_sum = 0.0
    for h, r, t in facts:
        scored = [(cand, predictor.score_triple(h, r, cand)) for cand in entities]
        scored.sort(key=lambda x: x[1], reverse=True)
        rank = next((i + 1 for i, (cand, _s) in enumerate(scored) if cand == t), None)
        if rank is None:
            continue
        reciprocal_sum += 1.0 / rank
        for k in hits:
            if rank <= k:
                hits[k] += 1
    n = len(facts)
    return {
        "evaluated": n,
        "mrr": round(reciprocal_sum / n, 4),
        "hit@1": round(hits[1] / n, 4),
        "hit@3": round(hits[3] / n, 4),
        "hit@5": round(hits[5] / n, 4),
        "hit@10": round(hits[10] / n, 4),
    }


def _rank_and_metrics(
    predictor: Any, train: list[tuple[str, str, str]], test: list[tuple[str, str, str]]
) -> dict[str, Any]:
    """留出法（inductive）下的过滤式尾实体排序，返回 MRR 与 Hit@k。"""
    entities = sorted({h for h, _, t in train} | {t for h, _, t in train})
    known_tails: dict[tuple[str, str], set[str]] = {}
    for h, r, t in train:
        known_tails.setdefault((h, r), set()).add(t)

    hits = {1: 0, 3: 0, 5: 0, 10: 0}
    reciprocal_sum = 0.0
    evaluated = 0
    for h, r, t in test:
        excluded = known_tails.get((h, r), set()) - {t}
        scored: list[tuple[str, float]] = []
        for cand in entities:
            if cand in excluded:
                continue
            scored.append((cand, predictor.score_triple(h, r, cand)))
        scored.sort(key=lambda x: x[1], reverse=True)
        ranks = [i + 1 for i, (cand, _s) in enumerate(scored) if cand == t]
        if not ranks:
            continue
        evaluated += 1
        rank = ranks[0]
        reciprocal_sum += 1.0 / rank
        for k in hits:
            if rank <= k:
                hits[k] += 1

    if not evaluated:
        return {"evaluated": 0}
    return {
        "evaluated": evaluated,
        "mrr": round(reciprocal_sum / evaluated, 4),
        "hit@1": round(hits[1] / evaluated, 4),
        "hit@3": round(hits[3] / evaluated, 4),
        "hit@5": round(hits[5] / evaluated, 4),
        "hit@10": round(hits[10] / evaluated, 4),
    }


def main(args: argparse.Namespace) -> int:
    from app.services.relation_inference_service import (
        GNNLinkPredictor,
        RotatELinkPredictor,
        StatisticalLinkPredictor,
        TransELinkPredictor,
    )

    facts = load_triples(args.relation, limit=args.limit)
    print(f"[rotate_eval] triples(relation={args.relation}) = {len(facts)}")
    if len(facts) < 6:
        print("[rotate_eval] 三元组过少，评测无统计意义，已退出")
        return 1

    train, test = split_facts(facts, args.holdout, args.seed)
    entities = sorted({h for h, _, t in train} | {t for h, _, t in train})
    # 星状拓扑（每个尾实体仅出现一次）会导致留出测试集为空，此时降级为 transductive 口径
    protocol = "holdout_filtered_tail_ranking"
    if not test:
        print(
            "[rotate_eval] 留出测试集为空（图谱为星状，尾实体在训练集中不重复出现），"
            "降级为 transductive 排序一致性口径"
        )
        protocol = "transductive_tail_ranking"
        train, test = facts, facts
        entities = sorted({h for h, _, t in facts} | {t for h, _, t in facts})
    print(
        f"[rotate_eval] protocol={protocol} train={len(train)} test={len(test)} entities={len(entities)}"
    )

    predictors: dict[str, Any] = {
        "rotate": RotatELinkPredictor(),
        "transe": TransELinkPredictor(),
        "gnn": GNNLinkPredictor(),
        "statistical": StatisticalLinkPredictor(),
    }
    results: dict[str, Any] = {}
    for name, predictor in predictors.items():
        try:
            predictor.fit(train)
            trained = bool(getattr(predictor, "trained", True))
            if not trained:
                metrics: dict[str, Any] = {"evaluated": 0}
            elif protocol.startswith("transductive"):
                metrics = _eval_transductive(predictor, facts)
            else:
                metrics = _rank_and_metrics(predictor, train, test)
        except Exception as e:  # noqa: BLE001
            trained, metrics = False, {"error": str(e)}
        results[name] = {"trained": trained, **metrics}
        print(f"[rotate_eval] {name:12} {metrics}")

    # 随机基线期望：hit@k ≈ k / 候选实体数
    results["random_baseline"] = {
        "hit@1": round(1 / len(entities), 4),
        "hit@3": round(min(3 / len(entities), 1.0), 4),
        "hit@5": round(min(5 / len(entities), 1.0), 4),
        "hit@10": round(min(10 / len(entities), 1.0), 4),
        "mrr_expected_lower_bound": round(1 / len(entities), 4),
    }

    summary = {
        "script": "rotate_inference_eval",
        "relation": args.relation,
        "seed": args.seed,
        "holdout": args.holdout,
        "triples_total": len(facts),
        "train_size": len(train),
        "test_size": len(test),
        "entity_count": len(entities),
        "protocol": protocol,
        "protocol_note": (
            "filtered tail ranking (留出法，可评估泛化)"
            if protocol == "holdout_filtered_tail_ranking"
            else "transductive ranking consistency — 与真实 iput 图谱拓扑有关，不代表归纳泛化"
        ),
        "results": results,
        "timestamp": datetime.now().isoformat(),
    }
    out_path = (
        Path(args.out)
        if args.out
        else _REPO_ROOT / "outputs" / "rotate_inference_eval.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[rotate_eval] report -> {out_path}")
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="RotatE 等打分器在真实图谱上的对比评测")
    p.add_argument("--relation", type=str, default="CITES")
    p.add_argument("--holdout", type=float, default=0.3)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--limit", type=int, default=5000)
    p.add_argument("--out", type=str, default=None)
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(main(parse_args()))
