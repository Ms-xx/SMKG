# -*- coding: utf-8 -*-
"""annotations 模块 HTTP 集成测试：创建/列表/更新/提交/两级审核/版本/删除/一致性评估。"""
import pytest

from conftest import API_PREFIX


async def _create_annotation(client, headers, document_id="doc1"):
    r = await client.post(f"{API_PREFIX}/annotations/", json={
        "document_id": document_id,
        "annotation_type": "entity",
        "content": {"name": "Perovskite", "type": "Material"},
        "confidence": 0.9,
    }, headers=headers)
    assert r.status_code == 201
    return r.json()


@pytest.mark.asyncio
async def test_annotation_crud_and_review(client, token):
    headers = token("u1", "admin")
    ann = await _create_annotation(client, headers)
    ann_id = ann["id"]
    assert ann["status"] == "draft"

    # 列表
    r = await client.get(f"{API_PREFIX}/annotations/", params={"document_id": "doc1"}, headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 1

    # 按文档查询
    r = await client.get(f"{API_PREFIX}/annotations/document/doc1", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 1

    # 更新
    r = await client.put(f"{API_PREFIX}/annotations/{ann_id}", json={"confidence": 0.95}, headers=headers)
    assert r.status_code == 200
    assert r.json()["confidence"] == 0.95

    # 提交审核
    r = await client.post(f"{API_PREFIX}/annotations/{ann_id}/submit", headers=headers)
    assert r.status_code == 200

    # 版本列表
    r = await client.get(f"{API_PREFIX}/annotations/{ann_id}/versions", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) >= 2

    # 初审通过
    r = await client.post(f"{API_PREFIX}/annotations/{ann_id}/first-review",
                          json={"approved": True, "comment": "ok"}, headers=headers)
    assert r.status_code == 200

    # 终审通过
    r = await client.post(f"{API_PREFIX}/annotations/{ann_id}/final-review",
                          json={"approved": True, "comment": "good"}, headers=headers)
    assert r.status_code == 200

    # 删除
    r = await client.delete(f"{API_PREFIX}/annotations/{ann_id}", headers=headers)
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_annotation_not_found_and_denied(client, token):
    headers = token("u1", "admin")
    # 不存在
    r = await client.put(f"{API_PREFIX}/annotations/no-id", json={"confidence": 0.5}, headers=headers)
    assert r.status_code == 404

    # 无权限
    r = await client.post(f"{API_PREFIX}/annotations/", json={
        "document_id": "doc1", "annotation_type": "entity", "content": {},
    }, headers=token("u2", "user"))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_annotation_agreement(client, token):
    headers = token("u1", "admin")
    r = await client.post(f"{API_PREFIX}/annotations/agreement", json={
        "ratings": [[1, 1], [2, 2], [1, 1]],
        "metrics": ["fleiss", "cohens", "krippendorff"],
    }, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body  # 返回指标字典