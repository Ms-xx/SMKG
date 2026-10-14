# -*- coding: utf-8 -*-
"""
步骤 21：GitHub 开源复现性优先推荐（模块四）

职责：
1. 从论文正文/脚注/摘要中抽取开源仓库链接（`github.com/{owner}/{repo}` 等），作为
   「可复现」的一级信号——离线亦可用，不依赖外部网络；
2. 在线抓取真实仓库元数据（star / license / 最近推送 / open issues / updated_at），
   用于复现性加权与推荐理由；
3. 网络不可达时显式降级标注 `source: "offline"`，**严禁编造 star 数**（offline 时
   star/license 等一律为 None，不填猜测值）。

关键约束（本机实测）：
- `api.github.com`（REST API）可达并返回真实元数据；
- `github.com` 网页 / `raw.githubusercontent.com` 本机超时。
  因此在线抓取以 `GITHUB_API_ENDPOINT`（默认 api.github.com）为准，网页不可达不影响抓取。
"""
from __future__ import annotations

import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from app.core.config import settings
from app.core.plugin.base import Plugin

# 仓库链接（scheme 与 `//` 均可选，兼容裸 `github.com/owner/repo` / 带子路径 /·前缀 www）
_REPO_URL_RE = re.compile(
    r"(?:https?:)?(?://)?(?:www\.)?(?P<host>github\.com|gitlab\.[a-z0-9.-]+|bitbucket\.org)"
    r"/(?P<owner>[A-Za-z0-9_.\-]+)/(?P<repo>[A-Za-z0-9_.\-]+)",
    re.IGNORECASE,
)


def extract_repo_links(text: str, extra_patterns: list[str] | None = None) -> list[str]:
    """从文本中抽取仓库标识（owner/repo），可按 `owner/repo` 排序去重保留首次出现。

    返回去重后的 `host:owner/repo` 字符串列表（host 便于后续路由到对应 API）。
    `extra_patterns` 为额外可控前缀（settings.GITHUB_REPO_LINK_PATTERNS 等），
    命中的非标准仓库前缀也按 `{prefix}:{owner}/{repo}` 收录。
    """
    found: list[tuple[str, str, str]] = []  # (host, owner, repo) 保持出现顺序
    seen: set[tuple[str, str]] = set()
    for m in _REPO_URL_RE.finditer(str(text or "")):
        host = (m.group("host") or "").lower()
        owner = m.group("owner")
        repo = m.group("repo").rstrip(".")
        key = (host, f"{owner}/{repo}")
        if key in seen:
            continue
        seen.add(key)
        found.append((host, owner, repo))
    # 额外可控前缀
    for pat in extra_patterns or []:
        prefix = str(pat).rstrip("/")
        rx = re.compile(
            re.escape(prefix) + r"/(?P<owner>[A-Za-z0-9_.\-]+)/(?P<repo>[A-Za-z0-9_.\-]+)"
        )
        for m in rx.finditer(str(text or "")):
            key = ("custom", f"{m.group('owner')}/{m.group('repo')}")
            if key in seen:
                continue
            seen.add(key)
            found.append(("custom", m.group("owner"), m.group("repo")))
    return [f"{h}:{o}/{r}" for h, o, r in found]


def parse_repo_link(repo_id: str) -> tuple[str, str] | None:
    """`repo_id` 形如 `github.com:owner/repo` 或 `owner/repo` → (owner, repo)；非法返回 None。"""
    raw = str(repo_id or "").strip()
    if ":" in raw:
        raw = raw.split(":", 1)[1]
    raw = raw.rstrip("/")
    parts = raw.split("/")
    if len(parts) != 2:
        return None
    owner, repo = parts[0], parts[1]
    if not re.fullmatch(r"[A-Za-z0-9_.\-]+", owner) or not re.fullmatch(r"[A-Za-z0-9_.\-]+", repo):
        return None
    return owner, repo


def _iso_or_none(s: str | None) -> str | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).isoformat(timespec="seconds")
    except (ValueError, TypeError):
        return None


def _licensed_name(lic: Any) -> str | None:
    if isinstance(lic, dict):
        return lic.get("spdx_id") or lic.get("name")
    return None


def fetch_repo_metadata(repo_id: str, timeout: float | None = None) -> dict[str, Any]:
    """在线抓取单个仓库真实元数据（api.github.com）。

    成功 → 返回带 `source: "online"` 的真实字段（star_count/license/latest_push/…）；
    失败（网络 / 4xx / 解析异常）→ 返回 `source: "offline"` 且星标等真实字段为 None，
    附 error 说明，绝不编造数值。
    """
    parsed = parse_repo_link(repo_id)
    if parsed is None:
        return {
            "repo": str(repo_id),
            "html_url": None,
            "source": "offline",
            "star_count": None,
            "license": None,
            "latest_push": None,
            "open_issues": None,
            "updated_at": None,
            "error": "非法仓库标识",
        }
    owner, repo = parsed
    endpoint = (settings.GITHUB_API_ENDPOINT or "https://api.github.com").rstrip("/")
    url = f"{endpoint}/repos/{owner}/{repo}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "sdp/backend/1.0",
    }
    if settings.GITHUB_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.GITHUB_API_TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout or settings.GITHUB_API_TIMEOUT) as resp:
            data = json_loads(resp.read().decode("utf-8", errors="replace").strip() or "{}")
    except Exception as e:  # noqa: BLE001 - 网络/HTTP/解析失败统一降级
        logger.debug(f"repo metadata offline: {repo_id}: {e}")
        return {
            "repo": f"{owner}/{repo}",
            "html_url": f"https://github.com/{owner}/{repo}",
            "source": "offline",
            "star_count": None,
            "license": None,
            "latest_push": None,
            "open_issues": None,
            "updated_at": None,
            "error": str(e),
        }
    if not isinstance(data, dict):
        return {
            "repo": f"{owner}/{repo}",
            "html_url": f"https://github.com/{owner}/{repo}",
            "source": "offline",
            "star_count": None,
            "license": None,
            "latest_push": None,
            "open_issues": None,
            "updated_at": None,
            "error": "响应非 JSON 对象",
        }
    return {
        "repo": f"{owner}/{repo}",
        "html_url": data.get("html_url") or f"https://github.com/{owner}/{repo}",
        "source": "online",
        "star_count": data.get("stargazers_count"),
        "license": _licensed_name(data.get("license")),
        "latest_push": _iso_or_none(data.get("pushed_at")),
        "open_issues": data.get("open_issues_count"),
        "updated_at": _iso_or_none(data.get("updated_at")),
        "error": None,
    }


def json_loads(s: str) -> Any:
    import json

    try:
        return json.loads(s)
    except (ValueError, TypeError):
        return {}


def check_github_online(timeout: float = 5.0) -> bool:
    """可用性探测：api.github.com 速率端点可达即视为在线（用于评测如实标注）。失败不抛异常。"""
    endpoint = (settings.GITHUB_API_ENDPOINT or "https://api.github.com").rstrip("/")
    try:
        req = urllib.request.Request(
            endpoint + "/rate_limit",
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "sdp/backend/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:  # noqa: BLE001
        return False


def enrich_candidates(
    candidates: list[dict[str, Any]], extra_patterns: list[str] | None = None
) -> list[dict[str, Any]]:
    """批量：为每个候选论文抽取仓库链接并对每个仓库抓取元数据。

    纯函数封装，便于复用；每个候选返回 `{...原字段, repos: [...]}`。
    """
    patterns = list(settings.GITHUB_REPO_LINK_PATTERNS or []) + list(extra_patterns or [])
    enriched: list[dict[str, Any]] = []
    for cand in candidates or []:
        text = " ".join(
            str(cand.get(k) or "") for k in ("title", "summary", "abstract", "text", "comment")
        )
        repo_ids = extract_repo_links(text, patterns)
        repos = [fetch_repo_metadata(rid) for rid in repo_ids]
        item = dict(cand)
        item["repos"] = repos
        enriched.append(item)
    return enriched


class RepoAvailabilityService:
    """步骤 21 仓库可用性 / 复现性元数据服务（在线抓取可降级）。"""

    # ─── 插件协议 ──────────────────────────────────────────────────────────
    async def on_start(self) -> None:
        logger.info("repo_availability plugin started")

    async def on_stop(self) -> None:
        logger.info("repo_availability plugin stopped")

    def health(self):
        return {"backend": "repo_availability", "available": self.available}

    @property
    def available(self) -> bool:
        return settings.REPO_RECOMMEND_ENABLED

    def extract(self, text: str, extra_patterns: list[str] | None = None) -> list[str]:
        return extract_repo_links(text, extra_patterns)

    def metadata(self, repo_id: str) -> dict[str, Any]:
        return fetch_repo_metadata(repo_id)

    def enrich(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return enrich_candidates(candidates)


repo_availability_service = RepoAvailabilityService()


class RepoAvailabilityPlugin(Plugin):
    """官方插件：repo_availability —— 仓库可用性 / 复现性元数据服务（存量迁移自 app/services/repo_availability_service.py）。

    - 配置沿用全局 settings（`GITHUB_*` / `REPO_RECOMMEND_*` 键）。
    - `create()` 返回全新实例供 registry 寻址；模块级单例 `repo_availability_service` 供门面再导出。
    - 消费者动态寻址：`registry.get("repo_availability")`。
    """

    name = "repo_availability"
    version = "1.0.0"
    config_prefix = ""
    requires: list[str] = []
    type = "service"
    legacy_module = "app.services.repo_availability_service"

    def create(self, registry, settings) -> RepoAvailabilityService:
        return RepoAvailabilityService()


plugin = RepoAvailabilityPlugin()
