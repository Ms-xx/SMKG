# -*- coding: utf-8 -*-
"""
A/B 测试框架（Model A/B Testing & Statistical Significance）

围绕「模型版本对比评估」主线，覆盖步骤 8 的三项能力：
1. 流量分流（8.1）：按权重把请求/用户（subject）确定性路由到不同模型变体；
2. 指标采集（8.2）：按变体收集观测值（准确率 / 延迟 / 用户满意度等）；
3. 统计显著性判定与结论面板（8.3）：对两个变体做假设检验，输出 p 值、
   效应量、胜负结论。

依赖策略：纯 Python 零依赖、确定性（统计量手写实现，不依赖 scipy），永远可用；
存储默认进程内内存注册表，`AB_TEST_STORE_PATH` 可指定 JSON 文件持久化，接口不变。

指标类型：
- binary：每次观测为成功/失败（转化率 / 准确率 / 满意度达标），用双比例 z 检验；
- continuous：每次观测为数值（延迟 / 评分 / 分数），用 Welch t 检验（异方差）。

方向约定：`minimize=False` 表示指标越大越优（准确率 / 满意度），=True 表示越小越优（延迟）。
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import threading
import time
from typing import Any

from loguru import logger

from app.core.config import settings

# 指标类型
METRIC_BINARY = "binary"
METRIC_CONTINUOUS = "continuous"


# ── 统计工具（零依赖手写：正态 CDF / t 分布 CDF / 双比例 z / Welch t）─────────
def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _z_two_tailed(z: float) -> float:
    return 2.0 * (1.0 - _normal_cdf(abs(z)))


def _betacf(a: float, b: float, x: float, max_iter: int = 200, eps: float = 3e-12) -> float:
    """连分式计算正则化不完全 beta 函数的连分项（Numerical Recipes 算法）。"""
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def _ibeta(a: float, b: float, x: float) -> float:
    """正则化不完全 beta 函数 I_x(a, b)。"""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    bt = math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def _t_cdf(t: float, df: float) -> float:
    """学生 t 分布 CDF（df 自由度）。"""
    x = df / (df + t * t)
    ib = _ibeta(df / 2.0, 0.5, x)
    return 1.0 - 0.5 * ib if t >= 0 else 0.5 * ib


def proportion_z_test(sa: int, na: int, sb: int, nb: int) -> dict[str, float]:
    """双比例 z 检验（binary 指标）。返回 z、p 值、两变体的率。"""
    pa = sa / na if na else 0.0
    pb = sb / nb if nb else 0.0
    p_pool = (sa + sb) / (na + nb) if (na + nb) else 0.0
    if na < 1 or nb < 1 or p_pool in (0.0, 1.0):
        return {"z": 0.0, "p_value": 1.0, "rate_a": pa, "rate_b": pb}
    se = math.sqrt(p_pool * (1.0 - p_pool) * (1.0 / na + 1.0 / nb))
    if se == 0.0:
        return {"z": 0.0, "p_value": 1.0, "rate_a": pa, "rate_b": pb}
    z = (pb - pa) / se
    return {"z": z, "p_value": _z_two_tailed(z), "rate_a": pa, "rate_b": pb}


def welch_ttest(
    mean_a: float, var_a: float, n_a: int, mean_b: float, var_b: float, n_b: int
) -> dict[str, float]:
    """Welch 异方差 t 检验（continuous 指标）。返回 t、p 值、自由度。"""
    if n_a < 2 or n_b < 2:
        return {"t": 0.0, "p_value": 1.0, "df": 0.0}
    se = math.sqrt(var_a / n_a + var_b / n_b)
    if se == 0.0:
        return {"t": 0.0, "p_value": 1.0, "df": 0.0}
    t = (mean_a - mean_b) / se
    df_num = (var_a / n_a + var_b / n_b) ** 2
    df_den = (var_a / n_a) ** 2 / (n_a - 1) + (var_b / n_b) ** 2 / (n_b - 1)
    df = df_num / df_den if df_den > 0 else 1.0
    p = 2.0 * (1.0 - _t_cdf(abs(t), df))
    return {"t": t, "p_value": p, "df": df}


def _mean_var(values: list[float]) -> tuple[float, float]:
    n = len(values)
    if n == 0:
        return 0.0, 0.0
    mean = sum(values) / n
    if n < 2:
        return mean, 0.0
    var = sum((v - mean) ** 2 for v in values) / (n - 1)  # 样本方差 ddof=1
    return mean, var


# ── 存储 ──────────────────────────────────────────────────────────────
class _ABStore:
    """进程内 A/B 实验注册表，线程安全，可 JSON 持久化。"""

    def __init__(self, path: str | None = None):
        self._lock = threading.Lock()
        self._experiments: dict[str, dict[str, Any]] = {}
        self._path = path
        if path:
            self._load()

    def _load(self) -> None:
        if not self._path or not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._experiments = data.get("experiments", {})
        except (OSError, ValueError) as exc:
            logger.warning(f"A/B 实验注册表加载失败，降级为空：{exc}")

    def _save(self) -> None:
        if not self._path:
            return
        try:
            os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump({"experiments": self._experiments}, f, ensure_ascii=False, default=str)
        except OSError as exc:
            logger.warning(f"A/B 实验注册表持久化失败：{exc}")

    def add(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._experiments[record["id"]] = record
            self._save()
        return dict(record)

    def get(self, experiment_id: str) -> dict[str, Any] | None:
        with self._lock:
            rec = self._experiments.get(experiment_id)
            return dict(rec) if rec else None

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self._experiments.values()]


class ABTestService:
    """A/B 测试门面：流量分流 / 指标采集 / 统计显著性判定。可插拔可降级。"""

    def __init__(self) -> None:
        self._store = _ABStore(settings.AB_TEST_STORE_PATH or None)

    @property
    def available(self) -> bool:
        return settings.AB_TEST_ENABLED

    # ── 1. 创建实验 ────────────────────────────────────────────
    def create_experiment(
        self,
        name: str,
        variants: list[str],
        weights: list[float] | None = None,
        metric_type: str = METRIC_BINARY,
        metric_name: str = "metric",
        minimize: bool = False,
        alpha: float | None = None,
    ) -> dict[str, Any]:
        """创建 A/B 实验：变体 + 分流权重 + 指标类型方向。

        Args:
            variants: 变体标识列表（如 ["ner-v1", "ner-v2"]），须 ≥ 2 且唯一。
            weights: 各变体分流权重（缺省均分）；长度须与 variants 一致且为正。
            metric_type: binary（成功率）| continuous（数值）。
            minimize: True 表示指标越小越优（如延迟）。
        """
        if metric_type not in (METRIC_BINARY, METRIC_CONTINUOUS):
            metric_type = METRIC_BINARY
        if len(variants) < 2:
            raise ValueError("A/B 实验至少需要 2 个变体")
        if len(set(variants)) != len(variants):
            raise ValueError("变体标识必须唯一")
        if weights is None:
            weights = [1.0] * len(variants)
        if len(weights) != len(variants) or any(w <= 0 for w in weights):
            raise ValueError("权重须与变体数量一致且均为正数")
        alpha = alpha if alpha is not None else settings.AB_TEST_ALPHA
        record = {
            "id": f"ab-{len(self._store.list()) + 1:04d}",
            "name": name,
            "variants": list(variants),
            "weights": [float(w) for w in weights],
            "metric_type": metric_type,
            "metric_name": metric_name,
            "minimize": bool(minimize),
            "alpha": float(alpha),
            "created_at": time.time(),
            "assignments": dict.fromkeys(variants, 0),
            "observations": {v: {} for v in variants},  # variant -> {metric_name: [values]}
        }
        return self._store.add(record)

    # ── 2. 流量分流 ────────────────────────────────────────────
    def assign(self, experiment_id: str, subject_id: str) -> dict[str, Any]:
        """按权重把 subject 确定性路由到某个变体（哈希取模，同一 subject 稳定）。"""
        exp = self._store.get(experiment_id)
        if exp is None:
            raise KeyError(f"实验 {experiment_id} 不存在")
        variant = self._pick_variant(exp["variants"], exp["weights"], subject_id)
        with self._store._lock:
            rec = self._store._experiments[experiment_id]
            rec["assignments"][variant] = rec["assignments"].get(variant, 0) + 1
            self._store._save()
        return {
            "experiment_id": experiment_id,
            "subject_id": subject_id,
            "variant": variant,
        }

    @staticmethod
    def _pick_variant(variants: list[str], weights: list[float], subject_id: str) -> str:
        digest = hashlib.sha256(subject_id.encode("utf-8")).hexdigest()
        x = int(digest[:16], 16) / float(2**64)  # [0, 1)
        total = sum(weights)
        cumulative = 0.0
        for variant, w in zip(variants, weights, strict=False):
            cumulative += w / total
            if x < cumulative:
                return variant
        return variants[-1]

    # ── 3. 指标采集 ────────────────────────────────────────────
    def record(
        self,
        experiment_id: str,
        variant: str,
        value: float | int | bool,
        metric_name: str | None = None,
    ) -> dict[str, Any]:
        """记录一次观测：binary 指标 value 为 0/1（或 bool），continuous 为数值。"""
        exp = self._store.get(experiment_id)
        if exp is None:
            raise KeyError(f"实验 {experiment_id} 不存在")
        if variant not in exp["variants"]:
            raise ValueError(f"变体 {variant} 不在实验 {experiment_id} 中")
        metric = metric_name or exp["metric_name"]
        if isinstance(value, bool):
            value = 1.0 if value else 0.0
        else:
            value = float(value)
        with self._store._lock:
            rec = self._store._experiments[experiment_id]
            obs = rec["observations"][variant]
            obs.setdefault(metric, []).append(value)
            self._store._save()
        return {
            "experiment_id": experiment_id,
            "variant": variant,
            "metric": metric,
            "value": value,
        }

    # ── 4. 统计显著性判定与结论 ────────────────────────────────
    def evaluate(
        self,
        experiment_id: str,
        metric_name: str | None = None,
        variant_a: str | None = None,
        variant_b: str | None = None,
        alpha: float | None = None,
    ) -> dict[str, Any]:
        """对比两个变体并输出结论（p 值 / 效应量 / 胜负 / 显著与否）。"""
        exp = self._store.get(experiment_id)
        if exp is None:
            raise KeyError(f"实验 {experiment_id} 不存在")
        variants = exp["variants"]
        a = variant_a or variants[0]
        b = variant_b or variants[1]
        if a not in variants or b not in variants:
            raise ValueError("待对比变体不在实验中")
        metric = metric_name or exp["metric_name"]
        metric_type = exp["metric_type"]
        alpha = alpha if alpha is not None else exp["alpha"]

        with self._store._lock:
            obs_a = list(exp["observations"].get(a, {}).get(metric, []))
            obs_b = list(exp["observations"].get(b, {}).get(metric, []))

        base = {
            "experiment_id": experiment_id,
            "experiment_name": exp["name"],
            "metric": metric,
            "metric_type": metric_type,
            "minimize": exp["minimize"],
            "alpha": alpha,
            "variant_a": a,
            "variant_b": b,
            "n_a": len(obs_a),
            "n_b": len(obs_b),
        }

        min_samples = settings.AB_TEST_MIN_SAMPLES
        base["min_samples_met"] = len(obs_a) >= min_samples and len(obs_b) >= min_samples

        if metric_type == METRIC_BINARY:
            sa = int(sum(1 for v in obs_a if v > 0))
            sb = int(sum(1 for v in obs_b if v > 0))
            stat = proportion_z_test(sa, len(obs_a), sb, len(obs_b))
            summary_a = {"n": len(obs_a), "rate": stat["rate_a"]}
            summary_b = {"n": len(obs_b), "rate": stat["rate_b"]}
            statistic = {
                "test": "two-proportion z-test",
                "z": stat["z"],
                "p_value": stat["p_value"],
            }
            p_value = stat["p_value"]
            effect = stat["rate_b"] - stat["rate_a"]
            lift = (stat["rate_b"] - stat["rate_a"]) / stat["rate_a"] if stat["rate_a"] > 0 else 0.0
        else:
            mean_a, var_a = _mean_var(obs_a)
            mean_b, var_b = _mean_var(obs_b)
            stat = welch_ttest(mean_a, var_a, len(obs_a), mean_b, var_b, len(obs_b))
            summary_a = {"n": len(obs_a), "mean": mean_a, "std": math.sqrt(var_a)}
            summary_b = {"n": len(obs_b), "mean": mean_b, "std": math.sqrt(var_b)}
            statistic = {
                "test": "Welch t-test",
                "t": stat["t"],
                "p_value": stat["p_value"],
                "df": stat["df"],
            }
            p_value = stat["p_value"]
            effect = mean_b - mean_a
            lift = (mean_b - mean_a) / abs(mean_a) if mean_a != 0 else 0.0

        significant = p_value < alpha
        # 判定胜负：continuous/binary 的 effect 更大（或更小）者胜；样本不足时不判胜负
        better_is_b = (effect < 0) if exp["minimize"] else (effect > 0)
        if not base["min_samples_met"]:
            winner = None
            conclusion = "样本量不足，暂不判定（建议继续采集）"
        elif not significant:
            winner = None
            conclusion = "差异不显著，两个变体无显著优劣"
        else:
            winner = b if better_is_b else a
            conclusion = f"变体 {winner} 显著更优（p={p_value:.4f}）"

        return {
            **base,
            "variants": {a: summary_a, b: summary_b},
            "statistic": statistic,
            "p_value": p_value,
            "effect_size": effect,
            "lift": lift,
            "significant": significant,
            "winner": winner,
            "conclusion": conclusion,
        }

    # ── 5. 查询 ────────────────────────────────────────────────
    def get_experiment(self, experiment_id: str) -> dict[str, Any] | None:
        return self._store.get(experiment_id)

    def list_experiments(self) -> list[dict[str, Any]]:
        return self._store.list()


# 全局单例（懒加载，构造时不做计算）
ab_test_service = ABTestService()
