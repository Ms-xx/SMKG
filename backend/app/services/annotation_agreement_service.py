# -*- coding: utf-8 -*-
"""
标注一致性评估服务（Inter-Rater Agreement / Annotation Consistency）

衡量多名标注员对同一批样本标注结果的一致性，支持三类经典指标：
1. Cohen's Kappa：两名标注员、名义类别；
2. Fleiss' Kappa：多名标注员、名义类别（每样本标注员数可变）；
3. Krippendorff's Alpha：任意标注员数量，支持名义/区间/比值等度量。

依赖策略（可插拔、可降级）：
- 全部指标为纯 Python 实现、零依赖、确定性，永远可用；
- Krippendorff's Alpha 通过距离函数支持 nominal（默认）/ interval / ratio 三种度量。

输入约定：
- ratings 为「样本 × 标注员」矩阵：ratings[subject][rater]；
- 单元格为类别标签（字符串或数值），可为 None 表示缺失，缺失会自动跳过。
"""
from __future__ import annotations

from typing import Any, Iterable

from app.core.config import settings

# 支持的评估指标与 Krippendorff 度量
METRICS = ("cohens", "fleiss", "krippendorff")
KRIPPENDORFF_METRICS = ("nominal", "interval", "ratio")


def _sorted_unique(values: Iterable[Any]) -> list[Any]:
    """去重排序（用 str 作为排序键以兼容混合类型），保证索引映射确定性。"""
    return sorted(set(values), key=str)


def cohens_kappa(rater1: Iterable[Any], rater2: Iterable[Any]) -> float | None:
    """
    Cohen's Kappa：两名标注员的名义类别一致性。

    参数为两名标注员各自对同一批样本的标注序列（等长，允许 None 缺失）。
    返回 kappa ∈ [-1, 1]；数据不足返回 None。
    """
    a, b = list(rater1), list(rater2)
    pairs = [(x, y) for x, y in zip(a, b, strict=False) if x is not None and y is not None]
    n = len(pairs)
    if n == 0:
        return None
    cats = _sorted_unique(c for pair in pairs for c in pair)
    if len(cats) < 2:
        return 1.0
    idx = {c: i for i, c in enumerate(cats)}
    k = len(cats)
    mat = [[0] * k for _ in range(k)]
    for x, y in pairs:
        mat[idx[x]][idx[y]] += 1
    po = sum(mat[i][i] for i in range(k)) / n
    row = [sum(mat[i]) for i in range(k)]
    col = [sum(mat[i][j] for i in range(k)) for j in range(k)]
    pe = sum(row[i] * col[i] for i in range(k)) / (n * n)
    if abs(1.0 - pe) < 1e-12:
        return 1.0
    return (po - pe) / (1.0 - pe)


def fleiss_kappa(ratings: list[list[Any]]) -> float | None:
    """
    Fleiss' Kappa：多名标注员的名义类别一致性。

    ratings 为「样本 × 标注员」矩阵（每样本标注员数可不同，缺失 None 已剔除）。
    返回 kappa ∈ [-1, 1]；数据不足返回 None。
    """
    rows = [[r for r in row if r is not None] for row in ratings]
    rows = [r for r in rows if len(r) >= 2]
    n = len(rows)
    if n == 0:
        return None
    cats = _sorted_unique(c for row in rows for c in row)
    if len(cats) < 2:
        return 1.0
    idx = {c: i for i, c in enumerate(cats)}
    k = len(cats)

    p_i_list: list[float] = []
    cat_totals = [0] * k
    total_assign = 0
    for row in rows:
        m = len(row)
        counts = [0] * k
        for c in row:
            i = idx[c]
            counts[i] += 1
            cat_totals[i] += 1
            total_assign += 1
        p_i = (sum(cnt * cnt for cnt in counts) - m) / (m * (m - 1))
        p_i_list.append(p_i)

    mean_p = sum(p_i_list) / n
    p_c = [c / total_assign for c in cat_totals]
    pe = sum(pc * pc for pc in p_c)
    if abs(1.0 - pe) < 1e-12:
        return 1.0
    return (mean_p - pe) / (1.0 - pe)


def krippendorff_alpha(ratings: list[list[Any]], metric: str = "nominal") -> float | None:
    """
    Krippendorff's Alpha：任意标注员数量的一致性，基于共现矩阵 + 距离函数。

    metric：
    - nominal（默认）：不同类别视为完全不一致（delta=1）；
    - interval：数值差的平方（(a-b)^2）；
    - ratio：归一化差的平方（((a-b)/(a+b))^2）。

    返回 alpha ∈ [-1, 1]；数据不足返回 None。
    """
    rows = [[r for r in row if r is not None] for row in ratings]
    rows = [r for r in rows if len(r) >= 2]
    if not rows:
        return None
    vals = _sorted_unique(v for row in rows for v in row)
    if len(vals) < 2:
        return 1.0
    vidx = {v: i for i, v in enumerate(vals)}
    nv = len(vals)

    metric = metric or "nominal"
    nums: list[float] | None = None
    if metric in ("interval", "ratio"):
        nums = []
        for v in vals:
            try:
                nums.append(float(v))
            except (TypeError, ValueError):
                nums.append(float(vidx[v]))

    def delta(i: int, j: int) -> float:
        if metric == "interval":
            return (nums[i] - nums[j]) ** 2
        if metric == "ratio":
            s = nums[i] + nums[j]
            return ((nums[i] - nums[j]) / s) ** 2 if s != 0 else 0.0
        # nominal（含未知度量回退）
        return 0.0 if i == j else 1.0

    # 共现矩阵：同一样本内不同标注员的两两取值，权重 1/(m-1)
    o = [[0.0] * nv for _ in range(nv)]
    for row in rows:
        m = len(row)
        w = 1.0 / (m - 1)
        for a in range(m):
            ia = vidx[row[a]]
            for b in range(m):
                if a == b:
                    continue
                o[ia][vidx[row[b]]] += w

    total = sum(sum(r) for r in o)
    if total <= 0:
        return None

    do = sum(o[a][b] * delta(a, b) for a in range(nv) for b in range(nv)) / total
    marg = [sum(o[a]) for a in range(nv)]
    de_num = sum(marg[a] * marg[b] * delta(a, b) for a in range(nv) for b in range(nv))
    de = de_num / (total * (total - 1)) if total > 1 else 0.0
    if abs(de) < 1e-12:
        return 1.0 if do <= 1e-12 else 0.0
    alpha = 1.0 - do / de
    return max(-1.0, min(1.0, alpha))


class AnnotationAgreementService:
    """标注一致性评估门面：Cohen's / Fleiss' / Krippendorff，可插拔可降级。"""

    @property
    def available(self) -> bool:
        return settings.ANNOTATION_AGREEMENT_ENABLED

    @staticmethod
    def _clean(ratings: list[list[Any]]) -> tuple[list[list[Any]], int, int]:
        rows = [[r for r in row if r is not None] for row in ratings]
        rows = [r for r in rows if r]
        n_subjects = len(rows)
        n_raters = max((len(r) for r in rows), default=0)
        return rows, n_subjects, n_raters

    @staticmethod
    def _cohens_summary(rows: list[list[Any]]) -> float | None:
        m = max((len(r) for r in rows), default=0)
        if m < 2:
            return None
        if m == 2:
            c1 = [r[0] for r in rows if len(r) >= 2]
            c2 = [r[1] for r in rows if len(r) >= 2]
            return cohens_kappa(c1, c2)
        # 多标注员：两两 Cohen's Kappa 均值
        vals: list[float] = []
        for a in range(m):
            for b in range(a + 1, m):
                subs = [r for r in rows if len(r) > a and len(r) > b]
                k = cohens_kappa([r[a] for r in subs], [r[b] for r in subs])
                if k is not None:
                    vals.append(k)
        return sum(vals) / len(vals) if vals else None

    def evaluate(
        self,
        ratings: list[list[Any]],
        metrics: list[str] | None = None,
        krippendorff_metric: str = "nominal",
    ) -> dict[str, Any]:
        """
        对标注结果矩阵计算一致性指标。

        Returns:
            {"n_subjects", "n_raters", "cohens_kappa", "fleiss_kappa",
             "krippendorff_alpha", "krippendorff_metric"}
        """
        rows, n_subjects, n_raters = self._clean(ratings)
        if metrics is None:
            metrics = list(METRICS)
        out: dict[str, Any] = {"n_subjects": n_subjects, "n_raters": n_raters}

        if "cohens" in metrics:
            out["cohens_kappa"] = self._cohens_summary(rows)
        if "fleiss" in metrics:
            out["fleiss_kappa"] = fleiss_kappa(rows)
        if "krippendorff" in metrics:
            out["krippendorff_alpha"] = krippendorff_alpha(rows, krippendorff_metric)
            out["krippendorff_metric"] = krippendorff_metric
        return out


# 全局单例（懒加载，构造时不做计算）
annotation_agreement_service = AnnotationAgreementService()
