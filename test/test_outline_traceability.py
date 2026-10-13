# -*- coding: utf-8 -*-
"""步骤 23 可溯源 References：生成式编造剔除 + 溯源绑定 + [n]一一对应 + LLM 降级。"""
import pytest

from app.models.document import Document
from app.core.permissions import DOCUMENT_READ
from app.services.writing_assistant_service import generate_outline

API_PREFIX = "/api/v1"


@pytest.mark.asyncio
async def test_import_permission_constant():
    # 门禁：接口层使用细粒度权限码而非裸 get_current_user
    assert DOCUMENT_READ == "document:read"


def test_hallucinated_ref_dropped_and_counted():
    wl = [
        {
            "title": "Attention Is All You Need",
            "document_id": "d1",
            "node_id": "n1",
            "page": 3,
        }
    ]
    refs = [
        {"index": 1, "title": "Attention Is All You Need"},
        {"index": 2, "title": "A Totally Fabricated Fake Paper 2999"},
        {"index": 3, "title": None, "raw": "No Title Ref"},
    ]
    out = generate_outline("transformers", refs, wl)
    assert out["backend"] == "template"  # LLM 缺失 → 模板骨架 + 真实引用
    assert out["reference_count"] == 1
    assert out["dropped_references"]["count"] == 2
    reasons = {i["reason"] for i in out["dropped_references"]["items"]}
    assert reasons == {"not_in_whitelist"}


def test_real_ref_kept_with_source_and_no_new_hallucination():
    wl = [
        {
            "title": "BERT: Pre-training of Deep Bidirectional Transformers",
            "document_id": "doc-bert",
            "node_id": "node-bert",
            "page": 7,
        }
    ]
    refs = [
        {"index": 1, "title": "BERT: Pre-training of Deep Bidirectional Transformers"}
    ]
    out = generate_outline("nlp", refs, wl)
    assert out["reference_count"] == 1
    r = out["references"][0]
    assert r["source"]["document_id"] == "doc-bert"
    assert r["source"]["node_id"] == "node-bert"
    assert r["source"]["page"] == 7
    # 无幻觉：不引入白名单外条目
    assert len(out["references"]) == 1


def test_fuzzy_title_match_case_and_whitespace():
    wl = [
        {
            "title": "Graph Convolutional Networks",
            "document_id": "gcn",
            "node_id": "gcn",
            "page": None,
        }
    ]
    refs = [{"index": 1, "title": "graph convolutional  networks: a deeper look"}]
    out = generate_outline("gnn", refs, wl)
    assert out["reference_count"] == 1
    assert out["references"][0]["source"]["document_id"] == "gcn"


def test_duplicate_source_ref_dropped():
    wl = [
        {
            "title": "The Duplicated Paper",
            "document_id": "dup",
            "node_id": "dup",
            "page": 1,
        },
    ]
    refs = [
        {"index": 1, "title": "The Duplicated Paper"},
        {"index": 2, "title": "The Duplicated Paper"},  # 同源重复
    ]
    out = generate_outline("ml", refs, wl)
    assert out["reference_count"] == 1
    assert out["dropped_references"]["count"] == 1
    assert out["dropped_references"]["items"][0]["reason"] == "duplicate_source"


def test_n_markers_align_with_references_list():
    wl = [
        {"title": "Paper Alpha", "document_id": "a", "node_id": "a", "page": 1},
        {"title": "Paper Beta", "document_id": "b", "node_id": "b", "page": 2},
    ]
    refs = [
        {"index": 90, "title": "Fake Gamma"},  # 编造 → 剔除
        {"index": 91, "title": "Paper Alpha"},
        {"index": 92, "title": "Paper Beta"},
    ]
    out = generate_outline("mm", refs, wl)
    kept = out["references"]
    assert [r["index"] for r in kept] == [1, 2]  # 重新编号 1..N
    assert len(out["citation_map"]) == 2  # [n] 与列表一一对应
    assert out["citation_map"][0]["n"] == 1 and out["citation_map"][1]["n"] == 2
    # Related Work 小节里的 [n] 标记与列表长度一致
    rw_section = next(s for s in out["sections"] if s["title"] == "Related Work")
    assert "[1]" in rw_section["content"] and "[2]" in rw_section["content"]
    # 编造项被剔除后不占编号
    assert "[3]" not in rw_section["content"]


def test_legacy_path_without_whitelist_keeps_old_behavior():
    # verified_references=None 时不强制过滤（兼容旧调用）
    refs = [{"index": 1, "title": "Real paper one", "raw": "Author. Real paper one."}]
    out = generate_outline("graph neural networks", refs)
    assert out["backend"] == "rule"
    assert out["reference_count"] == 1
    assert out["references"][0]["text"].startswith("Author")
    assert "dropped_references" not in out


def test_strict_empty_whitelist_drops_all():
    # 显式传入空白名单 = 「无可溯源来源」→ 全部剔除；空库降级回显由接口层把 [] → None 处理
    refs = [{"index": 1, "title": "Whatever Title", "raw": "Whatever."}]
    out = generate_outline("topic", refs, [])
    assert out["backend"] == "template"
    assert out["reference_count"] == 0
    assert out["dropped_references"]["count"] == 1


@pytest.mark.asyncio
async def test_outline_api_seeded_document_traceable(client, token, db):
    """接口层：库内有真实文档时，引用命中者带 source 溯源，编造项被剔除。"""
    doc = Document(
        id="doc-seeded-1",
        title="Attention Is All You Need",
        file_path="papers/attn.pdf",
        file_size=100,
        uploaded_by="u1",
        status="uploaded",
    )
    db.add(doc)
    await db.commit()

    resp = await client.post(
        f"{API_PREFIX}/writing-assistant/outline",
        json={
            "idea": "attention",
            "references": [
                {"index": 1, "title": "Attention Is All You Need"},
                {"index": 2, "title": "A Fabricated Non-Existent Paper 9999"},
            ],
        },
        headers=token(),  # admin role → DOCUMENT_READ 放行
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["reference_count"] == 1
    assert data["references"][0]["source"]["document_id"] == "doc-seeded-1"
    assert data["dropped_references"]["count"] == 1
    assert data["backend"] == "template"


@pytest.mark.asyncio
async def test_outline_api_empty_library_keeps_echo(client, token):
    """接口层：空库（无白名单）→ 降级回显，不报错，并保持文档:`references` 原样。"""
    resp = await client.post(
        f"{API_PREFIX}/writing-assistant/outline",
        json={"idea": "graph", "references": [{"index": 1, "raw": "A. Real."}]},
        headers=token(),
    )
    assert resp.status_code == 200
    assert resp.json()["reference_count"] == 1
