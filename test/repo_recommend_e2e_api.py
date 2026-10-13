# -*- coding: utf-8 -*-
"""步骤 21 端到端真实 API 实测（走 HTTP，非服务直调）。

流程：登录拿 token → POST /repo-recommend/recommend（真实 api.github.com 抓取）→
POST /repo-recommend/feedback（点赞持久化）→ GET /records → GET /online。
产物：outputs/repo_recommend_e2e_api.json。
运行：SciMKG python test/repo_recommend_e2e_api.py（需后端已启动在 127.0.0.1:8000）
"""
import json
import os
import sys

import requests

BASE = "http://127.0.0.1:8000/api/v1"
OUT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__), "..", "outputs", "repo_recommend_e2e_api.json"
    )
)

CANDIDATES = [
    {
        "title": "Attention Is All You Need",
        "summary": "Transformer architecture, implementation at github.com/huggingface/transformers.",
        "authors": ["Vaswani"],
        "source": "arxiv",
        "arxiv_id": "1706.03762",
    },
    {
        "title": "Deep Residual Learning",
        "summary": "ResNet, code at https://github.com/KaimingHe/deep-residual-networks.",
        "authors": ["He"],
        "source": "arxiv",
    },
    {
        "title": "An Unrelated Chemistry Note",
        "summary": "No code repository mentioned here.",
        "authors": ["X"],
        "source": "arxiv",
    },
]


def main() -> int:
    report = {"step": 21, "mode": "e2e-http"}

    # 1) 登录拿 token
    r = requests.post(
        f"{BASE}/auth/login",
        json={"username": "admin", "password": "admin123"},
        timeout=15,
    )
    report["login"] = {"status": r.status_code}
    if r.status_code != 200:
        report["error"] = r.text
        print("login failed:", r.status_code, r.text)
        return 1
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    report["login"]["ok"] = True

    # 2) /repo-recommend/recommend
    rr = requests.post(
        f"{BASE}/repo-recommend/recommend",
        headers=headers,
        json={
            "local_references": [{"title": "transformer attention encoder-decoder"}],
            "candidates": CANDIDATES,
        },
        timeout=40,
    )
    report["recommend"] = {
        "status": rr.status_code,
        "backend": rr.json().get("backend"),
        "github_online": rr.json().get("github_online"),
        "count": rr.json().get("count"),
        "open_source_first": (
            (rr.json().get("recommendations") or [{}])[0].get("title"),
            (rr.json().get("recommendations") or [{}])[0].get("open_source"),
        ),
        "n_recommendations": len(rr.json().get("recommendations") or []),
    }
    print(
        "recommend:",
        rr.status_code,
        "online:",
        rr.json().get("github_online"),
        "first:",
        report["recommend"]["open_source_first"],
    )
    if rr.status_code != 200:
        report["error"] = rr.text
        print("recommend failed:", rr.text)
        return 1
    reco = rr.json()

    # 3) /repo-recommend/feedback（点赞持久化）
    first_repo = (reco.get("recommendations") or [{}])[0].get("repos") or [{}]
    target = (
        first_repo[0].get("repo") if first_repo else None
    ) or "huggingface/transformers"
    fb = requests.post(
        f"{BASE}/repo-recommend/feedback",
        headers=headers,
        json={"repo": target, "sentiment": "like"},
        timeout=15,
    )
    report["feedback"] = {
        "status": fb.status_code,
        "sent": fb.json() if fb.status_code == 200 else fb.text,
    }
    print("feedback:", fb.status_code, fb.text[:120])

    # 4) GET /records
    rec = requests.get(
        f"{BASE}/repo-recommend/records",
        headers=headers,
        params={"limit": 50},
        timeout=15,
    )
    report["records"] = {
        "status": rec.status_code,
        "total": rec.json().get("total") if rec.status_code == 200 else None,
        "n": len(rec.json().get("items") or []) if rec.status_code == 200 else None,
    }
    print("records:", rec.status_code, "total:", report["records"]["total"])

    # 5) GET /online
    on = requests.get(f"{BASE}/repo-recommend/online", headers=headers, timeout=15)
    report["online"] = {
        "status": on.status_code,
        "github_online": on.json() if on.status_code == 200 else None,
    }
    print("online:", on.status_code, on.text[:80])

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    ok = (
        report["recommend"]["status"] == 200
        and report["recommend"]["github_online"] is True
        and report["recommend"]["open_source_first"][1] is True
        and report["feedback"]["status"] == 200
        and report["records"]["status"] == 200
    )
    report["e2e_ok"] = ok
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("e2e_ok:", ok, "wrote", OUT)
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        print("e2e error:", e)
        sys.exit(1)
