# -*- coding: utf-8 -*-
"""
置信度校准与漂移检测服务（Confidence Calibration & Data Drift Detection）

在「标注 → 训练 → 部署 → 监控」闭环中提供两部分能力：
1. 置信度校准：
   - Temperature Scaling：对 logits 除以温度 T 后 softmax，网格搜索最小化 NLL 拟合 T；
   - Platt Scaling：对二分类置信度做逻辑回归（`sigmoid(a*s + b)`），梯度下降拟合 a、b；
   - 校准质量评估：Expected Calibration Error（ECE）与 Reliability Curve（可靠性直方图）。
2. 数据漂移检测：
   - PSI（Population Stability Index，数值分布漂移）；
   - KS（Kolmogorov-Smirnov 两样本统计量，数值分布漂移）；
   - 卡方（Chi-Square，类别分布漂移）；
   - 阈值分级告警（stable / warning / drift）。

依赖策略（可插拔、可降级）：全部为纯 Python 实现、零依赖、确定性，永远可用。
"""
from __future__ import annotations

import math
from typing import Any, Iterable

from app.core.config import settings

# 漂移状态分级（PSI 常用阈值 0.1 / 0.25）
DRIFT_STATUS = ("stable", "warning", "drift")


def softmax(logits: Iterable[float], temperature: float = 1.0) -> list[float]:
    """带温度参数的 softmax：温度越大分布越均匀。"""
    t = float(temperature) if temperature and temperature > 0 else 1.0
    z = [float(x) / t for x in logits]
    m = max(z)
    exps = [math.exp(v - m) for v in z]
    total = sum(exps)
    return [e / total for e in exps]


def sigmoid(x: float) -> float:
    """数值稳定的 sigmoid。"""
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


# ── 1. Temperature Scaling ───────────────────────────────


def _nll_temperature(logits: list[list[float]], labels: list[int], t: float) -> float:
    total = 0.0
    for lg, y in zip(logits, labels, strict=False):
        p = softmax(lg, t)
        total += -math.log(max(float(p[y]), 1e-12))
    return total / len(labels)


def fit_temperature(
    logits: list[list[float]],
    labels: list[int],
    temperatures: Iterable[float] | None = None,
) -> tuple[float, float]:
    """
    网格搜索拟合温度 T（最小化 NLL）。返回 (best_T, best_nll)。

    默认搜索 T ∈ [0.2, 3.0]（步长 0.1）+ 1.0，纯 Python、确定性。
    """
    if not logits or not labels or len(logits) != len(labels):
        return 1.0, 0.0
    grid = list(temperatures) if temperatures else [round(0.2 + 0.1 * i, 2) for i in range(29)]
    if 1.0 not in grid:
        grid.append(1.0)
    best_t, best_nll = 1.0, float("inf")
    for t in grid:
        nll = _nll_temperature(logits, labels, t)
        if nll < best_nll:
            best_nll, best_t = nll, t
    return best_t, best_nll


# ── 2. Platt Scaling ─────────────────────────────────────


def fit_platt(
    scores: Iterable[float], labels: Iterable[int], lr: float = 0.1, epochs: int = 200
) -> tuple[float, float]:
    """
    拟合 Platt Scaling 参数：`P(y=1) = sigmoid(a*s + b)`。

    对二分类标签（0/1）做单变量逻辑回归（梯度下降，纯 Python）。返回 (a, b)。
    """
    s = [float(x) for x in scores]
    y = [int(x) for x in labels]
    n = len(s)
    if n == 0:
        return 0.0, 0.0
    a, b = 0.0, 0.0
    for _ in range(epochs):
        ga = gb = 0.0
        for si, yi in zip(s, y, strict=False):
            p = sigmoid(a * si + b)
            ga += (p - yi) * si
            gb += p - yi
        a -= lr * ga / n
        b -= lr * gb / n
    return a, b


def platt_calibrate(scores: Iterable[float], a: float, b: float) -> list[float]:
    """用已拟合参数对置信度做 Platt 校准。"""
    return [sigmoid(a * float(x) + b) for x in scores]


# ── 3. 校准质量评估 ──────────────────────────────────────


def expected_calibration_error(
    probs: Iterable[float], labels: Iterable[int], n_bins: int = 10
) -> float:
    """
    Expected Calibration Error：按置信度分箱，计算 |accuracy - confidence| 的加权平均。
    """
    p = [float(x) for x in probs]
    y = [int(x) for x in labels]
    n = len(p)
    if n == 0:
        return 0.0
    bins = n_bins or 10
    counts = [0] * bins
    conf_sum = [0.0] * bins
    acc_sum = [0.0] * bins
    for pi, yi in zip(p, y, strict=False):
        idx = min(int(pi * bins), bins - 1)
        counts[idx] += 1
        conf_sum[idx] += pi
        acc_sum[idx] += yi
    ece = 0.0
    for i in range(bins):
        if counts[i] == 0:
            continue
        conf = conf_sum[i] / counts[i]
        acc = acc_sum[i] / counts[i]
        ece += (counts[i] / n) * abs(acc - conf)
    return ece


def reliability_curve(
    probs: Iterable[float], labels: Iterable[int], n_bins: int = 10
) -> list[dict[str, Any]]:
    """可靠性直方图：每箱的置信度均值 / 准确率 / 样本数 / 区间。"""
    p = [float(x) for x in probs]
    y = [int(x) for x in labels]
    bins = n_bins or 10
    counts = [0] * bins
    conf_sum = [0.0] * bins
    acc_sum = [0.0] * bins
    for pi, yi in zip(p, y, strict=False):
        idx = min(int(pi * bins), bins - 1)
        counts[idx] += 1
        conf_sum[idx] += pi
        acc_sum[idx] += yi
    out: list[dict[str, Any]] = []
    for i in range(bins):
        low = i / bins
        high = (i + 1) / bins
        out.append(
            {
                "bin": i,
                "range": [low, high],
                "count": counts[i],
                "confidence": (conf_sum[i] / counts[i]) if counts[i] else None,
                "accuracy": (acc_sum[i] / counts[i]) if counts[i] else None,
            }
        )
    return out


# ── 4. 数据漂移检测 ──────────────────────────────────────


def psi(
    expected: Iterable[float], actual: Iterable[float], bins: int = 10, epsilon: float = 1e-6
) -> float:
    """
    Population Stability Index：基于期望分布分位区间，度量实际分布相对期望分布的偏移。

    PSI < 0.1 稳定；0.1 ~ 0.25 轻微漂移；> 0.25 显著漂移。
    """
    e = [float(x) for x in expected]
    a = [float(x) for x in actual]
    if not e or not a:
        return 0.0
    lo, hi = min(e), max(e)
    if hi - lo < 1e-12:
        return 0.0
    n_bins = bins or 10

    def _hist(vals: list[float]) -> list[int]:
        counts = [0] * n_bins
        for v in vals:
            idx = min(int((v - lo) / (hi - lo) * n_bins), n_bins - 1)
            counts[idx] += 1
        return counts

    e_counts = _hist(e)
    a_counts = _hist(a)
    n_e = len(e)
    n_a = len(a)
    value = 0.0
    for ec, ac in zip(e_counts, a_counts, strict=False):
        ep = ec / n_e + epsilon
        ap = ac / n_a + epsilon
        value += (ap - ep) * math.log(ap / ep)
    return value


def ks_statistic(ref: Iterable[float], curr: Iterable[float]) -> float:
    """
    两样本 Kolmogorov-Smirnov 统计量：经验 CDF 的最大差异 D ∈ [0, 1]。

    基于两分布的唯一取值遍历，`F(x) = P(X <= x)`，正确合并等值点。
    """
    a = sorted(float(x) for x in ref)
    b = sorted(float(x) for x in curr)
    n1, n2 = len(a), len(b)
    if n1 == 0 or n2 == 0:
        return 0.0
    values = sorted(set(a) | set(b))
    ia = ib = 0
    d = 0.0
    for v in values:
        while ia < n1 and a[ia] <= v:
            ia += 1
        while ib < n2 and b[ib] <= v:
            ib += 1
        diff = abs(ia / n1 - ib / n2)
        if diff > d:
            d = diff
    return d


def chi_square_drift(
    ref_counts: dict[Any, int],
    curr_counts: dict[Any, int],
    epsilon: float = 1e-6,
) -> float:
    """
    类别分布漂移卡方统计量：将期望（参考）分布按当前总量缩放后计算 Σ(O-E)²/E。
    """
    keys = set(ref_counts) | set(curr_counts)
    total_r = sum(ref_counts.values())
    total_c = sum(curr_counts.values())
    if total_r == 0 or total_c == 0 or total_r == total_c == 0:
        return 0.0
    chi2 = 0.0
    for k in keys:
        observed = float(curr_counts.get(k, 0))
        expected = float(ref_counts.get(k, 0)) * total_c / total_r
        if expected < epsilon:
            continue
        chi2 += (observed - expected) ** 2 / expected
    return chi2


def classify_psi(value: float, warning: float | None = None, alert: float | None = None) -> str:
    """PSI 分级：< warning 稳定；warning ~ alert 轻微漂移；> alert 显著漂移。"""
    low = settings.DRIFT_PSI_WARNING if warning is None else warning
    high = settings.DRIFT_PSI_ALERT if alert is None else alert
    if value < low:
        return "stable"
    if value < high:
        return "warning"
    return "drift"


# ── 门面服务 ─────────────────────────────────────────────


class CalibrationDriftService:
    """置信度校准 + 漂移检测门面，可插拔可降级。"""

    @property
    def available(self) -> bool:
        return settings.CALIBRATION_DRIFT_ENABLED

    def calibrate(
        self,
        method: str = "temperature",
        logits: list[list[float]] | None = None,
        labels: list[int] | None = None,
        scores: list[float] | None = None,
        binary_labels: list[int] | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """
        置信度校准。

        - method=temperature：对 logits 做温度缩放；未显式给 temperature 且提供 labels 时
          自动网格搜索拟合 T；返回逐样本校准后的概率分布。
        - method=platt：对二分类 scores 拟合 sigmoid(a*s+b)；返回逐样本校准概率。
        """
        if method == "platt":
            if scores is None or binary_labels is None:
                return {"ok": False, "error": "platt 需要 scores 与 binary_labels"}
            a, b = fit_platt(scores, binary_labels)
            return {
                "ok": True,
                "method": "platt",
                "a": a,
                "b": b,
                "probs": platt_calibrate(scores, a, b),
            }

        if logits is None:
            return {"ok": False, "error": "temperature 需要 logits"}
        if temperature is None and labels is not None:
            temperature, _ = fit_temperature(logits, labels)
        t = float(temperature) if temperature else 1.0
        return {
            "ok": True,
            "method": "temperature",
            "temperature": t,
            "probs": [softmax(lg, t) for lg in logits],
        }

    def evaluate_calibration(
        self, probs: list[float], labels: list[int], n_bins: int | None = None
    ) -> dict[str, Any]:
        """校准质量评估：ECE + 可靠性曲线。"""
        bins = n_bins if n_bins is not None else settings.CALIBRATION_ECE_BINS
        return {
            "ece": expected_calibration_error(probs, labels, bins),
            "n_bins": bins,
            "reliability": reliability_curve(probs, labels, bins),
        }

    def detect_drift(
        self,
        reference: list[Any],
        current: list[Any],
        method: str = "psi",
        categorical: bool = False,
    ) -> dict[str, Any]:
        """
        数据漂移检测。

        - 数值（categorical=False）：method=psi（PSI）/ ks（KS 统计量）；
        - 类别（categorical=True）：method 忽略，按卡方统计量 + 分级（用 PSI 阈值近似）。
        """
        if categorical:
            ref_counts: dict[Any, int] = {}
            for c in reference:
                ref_counts[c] = ref_counts.get(c, 0) + 1
            cur_counts: dict[Any, int] = {}
            for c in current:
                cur_counts[c] = cur_counts.get(c, 0) + 1
            value = chi_square_drift(ref_counts, cur_counts)
            return {
                "method": "chi_square",
                "value": value,
                "status": classify_psi(value),
                "warning": settings.DRIFT_PSI_WARNING,
                "alert": settings.DRIFT_PSI_ALERT,
            }

        if method == "ks":
            value = ks_statistic(reference, current)
            return {
                "method": "ks",
                "value": value,
                "status": classify_psi(value),
                "warning": settings.DRIFT_PSI_WARNING,
                "alert": settings.DRIFT_PSI_ALERT,
            }

        value = psi(reference, current)
        return {
            "method": "psi",
            "value": value,
            "status": classify_psi(value),
            "warning": settings.DRIFT_PSI_WARNING,
            "alert": settings.DRIFT_PSI_ALERT,
        }


# 全局单例（懒加载，构造时不做计算）
calibration_drift_service = CalibrationDriftService()
