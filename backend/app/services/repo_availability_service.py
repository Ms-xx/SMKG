# -*- coding: utf-8 -*-
"""
仓库可用性 / 复现性元数据服务门面（插件化架构迁移：实现已迁至 `app/plugins/repo_availability/service.py`）。

- 兼容再导出：既有 `from app.services.repo_availability_service import extract_repo_links /
  fetch_repo_metadata / parse_repo_link / RepoAvailabilityService / repo_availability_service`
  不受影响。
- 测试经本门面 `import urllib.request` 对共享 stdlib `urllib.request.urlopen` 打补丁，
  插件实现使用同一 stdlib 模块对象，补丁全局生效。
"""

from __future__ import annotations

import urllib.request  # noqa: F401  # 供测试 patch app.services.repo_availability_service.urllib.request.urlopen

from app.plugins.repo_availability.service import (
    RepoAvailabilityService,
    check_github_online,
    enrich_candidates,
    extract_repo_links,
    fetch_repo_metadata,
    json_loads,
    parse_repo_link,
    repo_availability_service,
)

__all__ = [
    "RepoAvailabilityService",
    "repo_availability_service",
    "extract_repo_links",
    "parse_repo_link",
    "fetch_repo_metadata",
    "json_loads",
    "check_github_online",
    "enrich_candidates",
]
