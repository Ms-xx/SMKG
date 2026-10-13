# -*- coding: utf-8 -*-
"""
创新点 C 校验：主动学习闭环（标注 → 训练代理分类器 → 评估 → 用模型概率再采样）。

覆盖：
- 纯函数：train_surrogate（available/不可用）、predict_soft（软概率）、evaluate_loop（acc/macro-F1）
- 闭环：提供已标注数据 + 特征 → trained=True、metrics 非空、采样结果按模型不确定性排序
- 降级：无已标注 → note=degraded_no_trained_model，仍按 1-confidence 采样不阻断
- 闭环飞轮：加入新标注后模型更新 → 再采样选择的不确定样本变化（体现数据预算投向难样本）

用法（SciMKG）:
    python innovC_active_learning_loop.py
输出: outputs/innovC_active_learning_loop.json
"""
from __future__ import annotations

import json
import math
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE_DIR, "backend"))

from app.core.config import settings  # noqa: E402
from app.services.active_learning_loop import (  # noqa: E402
    evaluate_loop,
    predict_soft,
    train_surrogate,
    active_learning_loop_service,
)


def _labeled_a(n: int = 6) -> list[dict]:
    # A 类聚集在原点附近
    return [{"text": f"A{i}", "label": "A", "features": [i * 0.1, i * 0.1]} for i in range(n)]


def _labeled_b(n: int = 6) -> list[dict]:
    # B 类聚集在 (10,10) 附近
    return [{"text": f"B{i}", "label": "B", "features": [10.0 + i * 0.1, 10.0 - i * 0.1]} for i in range(n)]


def test_pure() -> dict:
    # 空训练 → 不可用、均匀概率
    m0 = train_surrogate([])
    assert m0["available"] is False
    assert predict_soft(m0, [0.0, 0.0]) == []

    m = train_surrogate(_labeled_a() + _labeled_b())
    assert m["available"] is True
    assert set(m["labels"]) == {"A", "B"}
    # 分类面附近的点概率应接近 0.5/0.5（高熵）
    boundary = predict_soft(m, [5.0, 5.0])
    assert len(boundary) == 2
    assert all(0.2 < p < 0.8 for p in boundary), boundary
    # 原点远处应偏向 A
    near_a = predict_soft(m, [0.0, 0.0])
    assert near_a[0] > near_a[1], near_a

    ev = evaluate_loop(_labeled_a() + _labeled_b())
    assert ev["available"] is True
    assert 0.0 <= ev["accuracy"] <= 1.0
    assert 0.0 <= ev["macro_f1"] <= 1.0
    assert ev["label_count"] == 2
    return {
        "boundary_probs": boundary,
        "near_a_probs": near_a,
        "evaluate": ev,
    }


def test_loop_degraded() -> dict:
    # 无已标注：降级静态 1-confidence 采样，不阻断
    unlabeled = [
        {"id": "u1", "text": "低置信", "confidence": 0.3},
        {"id": "u2", "text": "高置信", "confidence": 0.9},
    ]
    r = active_learning_loop_service.run_cycle(
        labeled=[], unlabeled=unlabeled, strategy="uncertainty", top_k=2
    )
    assert r["enabled"] is True
    assert r["trained"] is False
    assert r["note"] == "degraded_no_trained_model"
    # 低置信样本应排第一
    ids = [x.get("id") for x in r["sampled"]["results"]]
    assert ids[0] == "u1", ids
    return {"note": r["note"], "sampled_ids": ids}


def test_loop_closed() -> dict:
    # 已标注 + 特征：训练代理分类器，边界样本不确定性最高应被优先采样
    labeled = _labeled_a(5) + _labeled_b(5)
    unlabeled = [
        {"id": "boundary", "text": "边界样本", "features": [5.0, 5.0]},
        {"id": "clear_a", "text": "明确A", "features": [0.0, 0.0]},
        {"id": "clear_b", "text": "明确B", "features": [10.0, 10.0]},
    ]
    r = active_learning_loop_service.run_cycle(
        labeled=labeled, unlabeled=unlabeled, strategy="uncertainty", top_k=3
    )
    assert r["enabled"] is True
    assert r["trained"] is True
    assert r["metrics"]["available"] is True
    assert r["note"] == "closed_loop"
    ids = [x.get("id") for x in r["sampled"]["results"]]
    assert ids[0] == "boundary", ids  # 模型概率下边界最不确定，优先标注
    return {
        "cycle_id": r["cycle_id"],
        "metrics": r["metrics"],
        "labels": r["labels"],
        "sampled_ids": ids,
        "sampled_probs": r["sampled"]["results"][0].get("score"),
    }


def test_loop_flywheel() -> dict:
    # 飞轮：把"边界难样本"标注后加入训练 → 该样本在下轮模型下的不确定性下降
    # （模型学会该区域 → 再采样的预算从已学习区域转移走），体现"标注回流→再采样"闭环。
    m1 = train_surrogate(_labeled_a(5) + _labeled_b(5))
    boundary_probs_before = predict_soft(m1, [5.0, 5.0])
    e_before = sum(-p * math.log2(p) for p in boundary_probs_before if p > 0)

    # 人工把边界样本标为 B → 加入训练集，重训
    m2 = train_surrogate(
        _labeled_a(5) + _labeled_b(5) + [{"text": "x", "label": "B", "features": [5.0, 5.0]}]
    )
    boundary_probs_after = predict_soft(m2, [5.0, 5.0])
    e_after = sum(-p * math.log2(p) for p in boundary_probs_after if p > 0)

    assert e_after < e_before, (e_before, e_after)
    return {
        "boundary_entropy_before": round(e_before, 4),
        "boundary_entropy_after": round(e_after, 4),
        "probs_before": boundary_probs_before,
        "probs_after": boundary_probs_after,
        "note": "标注回流降低了该样本的模型自评不确定性，再采样会投向未被覆盖的难样本",
    }


def main() -> None:
    results = {
        "innovC": "active_learning_loop",
        "enabled": settings.ACTIVE_LEARNING_LOOP_ENABLED,
        "temperature": settings.ACTIVE_LEARNING_LOOP_TEMPERATURE,
        "pure": test_pure(),
        "loop_degraded": test_loop_degraded(),
        "loop_closed": test_loop_closed(),
        "flywheel": test_loop_flywheel(),
    }
    out = os.path.join(BASE_DIR, "outputs", "innovC_active_learning_loop.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()