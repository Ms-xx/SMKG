# -*- coding: utf-8 -*-
"""
步骤 21：GitHub 开源复现性优先推荐 —— 排序 + 互动 DAO（模块四）

职责：
在步骤 8 既有「相关性推荐」（paper_retrieval_service.recommend）之上，叠加两个
可解释因子，形成「复现性优先」推荐排序：

    总分 = REPO_RECOMMEND_CORR_WEIGHT * 相关性
         + REPO_RECOMMEND_REPRO_WEIGHT * 复现性（star 对数归一化；无仓库则低分）
         + REPO_RECOMMEND_FEEDBACK_WEIGHT * 用户反馈（like−dislike，跨用户聚合）

- 相关性：复用以步骤 8 的 Jaccard 打分；
- 复现性：论文正文抽取到的仓库（见 repo_availability_service）中最佳仓库的
  log1p(1+star)/(log_scale) 归一化；`source:"offline"` 的仓库星标为 None → 复现性仅取
  少量「存在开源代码」基础分，绝不编造；可达时用真实 star。
- 反馈：跨用户点赞/踩净分经 tanh 平滑到 0~1，供多用户推荐算法复用。

拆分为「纯排序函数（可单测）」+「异步 DAO（读/写 recommend_records / recommend_feedback）」。
"""
from __future__ import annotations

import math
from typing import Any

from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.plugin.base import Plugin
from app.models.recommend import RecommendFeedback, RecommendRecord
from app.services.paper_retrieval_service import re_findall
from app.services.repo_availability_service import enrich_candidates


def _core():
    import app.services.repo_recommend_service as m

    return m


# enrich_candidates 经本模块再导出供门面消费（recommend_ranked 运行期经 _core() 动态寻址读取补丁）
__all__ = ["enrich_candidates"]

# ── 排序纯函数（确定性，零 DB 依赖） ────────────────────────────────────


def _jaccard(a: str, b: str) -> float:
    sa, sb = set(re_findall(a)), set(re_findall(b))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def star_score(star_count: int | None, log_scale: int | None = None) -> float:
    """star 对数归一化到 0~1：log1p(1+star)/log_scale，star None（离线/编造禁令）→ 0。"""
    if star_count is None or star_count <= 0:
        return 0.0
    scale = log_scale or settings.REPO_RECOMMEND_STAR_LOG_SCALE or 5
    return min(1.0, math.log1p(float(star_count)) / max(0.1, float(scale)))


def reproducibility_score(repos: list[dict[str, Any]]) -> float:
    """复现性分：存在开源代码得基础分 0.2；在线真实 star 再加星标归一化贡献。"""
    if not repos:
        return 0.0
    base = 0.2
    best_star = 0.0
    online = False
    for r in repos:
        if r.get("source") == "online" and r.get("star_count") is not None:
            online = True
            best_star = max(best_star, star_score(r["star_count"]))
        if r.get("source") == "online":
            online = True
    return base + (0.8 * best_star if online else 0.0)


def feedback_score_of(net: int | float | None) -> float:
    """用户反馈净分（like−dislike）平滑到 0~1：0.5*(1+tanh(net/5))。"""
    if net is None:
        return 0.5
    return 0.5 * (1.0 + math.tanh(float(net) / 5.0))


def recommend_ranked(
    local_references: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    feedback: dict[str, int] | None = None,
    weights: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """复现性优先推荐排序。

    - 仓库抽取 + 在线元数据抓取（见 repo_availability_service.enrich_candidates）；
    - 相关性：候选与本地文献库的 Jaccard；
    - feedback: {owner/repo: net} 跨用户净分，按候选内仓库取反馈最多的那个计算。

    返回按 total 降序的候选结果，含子分与可解释 reason。
    """
    feedback = feedback or {}
    w = {
        "corr": (weights or {}).get("corr", settings.REPO_RECOMMEND_CORR_WEIGHT),
        "repro": (weights or {}).get("repro", settings.REPO_RECOMMEND_REPRO_WEIGHT),
        "fb": (weights or {}).get("fb", settings.REPO_RECOMMEND_FEEDBACK_WEIGHT),
    }
    local_text = " ".join(
        f"{r.get('title') or ''} {r.get('journal') or ''}" for r in local_references or []
    )
    enriched = _core().enrich_candidates(candidates or [])
    results: list[dict[str, Any]] = []
    for c in enriched:
        cand_text = " ".join(
            f"{c.get('title') or ''} {c.get('summary') or ''} {' '.join(c.get('authors') or [])}"
        )
        corr = _jaccard(local_text, cand_text)
        repro = reproducibility_score(c.get("repos") or [])
        net = max((feedback.get(r.get("repo"), 0) for r in (c.get("repos") or [])), default=0)
        fb = feedback_score_of(net)
        total = w["corr"] * corr + w["repro"] * repro + w["fb"] * fb
        has_repo = bool(c.get("repos"))
        reason_parts = ["与本地文献库主题相关"]
        if has_repo:
            reason_parts.append("含开源实现，在线可获得真实 star/许可证")
        else:
            reason_parts.append("未检出开源仓库")
        results.append(
            {
                "title": c.get("title"),
                "source": c.get("source"),
                "arxiv_id": c.get("arxiv_id"),
                "open_source": has_repo,
                "repos": c.get("repos"),
                "correlation_score": round(corr, 4),
                "reproducibility_score": round(repro, 4),
                "feedback_score": round(fb, 4),
                "feedback_net": net,
                "total_score": round(total, 4),
                "reason": "；".join(reason_parts),
            }
        )
    results.sort(key=lambda x: x["total_score"], reverse=True)
    return results


# ── 异步 DAO（持久化 read/write） ──────────────────────────────────────


async def persist_record(db: AsyncSession, data: dict[str, Any]) -> dict[str, Any]:
    """写一条推荐记录快照，返回记录 dict。"""
    record = RecommendRecord(
        user_id=data["user_id"],
        title=str(data.get("title") or "")[:512],
        correlation_score=int(round((data.get("correlation_score") or 0) * 100)),
        reproducibility_score=int(round((data.get("reproducibility_score") or 0) * 100)),
        feedback_score=int(round((data.get("feedback_score") or 0) * 100)),
        total_score=int(round((data.get("total_score") or 0) * 100)),
        repos=data.get("repos") or [],
        reason=str(data.get("reason") or "")[:1000],
        backend=data.get("backend") or "builtin",
    )
    db.add(record)
    await db.flush()
    # created_at 为 server_default，MySQL 无 RETURNING 回填；flush 后须 refresh 才会在
    # Python 侧有值，否则 row_to_dict 访问 created_at 触发懒加载 SELECT → MissingGreenlet。
    await db.refresh(record)
    return {"id": record.id, **row_to_dict(record)}


async def upsert_feedback(
    db: AsyncSession,
    user_id: str,
    repo: str,
    sentiment: str,
    record_id: str | None = None,
    comment: str | None = None,
) -> dict[str, Any]:
    """点赞/踩（幂等 upsert）：同 (user_id, repo) 覆盖，刷新情感与记录关联。"""
    if sentiment not in ("like", "dislike"):
        raise ValueError("sentiment must be like|dislike")
    stmt = select(RecommendFeedback).where(
        RecommendFeedback.user_id == user_id, RecommendFeedback.repo == repo
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        row = RecommendFeedback(user_id=user_id, repo=repo)
        db.add(row)
    row.sentiment = sentiment
    row.record_id = record_id or row.record_id
    row.comment = comment or row.comment
    await db.flush()
    return {
        "id": row.id,
        "user_id": row.user_id,
        "repo": row.repo,
        "sentiment": sentiment,
    }


async def list_records(db: AsyncSession, limit: int = 100) -> list[dict[str, Any]]:
    rows = (
        (
            await db.execute(
                select(RecommendRecord).order_by(RecommendRecord.created_at.desc()).limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [row_to_dict(r) for r in rows]


async def list_feedback(db: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        (await db.execute(select(RecommendFeedback).order_by(RecommendFeedback.created_at.desc())))
        .scalars()
        .all()
    )
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "record_id": r.record_id,
            "repo": r.repo,
            "sentiment": r.sentiment,
            "comment": r.comment,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


async def aggregate_repo_feedback(db: AsyncSession) -> dict[str, int]:
    """跨用户聚合每个仓库的净反馈（like−dislike），供推荐排序复用（多用户推荐扩展位）。"""
    rows = (await db.execute(select(RecommendFeedback.repo, RecommendFeedback.sentiment))).all()
    net: dict[str, int] = {}
    for repo, sentiment in rows:
        net[repo] = net.get(repo, 0) + (1 if sentiment == "like" else -1)
    return net


async def clear_feedback(db: AsyncSession) -> int:
    """清空反馈（仅供测试/演示）。返回删除条数。"""
    result = await db.execute(delete(RecommendFeedback))
    return result.rowcount or 0


def row_to_dict(r: RecommendRecord) -> dict[str, Any]:
    return {
        "id": r.id,
        "user_id": r.user_id,
        "title": r.title,
        "correlation_score": r.correlation_score / 100,
        "reproducibility_score": r.reproducibility_score / 100,
        "feedback_score": r.feedback_score / 100,
        "total_score": r.total_score / 100,
        "repos": r.repos,
        "reason": r.reason,
        "backend": r.backend,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


class RepoRecommendService:
    """步骤 21 复现性优先推荐排序服务（纯函数 + DAO 的极薄封装）。"""

    # ─── 插件协议 ──────────────────────────────────────────────────────────
    async def on_start(self) -> None:
        logger.info("repo_recommend plugin started")

    async def on_stop(self) -> None:
        logger.info("repo_recommend plugin stopped")

    def health(self):
        return {"backend": "repo_recommend", "available": self.available}

    @property
    def available(self) -> bool:
        return settings.REPO_RECOMMEND_ENABLED

    def star(self, star_count: int | None, log_scale: int | None = None) -> float:
        return star_score(star_count, log_scale)

    def reproducibility(self, repos: list[dict[str, Any]]) -> float:
        return reproducibility_score(repos)

    def feedback(self, net: int | float | None) -> float:
        return feedback_score_of(net)

    def recommend(
        self,
        local_references: list[dict[str, Any]],
        candidates: list[dict[str, Any]],
        feedback: dict[str, int] | None = None,
        weights: dict[str, float] | None = None,
    ) -> list[dict[str, Any]]:
        return recommend_ranked(local_references, candidates, feedback, weights)


# 全局单例
repo_recommend_service = RepoRecommendService()


class RepoRecommendPlugin(Plugin):
    """官方插件：repo_recommend —— GitHub 开源复现性优先推荐排序服务（存量迁移自 app/services/repo_recommend_service.py）。

    - 配置沿用全局 settings（`REPO_RECOMMEND_*` 键）。
    - 纯排序函数 + 异步 DAO，无重型运行时资源；`create()` 返回全新实例供 registry 寻址，
      模块级单例 `repo_recommend_service` 供门面再导出。
    - 消费者动态寻址：`registry.get("repo_recommend")`。
    """

    name = "repo_recommend"
    version = "1.0.0"
    config_prefix = ""
    requires: list[str] = []
    type = "service"
    legacy_module = "app.services.repo_recommend_service"

    def create(self, registry, settings) -> RepoRecommendService:
        return RepoRecommendService()


plugin = RepoRecommendPlugin()
