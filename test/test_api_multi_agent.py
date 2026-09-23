# -*- coding: utf-8 -*-
"""多 Agent 协作与冲突解决（步骤 9）HTTP 集成测试。"""
import pytest

from conftest import API_PREFIX

MA = f"{API_PREFIX}/multi-agent"


@pytest.mark.asyncio
async def test_multi_agent_requires_auth(client):
    assert (await client.get(f"{MA}/agents")).status_code == 401


@pytest.mark.asyncio
async def test_multi_agent_full_flow(client, token):
    headers = token("u1", "admin")

    # 智能体列表
    r = await client.get(f"{MA}/agents", headers=headers)
    assert r.status_code == 200
    body = r.json()
    names = {a["name"] for a in body["agents"]}
    assert names == {"parse", "extract", "qa", "summarize"}

    # 任务编排
    r = await client.post(
        f"{MA}/run",
        json={"query": "钙钛矿有哪些性能特点？", "context": "钙钛矿太阳能电池具有高效率。", "mode": "merge"},
        headers=headers,
    )
    assert r.status_code == 200
    session = r.json()
    assert session["session_id"].startswith("ma-")
    assert len(session["agent_results"]) == 4
    assert "final_text" in session["resolution"]

    # 会话查询
    r = await client.get(f"{MA}/sessions/{session['session_id']}", headers=headers)
    assert r.status_code == 200
    assert r.json()["query"] == "钙钛矿有哪些性能特点？"

    # 独立冲突解决
    r = await client.post(
        f"{MA}/resolve",
        json={
            "proposals": [
                {"agent": "a1", "content": "X", "confidence": 0.9},
                {"agent": "a2", "content": "Y", "confidence": 0.7},
            ],
            "mode": "vote",
        },
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["conflicts"][0]["type"] == "answer"