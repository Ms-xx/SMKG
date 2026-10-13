# -*- coding: utf-8 -*-
"""步骤 20 引用含金量测试：位置权重、次数、结论表述、信号明细、批量聚合、API。"""
import pytest

from app.services.citation_quality_service import (
    CitationQualityService,
    analyze_document,
    score_documents,
    score_reference,
)

pytestmark = pytest.mark.asyncio


def test_core_reference_high_score():
    ref = {"index": 1, "title": "Attention Is All You Need"}
    out = score_reference(
        ref,
        {
            "position": "method",
            "occurrences": 4,
            "context_text": "we build on and extend this",
            "shared_topic": True,
            "shared_author": False,
            "numeric": True,
        },
        has_cites_edge=True,
    )
    assert out["score"] >= 0.7
    assert out["label"] == "core"
    assert any(s["signal"] == "position" for s in out["signals"])


def test_method_beats_related_work():
    ref = {"index": 1, "title": "X"}
    ctx_method = {
        "position": "method",
        "occurrences": 1,
        "context_text": "",
        "numeric": False,
    }
    ctx_rw = {
        "position": "related_work",
        "occurrences": 1,
        "context_text": "",
        "numeric": False,
    }
    s_method = score_reference(ref, ctx_method)
    s_rw = score_reference(ref, ctx_rw)
    assert s_method["score"] > s_rw["score"]


def test_perfunctory_label():
    ref = {"index": 2, "title": "Unrelated Survey"}
    out = score_reference(
        ref,
        {
            "position": "related_work",
            "occurrences": 1,
            "context_text": "see also [2] for a survey",
            "numeric": False,
        },
    )
    assert out["label"] == "perfunctory"
    assert out["score"] < 0.4


def test_occurrences_increase_score():
    ref = {"index": 1, "title": "Y"}
    low = score_reference(
        ref,
        {"position": "intro", "occurrences": 0, "context_text": "", "numeric": False},
    )
    high = score_reference(
        ref,
        {"position": "intro", "occurrences": 6, "context_text": "", "numeric": False},
    )
    assert high["score"] > low["score"]


def test_conclusion_term_hits():
    ref = {"index": 1, "title": "Z"}
    with_conc = score_reference(
        ref,
        {
            "position": "experiments",
            "occurrences": 2,
            "context_text": "our method outperforms [1]",
            "numeric": False,
        },
    )
    no_conc = score_reference(
        ref,
        {
            "position": "experiments",
            "occurrences": 2,
            "context_text": "see [1]",
            "numeric": False,
        },
    )
    assert with_conc["score"] > no_conc["score"]


def test_cites_edge_boosts():
    ref = {"index": 1, "title": "W"}
    ctx = {"position": "intro", "occurrences": 2, "context_text": "", "numeric": False}
    s1 = score_reference(ref, ctx, has_cites_edge=False)
    s2 = score_reference(ref, ctx, has_cites_edge=True)
    assert s2["score"] > s1["score"]


def test_analyze_document_produces_signals_and_counts():
    doc = {
        "document_id": "d1",
        "title": "Graph Neural Networks",
        "authors": ["Kipf"],
        "references": [
            {"index": 1, "title": "Attention Is All You Need"},
            {"index": 2, "title": "A Random Old Survey"},
        ],
        "pages": [
            {
                "page_number": 1,
                "text": (
                    "Introduction. Graph neural networks build on attention. Experiments show our "
                    "approach outperforms [1]. "
                    "Related Work. See also [2] for a broad survey of older methods."
                ),
            }
        ],
    }
    out = analyze_document(doc, cites_edges={"1": True, "2": False})
    assert out["total"] == 2
    assert any(s["signal"] == "occurrences" for r in out["refs"] for s in r["signals"])
    by_idx = {r["index"]: r for r in out["refs"]}
    assert by_idx[1]["label"] in ("core", "supporting")
    assert "signals" in by_idx[1]


def test_score_documents_aggregates_perfunctory():
    docs = [
        {
            "document_id": "a",
            "title": "Alpha",
            "references": [
                {"index": 1, "title": "Alpha Builds On Beta Method Long Name"}
            ],
            "pages": ["Related Work. See [1] for related survey."],
        },
        {
            "document_id": "b",
            "title": "Beta",
            "references": [
                {"index": 1, "title": "Some Core Method"},
                {"index": 2, "title": "Unrelated List Ref"},
            ],
            "pages": [
                "Method. We follow [1], extend [1] and improve on [1]; our approach outperforms [1].",
                "Related Work. Also see [2].",
            ],
        },
    ]
    out = score_documents(docs)
    assert out["document_count"] == 2
    assert out["total_refs"] == 3
    assert "perfunctory_refs" in out
    assert out["core_count"] >= 1


def test_service_methods():
    svc = CitationQualityService()
    s = svc.score(
        {"index": 1, "title": "T"},
        {"position": "method", "occurrences": 3, "context_text": "improve"},
        True,
    )
    assert "score" in s
    a = svc.analyze(
        {
            "document_id": "x",
            "references": [{"index": 1, "title": "T"}],
            "pages": ["Method. improve [1]"],
        }
    )
    assert a["total"] == 1


async def test_citation_quality_api(client, token):
    """端到端：POST /citation-quality/score 空列表正常（空库可不报错）。"""
    from conftest import API_PREFIX

    resp = await client.post(
        f"{API_PREFIX}/citation-quality/score",
        json={"document_ids": []},
        headers=token(),
    )
    assert resp.status_code == 200
    assert resp.json()["backend"] == "builtin"


async def test_citation_quality_api_requires_permission(client, token):
    from conftest import API_PREFIX

    resp = await client.post(
        f"{API_PREFIX}/citation-quality/score",
        json={"document_ids": []},
        headers=token(user_id="u1", role="viewer_unauthorized"),
    )
    assert resp.status_code == 403
