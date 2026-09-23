# -*- coding: utf-8 -*-
"""A/B 测试框架 HTTP 集成测试（步骤 8）。"""
import pytest

from conftest import API_PREFIX

AB = f"{API_PREFIX}/ab-test"


async def _create(client, headers, name="ab-api-exp"):
    r = await client.post(
        f"{AB}/experiments",
        json={"name": name, "variants": ["control", "treatment"], "metric_type": "binary"},
        headers=headers,
    )
    assert r.status_code == 200
    return r.json()


@pytest.mark.asyncio
async def test_ab_test_full_flow(client, token):
    headers = token("u1", "admin")

    # 创建实验
    exp = await _create(client, headers)
    exp_id = exp["id"]
    assert exp["variants"] == ["control", "treatment"]

    # 列表
    r = await client.get(f"{AB}/experiments", headers=headers)
    assert r.status_code == 200

    # 查询单个
    r = await client.get(f"{AB}/experiments/{exp_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["name"] == "ab-api-exp"

    # 流量分流
    r = await client.post(
        f"{AB}/assign", json={"experiment_id": exp_id, "subject_id": "u1"}, headers=headers
    )
    assert r.status_code == 200
    assert r.json()["variant"] in ("control", "treatment")

    # 指标采集（control 40% 成功，treatment 80% 成功，各 50 次）
    for i in range(50):
        assert (
            await client.post(
                f"{AB}/record",
                json={"experiment_id": exp_id, "variant": "control", "value": 1 if i < 20 else 0},
                headers=headers,
            )
        ).status_code == 200
        assert (
            await client.post(
                f"{AB}/record",
                json={"experiment_id": exp_id, "variant": "treatment", "value": 1 if i < 40 else 0},
                headers=headers,
            )
        ).status_code == 200

    # 统计显著性判定与结论
    r = await client.post(f"{AB}/evaluate", json={"experiment_id": exp_id}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["significant"] is True
    assert body["winner"] == "treatment"
    assert "conclusion" in body and body["p_value"] < 0.05


@pytest.mark.asyncio
async def test_ab_test_requires_auth(client, token):
    headers = token("u1", "admin")
    exp = await _create(client, headers)
    # 未带 token 拒绝访问
    r = await client.post(f"{AB}/assign", json={"experiment_id": exp["id"], "subject_id": "x"})
    assert r.status_code == 401
