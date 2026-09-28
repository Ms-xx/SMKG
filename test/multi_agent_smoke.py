# -*- coding: utf-8 -*-
"""
多 Agent 协作 HTTP 冒烟测试（步骤 9）：智能体列表 / 任务编排 / 三种冲突解决 / 会话查询。
对运行中的后端(8000)发起真实请求，结果写入 outputs/multi_agent.json。

用法:
  D:\\workapp\\Anaconda\\anaconda3\\envs\\SciMKG\\python.exe test\\multi_agent_smoke.py
"""

import argparse
import json
import os
import sys
from datetime import datetime

import requests


def login(base, username, password):
    r = requests.post(
        f"{base}/auth/login",
        json={"username": username, "password": password},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("access_token")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8000/api/v1")
    parser.add_argument("--out", default=None)
    parser.add_argument("--user", default="admin")
    parser.add_argument("--password", default="admin123")
    args = parser.parse_args()

    out = args.out or os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "outputs", "multi_agent.json")
    )
    os.makedirs(os.path.dirname(out), exist_ok=True)
    base = args.base.rstrip("/")

    summary = {"started_at": datetime.now().isoformat(), "base": base, "checks": []}
    S = requests.Session()
    S.headers["Authorization"] = f"Bearer {login(base, args.user, args.password)}"
    print("登录成功")

    def post(path, body):
        r = S.post(f"{base}{path}", json=body, timeout=60)
        return r.status_code, (
            r.json()
            if r.headers.get("content-type", "").startswith("application/json")
            else r.text
        )

    def get(path):
        r = S.get(f"{base}{path}", timeout=30)
        return r.status_code, (
            r.json()
            if r.headers.get("content-type", "").startswith("application/json")
            else r.text
        )

    # 1 智能体列表
    print("=" * 64)
    print("1) GET /multi-agent/agents")
    sc, body = get("/multi-agent/agents")
    summary["checks"].append({"name": "list_agents", "http": sc})
    print(
        f"   HTTP={sc} agents={[a['name'] for a in body.get('agents', [])]}  modes={body.get('modes')}"
    )
    assert sc == 200 and len(body.get("agents", [])) == 4

    # 2 任务编排（merge）
    print("2) POST /multi-agent/run  mode=merge (含中文材料上下文)")
    query = "钙钛矿有哪些性能特点？"
    ctx = "钙钛矿太阳能电池具有高效率、稳定性好，采用新制备方法改善性能，与石墨烯相关。"
    for mode, label in (
        ("merge", "merge"),
        ("vote", "vote"),
        ("arbitrate", "arbitrate"),
    ):
        sc, sess = post(
            "/multi-agent/run", {"query": query, "context": ctx, "mode": mode}
        )
        summary["checks"].append(
            {
                "name": f"run_{mode}",
                "http": sc,
                "session_id": sess.get("session_id"),
                "backend": sess.get("backend"),
                "backends_used": sorted(
                    {ar.get("backend") for ar in sess.get("agent_results", [])}
                ),
            }
        )
        print(
            f"   HTTP={sc} session={sess.get('session_id')} backend={sess.get('backend')} "
            f"agent_backends={sorted({ar.get('backend') for ar in sess.get('agent_results', [])})}"
        )
        print(
            f"   final_text={str(sess.get('resolution', {}).get('final_text'))[:120]!r}"
        )
        print(
            f"   conflicts={len(sess.get('conflicts', []))} unresolved={sess.get('resolution', {}).get('unresolved')}"
        )
        # 校验冲突解决字段齐全
        assert sc == 200 and sess.get("session_id", "").startswith("ma-")
        last_session_id = sess["session_id"]

    # 3 独立冲突解决（构造多个 Agent 产出）
    print("3) POST /multi-agent/resolve  (vote / merge / arbitrate)")
    proposals = [
        {"agent": "agent-a", "content": "高效率", "confidence": 0.9},
        {"agent": "agent-b", "content": "高效率", "confidence": 0.8},
        {"agent": "agent-c", "content": "低成本", "confidence": 0.7},
        {
            "agent": "agent-d",
            "items": [
                {"text": "钙钛矿", "type": "Material", "confidence": 0.9},
                {"text": "石墨烯", "type": "Method", "confidence": 0.7},
            ],
        },
    ]
    for mode in ("vote", "merge", "arbitrate"):
        sc, res = post("/multi-agent/resolve", {"proposals": proposals, "mode": mode})
        summary["checks"].append(
            {
                "name": f"resolve_{mode}",
                "http": sc,
                "final_text": res.get("final_text"),
                "final_items": res.get("final_items"),
                "conflicts": len(res.get("conflicts", [])),
                "mode": res.get("mode"),
            }
        )
        print(
            f"   mode={mode} HTTP={sc} final_text={res.get('final_text')!r} "
            f"final_items={res.get('final_items')} conflicts={len(res.get('conflicts', []))}"
        )
        assert sc == 200

    # 4 会话列表
    print("4) GET /multi-agent/sessions")
    sc, sres = get("/multi-agent/sessions")
    summary["checks"].append(
        {"name": "list_sessions", "http": sc, "count": len(sres.get("items", []))}
    )
    print(f"   HTTP={sc} 会话数={len(sres.get('items', []))}")
    assert sc == 200 and len(sres.get("items", [])) >= 3

    # 5 单会话查询
    print("5) GET /multi-agent/sessions/{last}")
    sc, one = get(f"/multi-agent/sessions/{last_session_id}")
    summary["checks"].append(
        {
            "name": "get_session",
            "http": sc,
            "session_id": last_session_id,
            "query": one.get("query"),
        }
    )
    print(f"   HTTP={sc} query={one.get('query')!r} agents={one.get('agents')}")
    assert sc == 200 and one.get("session_id") == last_session_id

    summary["finished_at"] = datetime.now().isoformat()
    ok = all(c.get("http") == 200 for c in summary["checks"])
    summary["ok"] = ok
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("=" * 64)
    print(f"结果写入: {out}  全部通过: {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
