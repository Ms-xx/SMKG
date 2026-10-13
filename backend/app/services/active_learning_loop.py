# -*- coding: utf-8 -*-
"""
主动学习闭环引擎（创新点 C）：标注 → 训练 → 评估 → 注册 → 再采样 飞轮。

把「采样」从与学习脱节的静态启发式（如直接 1-confidence）升级为「用已标注数据
训练出的代理模型输出概率 → 送入不确定性/多样性/QBC 采样」的闭环：人工每标注一批，
代理分类器随即更新，下一轮采样的不确定性由新模型给出，使数据预算投向模型最不确定
（信息增益最大）的样本。

可插拔可降级：
- 代理分类器为纯 Python 确定性实现（无 numpy/ML 依赖），CPU/离线永远可跑；
- 无已标注数据或未提供特征 → 自动降级为静态不可知采样（均匀/仅用 1-confidence），
  接口不变，不抛出；
- 后续可替换为真实微调模型：把 `predict_soft` 换成 `version_management_service`
  产出的 checkpoint 推理即可，无需改闭环编排。

数据约定（确定性、可单测）：
- labeled = [{text, label, features?, confidence?}]（来自标注回写训练集）
- unlabeled = [{id?, text?, features?, confidence?}]（来自待标注元素池）
"""
from __future__ import annotations

import math
import random
from typing import Any, Iterable

from app.core.config import settings


# ── 工具 ──────────────────────────────────────────────
def _centroid(rows: Iterable[Iterable[float]]) -> list[float]:
    """均值向量，空则返回 []."""
    rows = [list(r) for r in rows]
    if not rows:
        return []
    dim = len(rows[0])
    acc = [0.0] * dim
    for r in rows:
        for i in range(dim):
            acc[i] += r[i] / len(rows)
    return acc


def _euclidean(a: Iterable[float], b: Iterable[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=False)))


def _softmax(scores: list[float], temperature: float = 1.0) -> list[float]:
    """scores 越大概率越高（用于近邻距离的负向软化），零除安全。"""
    if not scores:
        return []
    m = max(scores)
    exps = [math.exp((s - m) / temperature) for s in scores]
    total = sum(exps)
    if total <= 0:
        return [1.0 / len(scores)] * len(scores)
    return [e / total for e in exps]


def _normalize(probs: Iterable[float]) -> list[float]:
    p = [max(0.0, float(x)) for x in probs]
    total = sum(p)
    if total <= 0:
        return p
    return [x / total for x in p]


# ── 确定性代理分类器（最近质心 + 标签平滑先验）─────────────
def train_surrogate(labeled: list[dict[str, Any]]) -> dict[str, Any]:
    """用已标注数据拟合一个可输出软概率的代理分类器。

    策略：每个标签的平滑先验 +（若提供特征）每类特征质心；预测时按「离质心越近
    概率越高」的 softmax 并结合先验。无标注 → available=False；无特征 → 仅先验。
    """
    labeled = [s for s in labeled if s.get("label") is not None]
    if not labeled:
        return {"available": False, "labels": [], "priors": [], "centroids": {}}

    labels = list(dict.fromkeys(s["label"] for s in labeled))
    priors_raw = dict.fromkeys(labels, 1.0)  # Laplace 平滑
    for s in labeled:
        priors_raw[s["label"]] += 1.0
    total = sum(priors_raw.values())
    priors = [priors_raw[lab] / total for lab in labels]

    centroids: dict[str, list[float]] = {}
    for lab in labels:
        feats = [s["features"] for s in labeled if s["label"] == lab and s.get("features")]
        c = _centroid(feats)
        if c:
            centroids[lab] = c

    return {
        "available": True,
        "labels": labels,
        "priors": priors,
        "centroids": centroids,
        "trained_size": len(labeled),
    }


def predict_soft(model: dict[str, Any], features: Any = None) -> list[float]:
    """用代理分类器输出一个样本在标签集上的概率分布。"""
    labels = model.get("labels") or []
    if not labels:
        return []
    k = len(labels)

    if not model.get("available"):
        return [1.0 / k] * k

    centroids = model.get("centroids") or {}
    priors = model.get("priors") or []

    # 有特征且全部质心齐备 → 近邻软化 + 先验的调和
    if features and centroids and all(lab in centroids for lab in labels):
        dist = [_euclidean(features, centroids[lab]) for lab in labels]
        sim = _softmax([-d for d in dist], temperature=settings.ACTIVE_LEARNING_LOOP_TEMPERATURE)
        mixed = [0.5 * sim[i] + 0.5 * priors[i] for i in range(k)]
        return _normalize(mixed)

    # 仅先验（无特征/质心）
    return _normalize(priors)


def _hold_out_split(
    labeled: list[dict[str, Any]], seed: int, test_ratio: float
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """按标签分层留出 train/test 切分，确定性（seed 固定）。"""
    by_label: dict[str, list[int]] = {}
    for i, s in enumerate(labeled):
        by_label.setdefault(s["label"], []).append(i)
    rng = random.Random(seed)
    test_idx: set[int] = set()
    for idxs in by_label.values():
        n_test = max(1, int(round(len(idxs) * test_ratio))) if len(idxs) > 1 else 0
        rng.shuffle(idxs)
        test_idx.update(idxs[:n_test])
    train = [s for i, s in enumerate(labeled) if i not in test_idx]
    test = [s for i, s in enumerate(labeled) if i in test_idx]
    return train, test


def evaluate_loop(
    labeled: list[dict[str, Any]], seed: int = 42, test_ratio: float = 0.2
) -> dict[str, Any]:
    """在留出集上评估代理分类器，返回 accuracy / macro-F1 / 混淆概况。

    样本过少或单一标签 → 降级返回 available=False，不强行给结论。
    """
    labeled = [s for s in labeled if s.get("label") is not None]
    labels = list(dict.fromkeys(s["label"] for s in labeled))
    if len(labeled) < 2 or len(labels) < 1:
        return {"available": False, "reason": "insufficient_data", "sample_count": len(labeled)}

    train, test = _hold_out_split(labeled, seed, test_ratio)
    if not test:
        return {"available": False, "reason": "no_test_set", "sample_count": len(labeled)}

    model = train_surrogate(train)
    preds = []
    for s in test:
        probs = predict_soft(model, s.get("features"))
        pred = (
            model.get("labels")[max(range(len(probs)), key=lambda i: probs[i])] if probs else None
        )
        preds.append((s["label"], pred))

    # accuracy
    correct = sum(1 for t, p in preds if t == p)
    accuracy = correct / len(preds)

    # macro-F1（按全部标签）
    per_label: dict[str, dict[str, int]] = {lab: {"tp": 0, "fp": 0, "fn": 0} for lab in labels}
    for t, p in preds:
        if p is None:
            per_label[t]["fn"] += 1
        elif p == t:
            per_label[t]["tp"] += 1
        else:
            per_label[p]["fp"] += 1
            per_label[t]["fn"] += 1
    f1s = []
    for lab in labels:
        tp, fp, fn = per_label[lab]["tp"], per_label[lab]["fp"], per_label[lab]["fn"]
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if (prec + rec) else 0.0)
    macro_f1 = sum(f1s) / len(f1s) if f1s else 0.0

    return {
        "available": True,
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "label_count": len(labels),
        "train_size": len(train),
        "test_size": len(test),
        "classes": labels,
    }


# ── 闭环编排 ──────────────────────────────────────────
class ActiveLearningLoopService:
    """主动学习闭环编排：标注 → 训练 → 评估 → 采样（输出下一批待标注样本）。"""

    @property
    def available(self) -> bool:
        return settings.ACTIVE_LEARNING_LOOP_ENABLED

    def run_cycle(
        self,
        labeled: list[dict[str, Any]],
        unlabeled: list[dict[str, Any]],
        strategy: str | None = None,
        top_k: int = 10,
        seed: int | None = None,
    ) -> dict[str, Any]:
        """执行一轮闭环，返回 {cycle_id, trained, metrics, sampled, note...}.

        labeled: [{text, label, features}]（标注回写训练集）
        unlabeled: [{id?, text?, features?, confidence?}]（待标注样本池）
        """
        if not self.available:
            return {"enabled": False, "reason": "disabled"}

        labeled = [dict(s) for s in labeled if s.get("label") is not None]
        unlabeled = [dict(s) for s in unlabeled]
        seed = seed if seed is not None else settings.ACTIVE_LEARNING_SEED

        # 1) 训练代理分类器（用全部已标注）
        model = train_surrogate(labeled)
        # 闭环仅在「确能产出特征驱动的软概率」时成立：有标注且每个标签都有特征质心。
        # 仅先验/无特征时视作不可用，走 1-confidence 静态降级（与文档「未提供特征→降级」一致）。
        _labels = model.get("labels") or []
        _centroids = model.get("centroids") or {}
        feature_model = bool(_centroids) and all(lab in _centroids for lab in _labels)
        trained = model.get("available", False) and feature_model

        # 2) 评估（留出集，可用性独立于训练）
        metrics = evaluate_loop(labeled, seed=seed)

        # 3) 用代理模型给出未标注样本的软概率 → 不确定性/混合采样
        candidate_unc = []
        for s in unlabeled:
            feats = s.get("features")
            probs = predict_soft(model, feats) if trained else []
            # 无可用模型时降级：置信度反转为不确定性（若提供了 confidence）
            if not probs:
                conf = s.get("confidence")
                if conf is not None:
                    probs = [float(conf), 1.0 - float(conf)]
            entry = dict(s)
            if probs:
                entry["probs"] = probs
            candidate_unc.append(entry)

        # 4) 送入既有采样门面（不确定性/多样性/QBC/混合，可插拔可降级）
        from app.services.active_learning_service import active_learning_service

        sampled = active_learning_service.select(
            samples=candidate_unc,
            strategy=strategy,
            top_k=top_k,
        )

        cycle_id = f"al-{math.floor(seed)}-{top_k}"  # 确定性可复现
        note = "closed_loop" if trained else "degraded_no_trained_model"
        return {
            "enabled": True,
            "cycle_id": cycle_id,
            "trained": trained,
            "train_size": model.get("trained_size", 0),
            "labels": model.get("labels", []),
            "metrics": metrics,
            "strategy": sampled.get("strategy"),
            "sampling_backend": sampled.get("backend"),
            "note": note,
            "sampled": sampled,
            "unlabeled_count": len(unlabeled),
        }


# 全局单例
active_learning_loop_service = ActiveLearningLoopService()
