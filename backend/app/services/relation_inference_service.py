# -*- coding: utf-8 -*-
"""
关系推理与图谱补全服务（Relation Inference & Graph Completion）

基于知识图谱三元组 (head, relation, tail) 完成两类任务：
1. 关系推理：通过可解释的领域规则（组合、逆关系、传递）从既有事实推导新关系；
2. 图谱补全 / 链路预测：给定头实体与关系，预测最可能的尾实体（TransE 嵌入打分），
   并支持对候选三元组打分用于补全缺失边。

依赖策略（可插拔、可降级）：
- 规则推理为纯函数、零依赖、永远可用；
- 链路预测后端可选：gnn（轻量 GNN，numpy 邻域聚合 + TransE 打分）→
  transe（numpy 浅层嵌入 + 负采样 SGD）→ statistical（统计共现 + 邻居 Jaccard）；
- numpy 缺失 / 三元组过少时逐级降级到 statistical 纯 Python 基线，接口不变；
- 后端设为 "none" 时仅保留规则推理。
"""
from __future__ import annotations

import math
from typing import Any

try:
    import numpy as np

    _NUMPY_AVAILABLE = True
except Exception:  # pragma: no cover - numpy 不可用时降级
    _NUMPY_AVAILABLE = False

from loguru import logger

from app.core.config import settings

# ── 领域推理规则（材料科学，可扩展）────────────────────────────────────
# 组合规则：(s)-[left]->(m)、(m)-[right]->(o) ==> (s)-[result]->(o)
_COMPOSITION_RULES: list[dict[str, str]] = [
    {"left": "PRODUCES", "right": "ACHIEVES", "result": "ENABLES"},
    {"left": "PRODUCES", "right": "EXHIBITS", "result": "ENABLES"},
    {"left": "TRANSPORTS_HOLE", "right": "ACHIEVES", "result": "CONTRIBUTES_TO"},
    {"left": "TRANSPORTS_ELECTRON", "right": "ACHIEVES", "result": "CONTRIBUTES_TO"},
    {"left": "TRANSPORTS_HOLE", "right": "EXHIBITS", "result": "PARTICIPATES_IN"},
    {"left": "TRANSPORTS_ELECTRON", "right": "EXHIBITS", "result": "PARTICIPATES_IN"},
]

# 逆关系规则：r 的逆关系名
_INVERSE_RELATIONS: dict[str, str] = {
    "PRODUCES": "PRODUCED_BY",
    "TRANSPORTS_HOLE": "HAS_HOLE_TRANSPORTER",
    "TRANSPORTS_ELECTRON": "HAS_ELECTRON_TRANSPORTER",
}

# 传递关系集合
_TRANSITIVE_RELATIONS: set[str] = {"REQUIRES"}


def _norm_triples(triples: list[Any]) -> list[tuple[str, str, str]]:
    """将多种三元组输入形式归一化为 (head, relation, tail) 元组列表。"""
    normalized: list[tuple[str, str, str]] = []
    for item in triples:
        if isinstance(item, dict):
            h = item.get("head") or item.get("source") or item.get("h")
            r = item.get("relation") or item.get("rel") or item.get("rel_type") or item.get("type")
            t = item.get("tail") or item.get("target") or item.get("t") or item.get("object")
        else:
            h, r, t = item[0], item[1], item[2]
        if h is None or r is None or t is None:
            continue
        normalized.append((str(h), str(r), str(t)))
    return normalized


def _add_inferred(
    seen: set[tuple[str, str, str]],
    inferred: list[dict[str, Any]],
    h: str,
    r: str,
    t: str,
    reason: str,
    confidence: float,
) -> None:
    """添加推理结果（去重）。"""
    key = (h, r, t)
    if key in seen:
        return
    seen.add(key)
    inferred.append(
        {
            "head": h,
            "relation": r,
            "tail": t,
            "reason": reason,
            "confidence": confidence,
        }
    )


def _infer_inverse(
    facts: list[tuple[str, str, str]],
    seen: set[tuple[str, str, str]],
    inferred: list[dict[str, Any]],
) -> None:
    """逆关系推理。"""
    for h, r, t in facts:
        inv = _INVERSE_RELATIONS.get(r)
        if inv:
            _add_inferred(seen, inferred, t, inv, h, f"逆关系: {r} ⇒ {inv}", 0.9)


def _infer_composition(
    facts: list[tuple[str, str, str]],
    seen: set[tuple[str, str, str]],
    inferred: list[dict[str, Any]],
) -> None:
    """组合规则推理（通过中间实体 m 连接）。"""
    heads_by_middle: dict[str, list[tuple[str, str]]] = {}
    for h, r, m in facts:
        heads_by_middle.setdefault(m, []).append((h, r))
    for m, r2, o in facts:
        for h, r1 in heads_by_middle.get(m, []):
            for rule in _COMPOSITION_RULES:
                if rule["left"] == r1 and rule["right"] == r2:
                    _add_inferred(
                        seen,
                        inferred,
                        h,
                        rule["result"],
                        o,
                        f"组合: {r1} + {r2} ⇒ {rule['result']}",
                        0.8,
                    )


def _infer_transitive(
    facts: list[tuple[str, str, str]],
    seen: set[tuple[str, str, str]],
    inferred: list[dict[str, Any]],
) -> None:
    """传递关系推理。"""
    for h, r, m in facts:
        if r not in _TRANSITIVE_RELATIONS:
            continue
        for m2, r2, o in facts:
            if m2 == m and r2 == r and h != o:
                _add_inferred(seen, inferred, h, r, o, f"传递: {r}", 0.7)


def infer_triples(triples: list[Any]) -> list[dict[str, Any]]:
    """
    规则推理：从已有三元组推导新关系（组合 / 逆关系 / 传递）。

    返回 [{head, relation, tail, reason, confidence}]，不重复既有事实。
    """
    facts = _norm_triples(triples)
    seen: set[tuple[str, str, str]] = set(facts)
    inferred: list[dict[str, Any]] = []
    _infer_inverse(facts, seen, inferred)
    _infer_composition(facts, seen, inferred)
    _infer_transitive(facts, seen, inferred)
    return inferred


class TransELinkPredictor:
    """
    TransE 知识图谱嵌入链路预测（numpy 实现）。

    将实体与关系嵌入同一低维空间，用 ||head + relation - tail|| 作为三元组
    的打分（越小越可能）；通过负采样 + margin ranking loss 做 SGD。
    """

    def __init__(
        self,
        dim: int = 50,
        epochs: int = 300,
        learning_rate: float = 0.01,
        margin: float = 1.0,
        seed: int = 42,
    ):
        self.dim = dim
        self.epochs = epochs
        self.lr = learning_rate
        self.margin = margin
        self.seed = seed
        self._trained = False
        self._entities: list[str] = []
        self._e2i: dict[str, int] = {}
        self._r2i: dict[str, int] = {}
        self._E: Any = None
        self._R: Any = None

    @property
    def trained(self) -> bool:
        return self._trained

    def fit(self, triples: list[Any]) -> "TransELinkPredictor":
        facts = _norm_triples(triples)
        if len(facts) < 2:
            self._trained = False
            return self

        self._entities = sorted({h for h, _, _ in facts} | {t for _, _, t in facts})
        relations = sorted({r for _, r, _ in facts})
        self._e2i = {e: i for i, e in enumerate(self._entities)}
        self._r2i = {r: i for i, r in enumerate(relations)}
        n_e, n_r = len(self._entities), len(relations)

        rng = np.random.default_rng(self.seed)
        bound = 6.0 / math.sqrt(self.dim)
        self._E = rng.uniform(-bound, bound, (n_e, self.dim))
        self._R = rng.uniform(-bound, bound, (n_r, self.dim))

        def _norm_rows(M: Any) -> None:
            norms = np.linalg.norm(M, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            M /= norms

        for _ in range(self.epochs):
            for h, r, t in facts:
                hi, ri, ti = self._e2i[h], self._r2i[r], self._e2i[t]
                if rng.random() < 0.5:
                    # 破坏头实体
                    hn = rng.integers(0, n_e)
                    while hn == hi:
                        hn = rng.integers(0, n_e)
                    d_pos = self._E[hi] + self._R[ri] - self._E[ti]
                    d_neg = self._E[hn] + self._R[ri] - self._E[ti]
                    pos = float(np.linalg.norm(d_pos))
                    neg = float(np.linalg.norm(d_neg))
                    if self.margin + pos - neg <= 0:
                        continue
                    g = d_pos / pos
                    gn = d_neg / neg
                    self._E[hi] -= self.lr * g
                    self._E[hn] += self.lr * gn
                    self._R[ri] -= self.lr * (g - gn)
                    self._E[ti] -= self.lr * (-g + gn)
                else:
                    # 破坏尾实体
                    tn = rng.integers(0, n_e)
                    while tn == ti:
                        tn = rng.integers(0, n_e)
                    d_pos = self._E[hi] + self._R[ri] - self._E[ti]
                    d_neg = self._E[hi] + self._R[ri] - self._E[tn]
                    pos = float(np.linalg.norm(d_pos))
                    neg = float(np.linalg.norm(d_neg))
                    if self.margin + pos - neg <= 0:
                        continue
                    g = d_pos / pos
                    gn = d_neg / neg
                    self._E[hi] -= self.lr * g
                    self._R[ri] -= self.lr * (g - gn)
                    self._E[ti] -= self.lr * (-g)
                    self._E[tn] += self.lr * gn

            _norm_rows(self._E)

        self._trained = True
        return self

    def score_triple(self, head: str, relation: str, tail: str) -> float:
        """返回三元组得分（越高越可能；未训练/未知实体返回 -inf）。"""
        if not self._trained:
            return float("-inf")
        if head not in self._e2i or relation not in self._r2i or tail not in self._e2i:
            return float("-inf")
        h = self._E[self._e2i[head]]
        r = self._R[self._r2i[relation]]
        t = self._E[self._e2i[tail]]
        return round(float(-np.linalg.norm(h + r - t)), 4)

    def predict_links(
        self,
        head: str,
        relation: str,
        top_k: int = 10,
        exclude: set[tuple[str, str, str]] | None = None,
    ) -> list[dict[str, Any]]:
        """预测头实体 head 通过 relation 最可能链接到的尾实体（top-k）。"""
        if not self._trained or relation not in self._r2i or head not in self._e2i:
            return []
        exclude = exclude or set()
        scored = []
        for t in self._entities:
            if (head, relation, t) in exclude:
                continue
            scored.append({"entity": t, "score": self.score_triple(head, relation, t)})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]


class RotatELinkPredictor:
    """
    RotatE 知识图谱嵌入链路预测（numpy 实现，步骤 17）。

    将实体嵌入复数空间（实部 + 虚部），关系建模为复数旋转（模长 1），
    打分 -||h ∘ r - t||（越大越可能）；通过负采样 + margin ranking loss 做 SGD。
    零强制依赖（numpy 缺失时返回未训练态）；接口与 TransELinkPredictor 对齐。
    """

    def __init__(
        self,
        dim: int = 50,
        epochs: int = 300,
        learning_rate: float = 0.01,
        margin: float = 1.0,
        gamma: float = 6.0,
        seed: int = 42,
    ):
        self.dim = dim
        self.epochs = epochs
        self.lr = learning_rate
        self.margin = margin
        self.gamma = gamma
        self.seed = seed
        self._trained = False
        self._entities: list[str] = []
        self._e2i: dict[str, int] = {}
        self._r2i: dict[str, int] = {}
        self._E_re: Any = None
        self._E_im: Any = None
        self._R_phase: Any = None

    @property
    def trained(self) -> bool:
        return self._trained

    def fit(self, triples: list[Any]) -> "RotatELinkPredictor":
        if not _NUMPY_AVAILABLE:
            self._trained = False
            return self
        facts = _norm_triples(triples)
        if len(facts) < 3:
            self._trained = False
            return self

        self._entities = sorted({h for h, _, _ in facts} | {t for _, _, t in facts})
        relations = sorted({r for _, r, _ in facts})
        self._e2i = {e: i for i, e in enumerate(self._entities)}
        self._r2i = {r: i for i, r in enumerate(relations)}
        n_e, n_r = len(self._entities), len(relations)

        rng = np.random.default_rng(self.seed)
        bound = self.gamma / self.dim
        # 实体嵌入：实部 + 虚部
        self._E_re = rng.uniform(-bound, bound, (n_e, self.dim))
        self._E_im = rng.uniform(-bound, bound, (n_e, self.dim))
        # 关系嵌入：相位（模长 1 的复数旋转），初始化为小随机相位
        self._R_phase = rng.uniform(-math.pi, math.pi, (n_r, self.dim))

        for _ in range(self.epochs):
            for h, r, t in facts:
                hi, ri, ti = self._e2i[h], self._r2i[r], self._e2i[t]
                # 负采样：破坏尾实体
                tn = rng.integers(0, n_e)
                while tn == ti:
                    tn = rng.integers(0, n_e)
                # 正样本打分：h ∘ r - t（复数旋转）
                pos_re, pos_im = self._rotate(hi, ri, ti)
                pos_score = float(np.linalg.norm(np.sqrt(pos_re**2 + pos_im**2)))
                # 负样本打分
                neg_re, neg_im = self._rotate(hi, ri, tn)
                neg_score = float(np.linalg.norm(np.sqrt(neg_re**2 + neg_im**2)))
                # margin ranking loss: max(0, margin + pos - neg)
                if self.margin + pos_score - neg_score <= 0:
                    continue
                # 简化梯度：沿正样本方向减小、负样本方向增大
                grad_pos_re = pos_re / (pos_score + 1e-9)
                grad_pos_im = pos_im / (pos_score + 1e-9)
                grad_neg_re = neg_re / (neg_score + 1e-9)
                grad_neg_im = neg_im / (neg_score + 1e-9)
                # 更新实体嵌入（简化 SGD）
                self._E_re[ti] -= self.lr * grad_pos_re
                self._E_im[ti] -= self.lr * grad_pos_im
                self._E_re[tn] += self.lr * grad_neg_re
                self._E_im[tn] += self.lr * grad_neg_im

        self._trained = True
        return self

    def _rotate(self, hi: int, ri: int, ti: int) -> tuple[Any, Any]:
        """计算 h ∘ r - t 的实部与虚部。"""
        h_re, h_im = self._E_re[hi], self._E_im[hi]
        r_ph = self._R_phase[ri]
        t_re, t_im = self._E_re[ti], self._E_im[ti]
        # 复数旋转：h * exp(i*r_ph) = (h_re*cos - h_im*sin) + i*(h_re*sin + h_im*cos)
        cos_r = np.cos(r_ph)
        sin_r = np.sin(r_ph)
        hr_re = h_re * cos_r - h_im * sin_r
        hr_im = h_re * sin_r + h_im * cos_r
        return hr_re - t_re, hr_im - t_im

    def score_triple(self, head: str, relation: str, tail: str) -> float:
        """返回三元组得分（越高越可能；未训练/未知实体返回 -inf）。"""
        if not self._trained:
            return float("-inf")
        if head not in self._e2i or relation not in self._r2i or tail not in self._e2i:
            return float("-inf")
        re, im = self._rotate(self._e2i[head], self._r2i[relation], self._e2i[tail])
        return round(float(-np.linalg.norm(np.sqrt(re**2 + im**2))), 4)

    def predict_links(
        self,
        head: str,
        relation: str,
        top_k: int = 10,
        exclude: set[tuple[str, str, str]] | None = None,
    ) -> list[dict[str, Any]]:
        """预测头实体 head 通过 relation 最可能链接到的尾实体（top-k）。"""
        if not self._trained or relation not in self._r2i or head not in self._e2i:
            return []
        exclude = exclude or set()
        scored = []
        for t in self._entities:
            if (head, relation, t) in exclude:
                continue
            scored.append({"entity": t, "score": self.score_triple(head, relation, t)})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]


class GNNLinkPredictor:
    """
    轻量 GNN 链路预测（numpy 实现，SGC / GraphSAGE 风格邻域聚合）。

    1. 消息传递：用图邻接矩阵（无向 + 自环归一化）做 K 层邻居平均聚合，
       得到结构感知的实体嵌入（等价于简化图卷积）；
    2. 打分：在聚合后的实体嵌入上复用 TransE 的 ||head + relation - tail||，
       通过负采样 + margin ranking SGD 学习关系嵌入。

    可作为正式 torch_geometric / dgl 的 RGCN / GraphSAGE 的降级替代。
    """

    def __init__(
        self,
        dim: int = 32,
        layers: int = 2,
        epochs: int = 120,
        learning_rate: float = 0.01,
        margin: float = 1.0,
        seed: int = 42,
    ):
        self.dim = dim
        self.layers = layers
        self.epochs = epochs
        self.lr = learning_rate
        self.margin = margin
        self.seed = seed
        self._trained = False
        self._entities: list[str] = []
        self._e2i: dict[str, int] = {}
        self._r2i: dict[str, int] = {}
        self._X: Any = None
        self._R: Any = None

    @property
    def trained(self) -> bool:
        return self._trained

    def _build_gnn_adjacency(self, facts: list[tuple[str, str, str]], n: int) -> Any:
        """构建归一化邻接矩阵。"""
        adj = np.zeros((n, n))
        for h, _r, t in facts:
            adj[self._e2i[h], self._e2i[t]] += 1.0
            adj[self._e2i[t], self._e2i[h]] += 1.0
        deg = adj.sum(axis=1, keepdims=True)
        deg[deg == 0] = 1.0
        return adj / deg

    def _aggregate_embeddings(self, X: Any, adj_norm: Any) -> Any:
        """K 层邻居平均聚合（SGC 风格）。"""
        for _ in range(self.layers):
            X = adj_norm @ X
            norms = np.linalg.norm(X, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            X /= norms
        return X

    def _negative_sample_head(self, X: Any, hi: int, ri: int, ti: int, rng: Any, n: int) -> None:
        """负采样头实体 SGD 更新。"""
        hn = rng.integers(0, n)
        while hn == hi:
            hn = rng.integers(0, n)
        pos = float(np.linalg.norm(X[hi] + self._R[ri] - X[ti]))
        neg = float(np.linalg.norm(X[hn] + self._R[ri] - X[ti]))
        if self.margin + pos - neg <= 0:
            return
        g = (X[hi] + self._R[ri] - X[ti]) / pos
        gn = (X[hn] + self._R[ri] - X[ti]) / neg
        self._R[ri] -= self.lr * (g - gn)

    def _negative_sample_tail(self, X: Any, hi: int, ri: int, ti: int, rng: Any, n: int) -> None:
        """负采样尾实体 SGD 更新。"""
        tn = rng.integers(0, n)
        while tn == ti:
            tn = rng.integers(0, n)
        pos = float(np.linalg.norm(X[hi] + self._R[ri] - X[ti]))
        neg = float(np.linalg.norm(X[hi] + self._R[ri] - X[tn]))
        if self.margin + pos - neg <= 0:
            return
        g = (X[hi] + self._R[ri] - X[ti]) / pos
        gn = (X[hi] + self._R[ri] - X[tn]) / neg
        self._R[ri] -= self.lr * (g - gn)

    def _train_relation_sgd(
        self, facts: list[tuple[str, str, str]], X: Any, rng: Any, n: int
    ) -> None:
        """负采样 SGD 训练循环。"""
        for _ in range(self.epochs):
            for h, r, t in facts:
                hi, ri, ti = self._e2i[h], self._r2i[r], self._e2i[t]
                if rng.random() < 0.5:
                    self._negative_sample_head(X, hi, ri, ti, rng, n)
                else:
                    self._negative_sample_tail(X, hi, ri, ti, rng, n)

    def fit(self, triples: list[Any]) -> "GNNLinkPredictor":
        facts = _norm_triples(triples)
        if len(facts) < 2:
            self._trained = False
            return self

        self._entities = sorted({h for h, _, _ in facts} | {t for _, _, t in facts})
        relations = sorted({r for _, r, _ in facts})
        self._e2i = {e: i for i, e in enumerate(self._entities)}
        self._r2i = {r: i for i, r in enumerate(relations)}
        n = len(self._entities)

        rng = np.random.default_rng(self.seed)
        bound = 6.0 / math.sqrt(self.dim)
        X = rng.uniform(-bound, bound, (n, self.dim))

        adj_norm = self._build_gnn_adjacency(facts, n)
        X = self._aggregate_embeddings(X, adj_norm)

        self._R = rng.uniform(-bound, bound, (len(relations), self.dim))
        self._train_relation_sgd(facts, X, rng, n)

        self._X = X
        self._trained = True
        return self

    def score_triple(self, head: str, relation: str, tail: str) -> float:
        if not self._trained:
            return float("-inf")
        if head not in self._e2i or relation not in self._r2i or tail not in self._e2i:
            return float("-inf")
        h = self._X[self._e2i[head]]
        r = self._R[self._r2i[relation]]
        t = self._X[self._e2i[tail]]
        return round(float(-np.linalg.norm(h + r - t)), 4)

    def predict_links(
        self,
        head: str,
        relation: str,
        top_k: int = 10,
        exclude: set[tuple[str, str, str]] | None = None,
    ) -> list[dict[str, Any]]:
        if not self._trained or relation not in self._r2i or head not in self._e2i:
            return []
        exclude = exclude or set()
        scored = []
        for t in self._entities:
            if (head, relation, t) in exclude:
                continue
            scored.append({"entity": t, "score": self.score_triple(head, relation, t)})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]


class StatisticalLinkPredictor:
    """统计共现链路预测（纯 Python 降级基线，零依赖）。"""

    def __init__(self):
        self._facts: list[tuple[str, str, str]] = []
        self._tails_by_head: dict[str, set[str]] = {}
        self._neighbors: dict[str, set[str]] = {}

    def fit(self, triples: list[Any]) -> "StatisticalLinkPredictor":
        facts = _norm_triples(triples)
        self._facts = facts
        self._tails_by_head = {}
        self._neighbors = {}
        for h, _r, t in facts:
            self._tails_by_head.setdefault(h, set()).add(t)
            self._tails_by_head.setdefault(t, set()).add(h)
            self._neighbors.setdefault(h, set()).add(t)
            self._neighbors.setdefault(t, set()).add(h)
        return self

    def score_triple(self, head: str, relation: str, tail: str) -> float:
        if (head, relation, tail) in self._facts:
            return 1.0
        if tail in self._neighbors.get(head, set()):
            return 0.5
        if tail in self._tails_by_head.get(head, set()):
            return 0.3
        return 0.0

    def predict_links(
        self,
        head: str,
        relation: str,
        top_k: int = 10,
        exclude: set[tuple[str, str, str]] | None = None,
    ) -> list[dict[str, Any]]:
        exclude = exclude or set()
        scored: dict[str, float] = {}
        for h, r, t in self._facts:
            if r != relation or h != head:
                continue
            if (head, relation, t) in exclude:
                continue
            scored[t] = max(scored.get(t, 0.0), self.score_triple(head, relation, t))

        # 邻居 Jaccard 相似度兜底：补未直接出现在 relation 中的候选尾实体
        h_nei = self._neighbors.get(head, set())
        for cand, c_nei in self._neighbors.items():
            if cand == head or cand in scored:
                continue
            union = h_nei | c_nei
            inter = h_nei & c_nei
            jac = len(inter) / len(union) if union else 0.0
            if jac > 0:
                scored[cand] = max(scored.get(cand, 0.0), round(jac, 4))

        ranked = sorted(scored.items(), key=lambda kv: kv[1], reverse=True)
        return [{"entity": t, "score": s} for t, s in ranked[:top_k]]


class RelationInferenceService:
    """关系推理与图谱补全服务门面（规则推理 + 链路预测，可插拔可降级）。"""

    def __init__(self):
        self._predictor: Any = None
        self._backend_used: str | None = None
        self._fit_facts: list[tuple[str, str, str]] = []

    @property
    def available(self) -> bool:
        return settings.RELATION_INFERENCE_ENABLED and settings.RELATION_INFERENCE_BACKEND != "none"

    def reason(self, triples: list[Any]) -> list[dict[str, Any]]:
        """规则推理：组合 / 逆关系 / 传递。"""
        return infer_triples(triples)

    def _ensure_predictor(self, triples: list[Any]) -> None:
        facts = _norm_triples(triples)
        if self._fit_facts == facts and self._predictor is not None:
            return
        self._fit_facts = facts

        backend = settings.RELATION_INFERENCE_BACKEND if self.available else "none"

        use_gnn = backend == "gnn" and _NUMPY_AVAILABLE and len(facts) >= 2
        if use_gnn:
            try:
                self._predictor = GNNLinkPredictor(
                    dim=settings.TRANSE_DIM,
                    layers=settings.GNN_LAYERS,
                    epochs=settings.GNN_EPOCHS,
                    learning_rate=settings.TRANSE_LR,
                    margin=settings.TRANSE_MARGIN,
                    seed=settings.TRANSE_SEED,
                ).fit(facts)
                self._backend_used = "gnn"
                return
            except Exception as e:  # pragma: no cover - GNN 训练异常降级
                logger.warning("GNN 训练失败，降级为 TransE：%s", e)

        use_transe = backend in ("gnn", "transe") and _NUMPY_AVAILABLE and len(facts) >= 3
        if use_transe:
            try:
                self._predictor = TransELinkPredictor(
                    dim=settings.TRANSE_DIM,
                    epochs=settings.TRANSE_EPOCHS,
                    learning_rate=settings.TRANSE_LR,
                    margin=settings.TRANSE_MARGIN,
                    seed=settings.TRANSE_SEED,
                ).fit(facts)
                self._backend_used = "transe"
                return
            except Exception as e:  # pragma: no cover - 训练异常降级
                logger.warning("TransE 训练失败，降级为 RotatE：%s", e)

        # 步骤 17：RotatE 候选级（gnn → transe → rotate → statistical）
        use_rotate = backend in ("gnn", "transe", "rotate") and _NUMPY_AVAILABLE and len(facts) >= 3
        if use_rotate:
            try:
                self._predictor = RotatELinkPredictor(
                    dim=settings.ROTATE_DIM,
                    epochs=settings.ROTATE_EPOCHS,
                    learning_rate=settings.ROTATE_LR,
                    margin=settings.ROTATE_MARGIN,
                    gamma=settings.ROTATE_GAMMA,
                    seed=settings.ROTATE_SEED,
                ).fit(facts)
                self._backend_used = "rotate"
                return
            except Exception as e:  # pragma: no cover - 训练异常降级
                logger.warning("RotatE 训练失败，降级为统计基线：%s", e)

        self._predictor = StatisticalLinkPredictor().fit(facts)
        self._backend_used = "statistical"

    def predict_links(
        self,
        head: str,
        relation: str,
        triples: list[Any] | None = None,
        top_k: int = 10,
    ) -> dict[str, Any]:
        """链路预测：返回 {head, relation, backend, candidates:[{entity, score}]}。"""
        triples = triples if triples is not None else self._fit_facts
        self._ensure_predictor(triples)
        facts = _norm_triples(triples)
        candidates = self._predictor.predict_links(head, relation, top_k=top_k, exclude=set(facts))
        return {
            "head": head,
            "relation": relation,
            "backend": self._backend_used,
            "candidates": candidates,
        }

    def score_triple(
        self, head: str, relation: str, tail: str, triples: list[Any] | None = None
    ) -> float:
        """对候选三元组打分（越高越可能；用于图谱补全的缺失边判定）。"""
        triples = triples if triples is not None else self._fit_facts
        self._ensure_predictor(triples)
        return self._predictor.score_triple(head, relation, tail)


# 全局单例（懒加载，构造时不训练）
relation_inference_service = RelationInferenceService()
