# -*- coding: utf-8 -*-
"""知识图谱增强 / 主动学习 / 校准漂移 / 版本管理 模块 HTTP 集成测试。

这些模块的 service 均已有单元测试，此处覆盖其 API 路由层（原先 0% 覆盖）。
"""
import pytest

from conftest import API_PREFIX

KG = f"{API_PREFIX}/knowledge-graph"


@pytest.mark.asyncio
async def test_entity_link(client, token):
    headers = token("u1", "user")
    r = await client.post(f"{KG}/entity-link", json={
        "entities": [{"text": "Perovskite", "entity_type": "Material"}],
    }, headers=headers)
    assert r.status_code == 200
    assert r.json()["total"] >= 0

    r = await client.post(f"{KG}/entity-link/single", json={
        "text": "Perovskite", "entity_type": "Material",
    }, headers=headers)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_relation_reason_and_prediction(client, token):
    headers = token("u1", "user")
    triples = [
        {"head": "A", "relation": "use", "tail": "B"},
        {"head": "B", "relation": "use", "tail": "C"},
    ]

    r = await client.post(f"{KG}/reason", json={"triples": triples}, headers=headers)
    assert r.status_code == 200
    assert "inferred" in r.json()

    r = await client.post(f"{KG}/link-prediction", json={
        "head": "A", "relation": "use", "triples": triples, "top_k": 5,
    }, headers=headers)
    assert r.status_code == 200

    r = await client.post(f"{KG}/triple-score", json={
        "head": "A", "relation": "use", "tail": "B", "triples": triples,
    }, headers=headers)
    assert r.status_code == 200
    assert "score" in r.json()


@pytest.mark.asyncio
async def test_semantic_search_and_text_to_cypher(client, token):
    headers = token("u1", "user")

    r = await client.post(f"{KG}/suggest", json={
        "prefix": "ma", "candidates": ["material", "method", "machine"], "limit": 3,
    }, headers=headers)
    assert r.status_code == 200

    r = await client.post(f"{KG}/facet-search", json={
        "query": "perovskite",
        "records": [{"label": "perovskite solar cell"}, {"label": "silicon"}],
        "facet_key": "label",
    }, headers=headers)
    assert r.status_code == 200

    r = await client.post(f"{KG}/text-to-cypher", json={
        "question": "列出所有材料",
        "node_labels": ["Material"],
        "relation_types": [],
        "limit": 20,
    }, headers=headers)
    assert r.status_code == 200
    assert "cypher" in r.json()


@pytest.mark.asyncio
async def test_active_learning_select(client, token):
    headers = token("u1", "user")
    r = await client.post(f"{API_PREFIX}/active-learning/select", json={
        "samples": [
            {"id": "s1", "probs": [0.9, 0.1]},
            {"id": "s2", "probs": [0.4, 0.6]},
            {"id": "s3", "probs": [0.33, 0.34, 0.33]},
        ],
        "strategy": "uncertainty",
        "top_k": 2,
        "uncertainty_method": "entropy",
    }, headers=headers)
    assert r.status_code == 200
    assert "selected" in r.json()


@pytest.mark.asyncio
async def test_calibration_drift(client, token):
    headers = token("u1", "user")

    r = await client.post(f"{API_PREFIX}/calibration-drift/calibrate", json={
        "method": "temperature",
        "logits": [[2.0, 0.1], [0.2, 1.8]],
        "labels": [0, 1],
    }, headers=headers)
    assert r.status_code == 200

    r = await client.post(f"{API_PREFIX}/calibration-drift/evaluate", json={
        "probs": [0.95, 0.1, 0.7, 0.2],
        "labels": [1, 0, 1, 0],
    }, headers=headers)
    assert r.status_code == 200
    assert "ece" in r.json()

    r = await client.post(f"{API_PREFIX}/calibration-drift/detect", json={
        "reference": [1, 1, 2, 2, 3],
        "current": [1, 1, 2, 2, 3],
        "method": "psi",
        "categorical": False,
    }, headers=headers)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_version_management_flow(client, token):
    headers = token("u1", "user")
    VM = f"{API_PREFIX}/version-management"

    r = await client.post(f"{VM}/datasets", json={
        "name": "ds-v1", "data": [{"label": "a"}, {"label": "b"}],
    }, headers=headers)
    assert r.status_code == 200

    r = await client.get(f"{VM}/datasets", headers=headers)
    assert r.status_code == 200

    r = await client.post(f"{VM}/experiments", json={
        "name": "exp-1", "params": {"lr": 0.01}, "metrics": {"acc": 0.9},
    }, headers=headers)
    assert r.status_code == 200

    r = await client.get(f"{VM}/experiments", headers=headers)
    assert r.status_code == 200

    r = await client.post(f"{VM}/experiments/compare", json={"experiment_ids": None}, headers=headers)
    assert r.status_code == 200

    r = await client.post(f"{VM}/models", json={
        "name": "ner-model", "metrics": {"f1": 0.85},
    }, headers=headers)
    assert r.status_code == 200
    model = r.json()
    version = model.get("version", 1)

    r = await client.get(f"{VM}/models", headers=headers)
    assert r.status_code == 200

    r = await client.post(f"{VM}/models/stage", json={
        "name": "ner-model", "version": version, "stage": "production",
    }, headers=headers)
    assert r.status_code == 200

    r = await client.post(f"{VM}/retrain/check", json={
        "new_annotated": 120, "last_train_count": 10, "force": False,
    }, headers=headers)
    assert r.status_code == 200

    r = await client.post(f"{VM}/retrain/run", json={
        "model_name": "ner-model", "trigger_reason": "manual",
    }, headers=headers)
    assert r.status_code == 200
    run_id = r.json().get("run_id")

    if run_id:
        r = await client.get(f"{VM}/retrain/{run_id}", headers=headers)
        assert r.status_code == 200