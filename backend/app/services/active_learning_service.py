# -*- coding: utf-8 -*-
"""
主动学习采样服务（Active Learning Sampling）

在「标注 → 训练 → 采样」闭环中，从待标注样本池里挑选最值得优先标注的样本，
覆盖三类策略：
1. 不确定性采样：熵（Entropy）/ 最小置信度（Least Confidence）/ 边缘（Margin）；
2. 多样性采样：核心集选择（Core-Set，贪心最远点）/ K-Means++ 聚类代表点；
3. 基于委员会的查询（QBC）：投票熵（Vote Entropy）/ 分歧度（Disagreement）。

依赖策略（可插拔、可降级）：
- 全部策略为纯 Python 实现、零依赖、确定性，永远可用；
- K-Means++ 与 Core-Set 均不依赖 numpy；
- 混合策略（hybrid）在可用信号维度上加权融合，某维度缺失自动跳过，接口不变。
"""
from __future__ import annotations

import math
import random
from typing import Any, Iterable

from app.core.config import settings

# ── 通用工具 ──────────────────────────────────────────────

UNCERTAINTY_METHODS = ("entropy", "least_confidence", "margin")
DIVERSITY_METHODS = ("core_set", "kmeans")
QBC_METHODS = ("vote_entropy", "disagreement")


def _normalize(probs: Iterable[float]) -> list[float]:
    """将任意非负权重归一化为概率分布（和为 1）。"""
    p = [max(0.0, float(x)) for x in probs]
    total = sum(p)
    if total <= 0:
        return p
    return [x / total for x in p]


def _argmax(probs: Iterable[float]) -> int:
    p = list(probs)
    return max(range(len(p)), key=lambda i: p[i])


def _euclidean(a: Iterable[float], b: Iterable[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=False)))


def _minmax_norm(values: list[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi - lo < 1e-12:
        return [0.5 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


# ── 1. 不确定性采样 ───────────────────────────────────────


def entropy(probs: Iterable[float]) -> float:
    """预测分布的熵（越高越不确定）。"""
    p = _normalize(probs)
    return float(-sum(x * math.log2(x) for x in p if x > 0))


def least_confidence(probs: Iterable[float]) -> float:
    """最小置信度：1 - 最大概率（越高越不确定）。"""
    p = _normalize(probs)
    return float(1.0 - max(p)) if p else 0.0


def margin(probs: Iterable[float]) -> float:
    """边缘采样：1 - (最高两类的概率差)（差距越小越不确定）。"""
    p = sorted(_normalize(probs), reverse=True)
    if not p:
        return 0.0
    if len(p) < 2:
        return float(1.0 - p[0])
    return float(1.0 - (p[0] - p[1]))


_UNCERTAINTY_FN = {
    "entropy": entropy,
    "least_confidence": least_confidence,
    "margin": margin,
}


def uncertainty_score(probs: Iterable[float], method: str = "entropy") -> float:
    """不确定性得分：越高越应优先标注。"""
    if not probs:
        return 0.0
    fn = _UNCERTAINTY_FN.get(method, entropy)
    return float(fn(probs))


# ── 2. QBC（基于委员会的查询）─────────────────────────────


def vote_entropy(predictions: list[Iterable[float]]) -> float:
    """投票熵：对各委员会成员预测分布求平均后的熵（越高分歧越大）。"""
    preds = [list(_normalize(p)) for p in predictions if p]
    if not preds:
        return 0.0
    n = len(preds[0])
    avg = [0.0] * n
    for p in preds:
        for i in range(n):
            avg[i] += p[i] / len(preds)
    return entropy(avg)


def disagreement(predictions: list[Iterable[float]]) -> float:
    """分歧度：委员会成员两两预测标签不一致的占比（越高分歧越大）。"""
    labels = [_argmax(p) for p in predictions if p]
    n = len(labels)
    if n < 2:
        return 0.0
    pairs = n * (n - 1) / 2
    diff = sum(1 for i in range(n) for j in range(i + 1, n) if labels[i] != labels[j])
    return float(diff / pairs)


_QBC_FN = {
    "vote_entropy": vote_entropy,
    "disagreement": disagreement,
}


def qbc_score(predictions: list[Iterable[float]], method: str = "vote_entropy") -> float:
    """委员会分歧得分：越高越应优先标注。"""
    if not predictions:
        return 0.0
    fn = _QBC_FN.get(method, vote_entropy)
    return float(fn(predictions))


# ── 3. 多样性采样 ─────────────────────────────────────────


def core_set_indices(features: list[Iterable[float]], k: int) -> list[int]:
    """
    核心集选择（Core-Set）：贪心最远点遍历（minimax，最小化覆盖半径）。

    从第一个点开始，反复选取到「已选集合」最近距离最大的点，返回代表性样本下标。
    """
    n = len(features)
    if n == 0 or k <= 0:
        return []
    k = min(int(k), n)
    selected = [0]
    min_d2 = [_euclidean(features[i], features[0]) ** 2 for i in range(n)]
    while len(selected) < k:
        far = -1
        best = -1.0
        for j in range(n):
            if j in selected:
                continue
            if min_d2[j] > best:
                best = min_d2[j]
                far = j
        if far < 0:
            break
        selected.append(far)
        for j in range(n):
            if j in selected:
                continue
            d2 = _euclidean(features[j], features[far]) ** 2
            if d2 < min_d2[j]:
                min_d2[j] = d2
    return selected


def kmeans_pp_indices(features: list[Iterable[float]], k: int, seed: int = 42) -> list[int]:
    """
    K-Means++ 初始化：按距离平方加权概率反复选取聚类中心，返回代表性样本下标。

    与 K-Means 的初始化一致，用于挑选「分布上分散」的代表样本（纯 Python）。
    """
    n = len(features)
    if n == 0 or k <= 0:
        return []
    k = min(int(k), n)
    rng = random.Random(seed)
    selected = [0]
    min_d2 = [_euclidean(features[i], features[0]) ** 2 for i in range(n)]
    while len(selected) < k:
        total = sum(min_d2[j] for j in range(n) if j not in selected)
        if total <= 1e-12:
            for j in range(n):
                if j not in selected:
                    selected.append(j)
                    break
            continue
        r = rng.random() * total
        cum = 0.0
        chosen = -1
        for j in range(n):
            if j in selected:
                continue
            cum += min_d2[j]
            if cum >= r:
                chosen = j
                break
        if chosen < 0:
            chosen = next(j for j in range(n) if j not in selected)
        selected.append(chosen)
        for j in range(n):
            if j in selected:
                continue
            d2 = _euclidean(features[j], features[chosen]) ** 2
            if d2 < min_d2[j]:
                min_d2[j] = d2
    return selected


def diversity_select(
    features: list[Iterable[float]], k: int, method: str = "core_set", seed: int = 42
) -> list[int]:
    """多样性采样：返回 top-k 个代表性样本下标（在分布式分散）。"""
    if method == "kmeans":
        return list(kmeans_pp_indices(features, int(k), seed))
    return list(core_set_indices(features, int(k)))


# ── 门面服务 ─────────────────────────────────────────────


class ActiveLearningService:
    """主动学习采样服务：不确定性 / 多样性 / QBC / 混合，可插拔可降级。"""

    @property
    def available(self) -> bool:
        return settings.ACTIVE_LEARNING_ENABLED

    @staticmethod
    def _norm_sample(sample: Any) -> dict[str, Any]:
        if hasattr(sample, "model_dump"):
            return sample.model_dump()
        return dict(sample)

    def select(
        self,
        samples: list[Any],
        strategy: str | None = None,
        top_k: int = 10,
        uncertainty_method: str | None = None,
        diversity_method: str | None = None,
        qbc_method: str | None = None,
    ) -> dict[str, Any]:
        """
        从样本池中挑选优先标注样本。

        样本字段：
        - probs: 概率分布（用于不确定性）
        - predictions: 委员会各成员的概率分布列表（用于 QBC）
        - features: 特征向量（用于多样性；缺失时多样性 / 混合自动跳过）
        - id / text: 可选元信息，原样透传。

        Returns:
            {"strategy", "backend", "top_k", "results": [{index, id, text, score, ...}], "total"}
        """
        items = [self._norm_sample(s) for s in samples]
        strategy = strategy or settings.ACTIVE_LEARNING_STRATEGY
        um = uncertainty_method or settings.ACTIVE_LEARNING_UNCERTAINTY
        dm = diversity_method or settings.ACTIVE_LEARNING_DIVERSITY
        qm = qbc_method or settings.ACTIVE_LEARNING_QBC

        # 可用的信号维度
        has_unc = any(("probs" in s) and s["probs"] for s in items)
        has_qbc = any(("predictions" in s) and s["predictions"] for s in items)
        has_div = any(("features" in s) and s["features"] for s in items)

        def _unc(i: dict) -> float:
            return uncertainty_score(i.get("probs") or [], um)

        def _qbc(i: dict) -> float:
            return qbc_score(i.get("predictions") or [], qm)

        results: list[dict[str, Any]] = []

        # 1) 纯多样性：直接选取代表性下标
        if strategy == "diversity" and has_div:
            feats = [s["features"] for s in items]
            for rank, idx in enumerate(
                diversity_select(feats, top_k, dm, settings.ACTIVE_LEARNING_SEED)
            ):
                entry = {"index": idx, "rank": rank + 1, "method": dm}
                entry.update(self._meta(items[idx]))
                results.append(entry)
            return self._wrap(strategy, "builtin", top_k, results, len(items))

        # 2) 计算每个样本的基础得分（不确定性 / QBC / 混合）
        base: list[float] = []
        for s in items:
            if strategy == "uncertainty":
                base.append(_unc(s))
            elif strategy == "qbc":
                base.append(_qbc(s))
            else:  # hybrid（含不可用的降级）
                parts = []
                if has_unc:
                    parts.append(_unc(s))
                if has_qbc:
                    parts.append(_qbc(s))
                base.append(_mean(parts) if parts else 1.0)

        norm_base = _minmax_norm(base)

        # 3) 混合策略 + 有特征向量：贪心多样 top-k（MMR 风格，兼顾不确定性与分散度）
        if strategy == "hybrid" and has_div and (has_unc or has_qbc):
            feats = [s["features"] for s in items]
            max_dist = (
                max(
                    (
                        _euclidean(feats[i], feats[j])
                        for i in range(len(feats))
                        for j in range(i + 1, len(feats))
                    ),
                    default=1.0,
                )
                or 1.0
            )
            order = sorted(range(len(items)), key=lambda j: -norm_base[j])
            picked: list[int] = []
            while len(picked) < min(top_k, len(order)):
                best_j, best_val = -1, -1.0
                for j in order:
                    if j in picked:
                        continue
                    div = (
                        (min((_euclidean(feats[j], feats[p]) for p in picked), default=0.0))
                        / max_dist
                        if picked
                        else 0.0
                    )
                    val = 0.5 * norm_base[j] + 0.5 * div
                    if val > best_val:
                        best_val, best_j = val, j
                if best_j < 0:
                    break
                picked.append(best_j)
            for idx in picked:
                entry = {
                    "index": idx,
                    "score": round(norm_base[idx], 4),
                    "method": "hybrid",
                    "diverse": True,
                }
                entry.update(self._meta(items[idx]))
                results.append(entry)
            return self._wrap(strategy, "builtin", top_k, results, len(items))

        # 4) 规则 / 不确定性 / QBC：按得分降序取 top_k
        order = sorted(range(len(items)), key=lambda j: -norm_base[j])
        for idx in order[:top_k]:
            entry = {"index": idx, "score": round(norm_base[idx], 4)}
            s = items[idx]
            if strategy == "hybrid":
                entry["method"] = (
                    " + ".join(
                        m for m, flag in (("uncertainty", has_unc), ("qbc", has_qbc)) if flag
                    )
                    or "none"
                )
            elif strategy == "uncertainty":
                entry["method"] = um
            else:
                entry["method"] = qm
            entry.update(self._meta(s))
            results.append(entry)

        return self._wrap(strategy, "builtin", top_k, results, len(items))

    @staticmethod
    def _meta(s: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if s.get("id") is not None:
            out["id"] = s["id"]
        if s.get("text") is not None:
            out["text"] = s["text"]
        return out

    @staticmethod
    def _wrap(
        strategy: str, backend: str, top_k: int, results: list[dict[str, Any]], total: int
    ) -> dict[str, Any]:
        return {
            "strategy": strategy,
            "backend": backend,
            "top_k": top_k,
            "total": total,
            "selected": len(results),
            "results": results,
        }


# 全局单例（懒加载，构造时不做计算）
active_learning_service = ActiveLearningService()
