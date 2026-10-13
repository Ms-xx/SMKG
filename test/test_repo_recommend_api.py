# -*- coding: utf-8 -*-
"""步骤 21 API 测试：/repo-recommend/* 推荐、点赞/踩、记录列表、在线探测、权限 403。"""
import pytest
from unittest.mock import patch

pytestmark = pytest.mark.asyncio

CANDIDATES_OPEN = [
    {
        "title": "attention is all you need transformer model",
        "summary": "github.com/hf/transformers",
        "authors": ["a"],
        "source": "arxiv",
        "arxiv_id": "1706.03762",
    }
]
CANDIDATES_CLOSED = [{"title": "unrelated chemistry", "summary": "", "authors": []}]


def _patch_enrich():
    old = "app.services.repo_recommend_service.enrich_candidates"

    def side(cands, extra=None):
        out = []
        for c in cands:
            if "github.com" in (c.get("summary") or ""):
                out.append(
                    {
                        **c,
                        "repos": [
                            {
                                "repo": "hf/transformers",
                                "source": "online",
                                "star_count": 167000,
                                "license": "Apache-2.0",
                            }
                        ],
                    }
                )
            else:
                out.append({**c, "repos": []})
        return out

    return patch(old, side_effect=side)


async def test_recommend_returns_ranked_and_persists(client):
    with _patch_enrich():
        resp = await client.post(
            "/api/v1/repo-recommend/recommend",
            json={
                "local_references": [{"title": "transformer attention model"}],
                "candidates": CANDIDATES_OPEN + CANDIDATES_CLOSED,
            },
            headers=_auth(),
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    assert body["github_online"] is True  # 已抓取在线元数据
    assert body["recommendations"][0]["open_source"] is True
    assert body["recommendations"][0]["reason"]
    assert body["recommendations"][0]["repos"][0]["star_count"] == 167000
    # 已持久化
    recs = await client.get("/api/v1/repo-recommend/records", headers=_auth())
    assert recs.status_code == 200
    assert recs.json()["count"] >= 1


async def test_recommend_permission_403(client):
    with _patch_enrich():
        resp = await client.post(
            "/api/v1/repo-recommend/recommend",
            json={"local_references": [], "candidates": []},
            headers=_auth(role="viewer_unauthorized"),
        )
    assert resp.status_code == 403


async def test_feedback_upsert_and_list(client):
    with _patch_enrich():
        await client.post(
            "/api/v1/repo-recommend/recommend",
            json={"local_references": [], "candidates": CANDIDATES_OPEN},
            headers=_auth(),
        )
    resp = await client.post(
        "/api/v1/repo-recommend/feedback",
        json={"repo": "hf/transformers", "sentiment": "like", "comment": "好复现"},
        headers=_auth(),
    )
    assert resp.status_code == 200
    # 幂等覆盖为 dislike
    resp2 = await client.post(
        "/api/v1/repo-recommend/feedback",
        json={"repo": "hf/transformers", "sentiment": "dislike"},
        headers=_auth(),
    )
    assert resp2.status_code == 200
    lst = await client.get("/api/v1/repo-recommend/feedback", headers=_auth())
    rows = [f for f in lst.json()["items"] if f["repo"] == "hf/transformers"]
    assert len(rows) == 1 and rows[0]["sentiment"] == "dislike"  # 覆盖非重复


async def test_feedback_write_permission_403(client):
    resp = await client.post(
        "/api/v1/repo-recommend/feedback",
        json={"repo": "a/b", "sentiment": "like"},
        headers=_auth(role="viewer_unauthorized"),
    )
    assert resp.status_code == 403


async def test_feedback_invalid_sentiment_422(client):
    resp = await client.post(
        "/api/v1/repo-recommend/feedback",
        json={"repo": "a/b", "sentiment": "meh"},
        headers=_auth(),
    )
    assert resp.status_code == 422


async def test_online_probe_mocked(client, monkeypatch):
    from app.api.v1 import repo_recommend as api_mod

    monkeypatch.setattr(api_mod, "check_github_online", lambda: True)
    resp = await client.get("/api/v1/repo-recommend/online", headers=_auth())
    assert resp.status_code == 200
    assert resp.json()["github_online"] is True


def _auth(user_id: str = "u1", role: str = "admin"):
    from app.core.security import create_access_token

    return {
        "Authorization": f"Bearer {create_access_token({'sub': user_id, 'role': role})}"
    }
