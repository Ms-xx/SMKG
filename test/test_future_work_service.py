# -*- coding: utf-8 -*-
"""步骤 22 Future Work 前沿探索测试：抽取、已解决判定、无年份/无边降级、置信度标注。"""
import pytest

from app.services.future_work_service import (
    FutureWorkService,
    extract_future_work,
    judge_resolved,
    scan_future_work,
)

pytestmark = pytest.mark.asyncio


def test_extract_future_work_finds_english():
    chunks = [
        "As future work, we plan to study knowledge distillation for smaller models."
    ]
    out = extract_future_work(chunks)
    assert len(out) == 1
    assert "distillation" in out[0]["idea"].lower()
    assert out[0]["keyword"]


def test_extract_future_work_finds_chinese():
    chunks = ["未来工作：我们将探索跨语言迁移在多语言模型上的效果。"]
    out = extract_future_work(chunks)
    assert len(out) == 1
    assert "跨语言" in out[0]["idea"]


def test_extract_future_work_empty_when_no_statement():
    assert (
        extract_future_work(["This paper reports experiments without future plans."])
        == []
    )


def test_judge_resolved_with_later_paper_and_edge():
    idea = {
        "idea": "study knowledge distillation for smaller models",
        "keyword": "future work",
    }
    later = [
        {
            "document_id": "p2",
            "title": "Distilling the Knowledge",
            "year": 2015,
            "has_cites_edge": True,
            "text": (
                "In this paper we address knowledge distillation: we solve the compression "
                "problem for smaller models."
            ),
        }
    ]
    j = judge_resolved(idea, later)
    assert j["resolved"] is True
    assert j["confidence"] >= 0.85
    assert j["resolved_by"][0]["document_id"] == "p2"


def test_judge_not_resolved_without_later_paper():
    idea = {"idea": "explore unsupervised parsing", "keyword": "future work"}
    j = judge_resolved(idea, [])
    assert j["resolved"] is False
    assert j["confidence"] <= 0.3


def test_judge_low_confidence_when_no_year():
    idea = {"idea": "improve multilingual models", "keyword": "future work"}
    later = [
        {
            "document_id": "p9",
            "title": "Multilingual Workshop",
            "year": None,
            "has_cites_edge": True,
            "text": (
                "we address the multilingual problem and we solve the model scaling "
                "using improved multilingual models."
            ),
        }
    ]
    j = judge_resolved(idea, later)
    assert j["resolved"] is True
    # 无年份 → 顶多低置信度（≤0.5）
    assert j["confidence"] <= 0.5


def test_judge_low_confidence_when_no_cites_edge():
    idea = {
        "idea": "apply graph attention to node classification",
        "keyword": "future work",
    }
    later = [
        {
            "document_id": "p3",
            "title": "Graph Attention",
            "year": 2018,
            "has_cites_edge": False,
            "text": (
                "we introduce graph attention and we address node classification "
                "by applying graph attention."
            ),
        }
    ]
    j = judge_resolved(idea, later)
    assert j["resolved"] is True
    assert j["confidence"] < 0.85  # 无边 → 加权后封顶 0.75


def test_scan_separates_excluded_and_candidates():
    docs = [
        {
            "document_id": "p0",
            "title": "Base",
            "year": 2015,
            "authors": ["A"],
            "references": [],
            "pages": [
                {
                    "page_number": 1,
                    "text": "Future work: we plan to explore knowledge distillation.",
                }
            ],
        },
        {
            "document_id": "p1",
            "title": "Later",
            "year": 2017,
            "authors": ["A"],
            "references": [{"title": "Base"}],
            "pages": [
                {
                    "page_number": 1,
                    "text": "In this work we solve knowledge distillation compression.",
                }
            ],
        },
    ]
    scan = scan_future_work(docs)
    assert scan["idea_count"] >= 1
    # Base 提出的蒸馏 idea 被 Later（更晚年份+共享作者）解决 → 进 excluded
    excluded_ids = {r for i in scan["excluded"] for r in i["resolved_by"]}
    assert "p1" in excluded_ids
    assert scan["time_buckets"]  # 复用步骤12时间桶


def test_scan_time_buckets():
    docs = [
        {
            "document_id": "a",
            "title": "A",
            "year": 2018,
            "pages": ["no future work text here simple"],
        },
        {"document_id": "b", "title": "B", "year": 2020, "pages": ["nothing"]},
    ]
    scan = scan_future_work(docs)
    assert scan["time_buckets"] == [
        {"year": 2018, "count": 1},
        {"year": 2020, "count": 1},
    ]


def test_service_extract_and_judge():
    svc = FutureWorkService()
    out = svc.extract(["As future work, we will study calibration."])
    assert len(out) == 1
    j = svc.judge(out[0], [])
    assert j["resolved"] is False


async def test_future_work_api(client, token):
    """端到端：GET /citation-graph/future-work 返回 scan（可不报错、空库也可）。"""
    from conftest import API_PREFIX

    resp = await client.get(f"{API_PREFIX}/citation-graph/future-work", headers=token())
    assert resp.status_code == 200
    body = resp.json()
    assert body["backend"] == "builtin"
    assert "excluded" in body and "candidates" in body
    assert "filtered" in body


async def test_future_work_api_filter(client, token):
    """时间窗/领域过滤不报错。"""
    from conftest import API_PREFIX

    resp = await client.get(
        f"{API_PREFIX}/citation-graph/future-work?min_year=2014&max_year=2026&domain=ai",
        headers=token(),
    )
    assert resp.status_code == 200
    assert resp.json()["filtered"]["min_year"] == 2014
