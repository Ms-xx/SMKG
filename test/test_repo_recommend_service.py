# -*- coding: utf-8 -*-
"""步骤 21 单测：仓库链接抽取、元数据抓取降级（在线/离线）、复现性/反馈打分、排序、DAO 持久化。"""
from unittest.mock import patch

import pytest

from app.services import repo_recommend_service as rrs
from app.services.repo_availability_service import (
    extract_repo_links,
    fetch_repo_metadata,
    parse_repo_link,
)

pytestmark = pytest.mark.asyncio


# ── 仓库链接抽取 / 解析 ────────────────────────────────────────────────
def test_extract_repo_links_dedup_and_parse():
    text = (
        "Code at https://github.com/huggingface/transformers and "
        "http://github.com/huggingface/transformers/tree/v4.0 and "
        "https://gitlab.com/group/proj"
    )
    links = extract_repo_links(text)
    # huggingface/transformers 去重后只出现一次
    assert links.count("github.com:huggingface/transformers") == 1
    assert "gitlab.com:group/proj" in links
    assert parse_repo_link("github.com:huggingface/transformers") == (
        "huggingface",
        "transformers",
    )
    assert parse_repo_link("bad_repo_id") is None


def test_extract_repo_links_extra_patterns():
    text = "internal at http://git.internal/x/y"
    links = extract_repo_links(text, extra_patterns=["http://git.internal"])
    assert links == ["custom:x/y"]


# ── 在线元数据抓取：降级不编造 ─────────────────────────────────────────
@patch(
    "app.services.repo_availability_service.urllib.request.urlopen",
    side_effect=TimeoutError("timeout"),
)
def test_fetch_repo_metadata_offline_no_fabrication(mock_open):
    meta = fetch_repo_metadata("github.com:facebook/pytorch")
    assert meta["source"] == "offline"
    assert meta["star_count"] is None  # 严禁编造
    assert meta["license"] is None
    assert "error" in meta


@patch("app.services.repo_availability_service.urllib.request.Request")
def test_fetch_repo_metadata_online(mock_req):
    import json as _json

    payload = {
        "html_url": "https://github.com/hf/tr",
        "stargazers_count": 999,
        "license": {"spdx_id": "Apache-2.0", "name": "Apache-2.0"},
        "pushed_at": "2026-01-01T00:00:00Z",
        "open_issues_count": 7,
        "updated_at": "2026-01-02T00:00:00Z",
    }

    class FakeResp:
        def read(self):
            return _json.dumps(payload).encode()

    class FakeCtx:
        def __enter__(self):
            return FakeResp()

        def __exit__(self, *a):
            return False

    with patch(
        "app.services.repo_availability_service.urllib.request.urlopen",
        return_value=FakeCtx(),
    ):
        meta = fetch_repo_metadata("github.com:hf/tr", timeout=2)
    assert meta["source"] == "online"
    assert meta["star_count"] == 999
    assert meta["license"] == "Apache-2.0"


# ── 打分函数 ───────────────────────────────────────────────────────────
def test_star_score_log_scale_and_none():
    assert rrs.star_score(None, log_scale=5) == 0.0
    assert rrs.star_score(0, log_scale=5) == 0.0
    assert rrs.star_score(100000, log_scale=5) <= 1.0
    assert rrs.star_score(10, log_scale=5) > 0.0


def test_reproducibility_online_vs_offline():
    online = [{"source": "online", "star_count": 100000}]
    offline = [{"source": "offline", "star_count": None}]
    none_repo = []
    # 在线有真实 star 的复现性分最大；离线仅有基础分 0.2；无仓库为 0
    assert rrs.reproducibility_score(online) > rrs.reproducibility_score(offline)
    assert rrs.reproducibility_score(offline) == 0.2
    assert rrs.reproducibility_score(none_repo) == 0.0


def test_feedback_score_smooth():
    assert 0.0 < rrs.feedback_score_of(None) < 1.0
    assert rrs.feedback_score_of(10) > rrs.feedback_score_of(-10)


# ── 排序：复现性优先 ────────────────────────────────────────────────────
@patch(
    "app.services.repo_recommend_service.enrich_candidates",
    side_effect=lambda cands, extra=None: [
        (
            {
                **c,
                "repos": [
                    {"repo": "os/repo", "source": "online", "star_count": 200000}
                ],
            }
            if i == 0
            else {**c, "repos": []}
        )
        for i, c in enumerate(cands)
    ],
)
def test_recommend_open_source_ranks_higher(mock_enrich):
    refs = [{"title": "transformer attention model"}]
    cands = [
        {
            "title": "attention is all you need transformer model",
            "summary": "",
            "authors": [],
        },
        {"title": "unrelated chemistry paper", "summary": "", "authors": []},
    ]
    ranked = rrs.recommend_ranked(refs, cands)
    assert ranked[0]["title"].startswith("attention")
    assert ranked[0]["open_source"] is True
    # 无关候选因无开源仓库且低相关，复现性分为 0
    assert ranked[1]["open_source"] is False
    assert ranked[1]["reproducibility_score"] == 0.0
    assert all("reason" in r for r in ranked)


# ── DAO 持久化 + 反馈聚合 ───────────────────────────────────────────────
async def test_persist_and_feedback_upsert_and_aggregate(db):
    rec = await rrs.persist_record(
        db,
        {
            "user_id": "u1",
            "title": "paper x",
            "correlation_score": 0.5,
            "reproducibility_score": 0.8,
            "feedback_score": 0.5,
            "total_score": 1.3,
            "repos": [{"repo": "os/repo"}],
            "reason": "相关且含开源",
            "backend": "builtin",
        },
    )
    assert rec["id"]
    rows = await rrs.list_records(db)
    assert any(r["id"] == rec["id"] for r in rows)

    await rrs.upsert_feedback(db, "u1", "os/repo", "like", record_id=rec["id"])
    # 幂等：同 (user_id, repo) 覆盖为 dislike
    await rrs.upsert_feedback(db, "u1", "os/repo", "dislike", record_id=rec["id"])
    await rrs.upsert_feedback(db, "u2", "os/repo", "like")
    net = await rrs.aggregate_repo_feedback(db)
    today_dislike = net.get("os/repo")
    # u1 覆盖为 dislike(-1) + u2 like(+1) = 0
    assert today_dislike == 0

    flist = await rrs.list_feedback(db)
    assert len(flist) >= 2
    assert all(f["sentiment"] in ("like", "dislike") for f in flist)
