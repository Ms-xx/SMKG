# -*- coding: utf-8 -*-
"""
GitHub 开源复现性优先推荐排序服务门面（插件化架构迁移：实现已迁至 `app/plugins/repo_recommend/service.py`）。

- 兼容再导出：既有 `from app.services.repo_recommend_service import star_score /
  reproducibility_score / persistence DAO` 不受影响。
- 测试经本门面对 `enrich_candidates` 打补丁，插件实现 `recommend_ranked` 运行期经 `_core()`
  动态寻址门面读取补丁，保证打补丁生效。
"""

from __future__ import annotations

from app.plugins.repo_recommend.service import (
    RepoRecommendService,
    aggregate_repo_feedback,
    clear_feedback,
    enrich_candidates,
    feedback_score_of,
    list_feedback,
    list_records,
    persist_record,
    recommend_ranked,
    repo_recommend_service,
    reproducibility_score,
    row_to_dict,
    star_score,
    upsert_feedback,
)

__all__ = [
    "RepoRecommendService",
    "repo_recommend_service",
    "star_score",
    "reproducibility_score",
    "feedback_score_of",
    "recommend_ranked",
    "persist_record",
    "upsert_feedback",
    "list_records",
    "list_feedback",
    "aggregate_repo_feedback",
    "clear_feedback",
    "row_to_dict",
    "enrich_candidates",
]
