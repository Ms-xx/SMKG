# -*- coding: utf-8 -*-
"""步骤 19 跨文献结构化演进对比矩阵测试：维度完整性、锚点非空、无锚点不出结论、LLM 降级。"""
from unittest.mock import patch

import pytest

from app.core.config import settings
from app.services.multi_paper_compare_service import (
    DEFAULT_DIMENSIONS,
    MultiPaperCompareService,
    build_compare_matrix,
    enhance_insights,
)

pytestmark = pytest.mark.asyncio

# 模拟真实文献原文（数值与原文一致，供抽取）
_DOC_BERT = {
    "document_id": "p-bert",
    "title": "BERT: Pre-training of Deep Bidirectional Transformers",
    "pages": [
        {
            "page_number": 1,
            "text": (
                "BERT is a BERT bidirectional encoder representations from transformers. "
                "It is a transformer encoder architecture with 110M parameters and a "
                "context length of 512 tokens. Layer normalization applied in post-norm style. "
                "Self-attention with multi-head attention is used."
            ),
        },
        {
            "page_number": 2,
            "text": "BERT uses a sinusoidal positional encoding for input tokens.",
        },
    ],
    "param_count": "110M",
    "context_window": "512",
}
_DOC_GPT = {
    "document_id": "p-gpt3",
    "title": "GPT-3: Language Models are Few-Shot Learners",
    "pages": [
        {
            "page_number": 1,
            "text": (
                "GPT-3 is a generative pre-trained transformer causal decoder. "
                "The largest model has 175B parameters and a context window of 2048 tokens. "
                "Layer normalization is applied with pre-norm (norm before each sublayer). "
                "Masked causal self-attention used."
            ),
        }
    ],
    "param_count": "175B",
    "context_window": "2048",
}
_DOC_TF = {
    "document_id": "p-tf",
    "title": "Attention Is All You Need",
    "pages": [
        {
            "page_number": 1,
            "text": "The Transformer uses an encoder-decoder architecture with self-attention "
            "and 65M parameters. It supports a sequence length of 512. "
            "Layer normalization applied post-norm after each sublayer.",
        }
    ],
}


def test_default_dimensions_at_least_five():
    assert len(DEFAULT_DIMENSIONS) >= 5


def test_matrix_returns_expected_shape():
    m = build_compare_matrix([_DOC_BERT, _DOC_GPT])
    assert m["backend"] == "auto"
    assert m["document_count"] == 2
    assert m["dimension_count"] >= 5
    assert len(m["document_columns"]) == 2
    assert len(m["rows"]) == m["dimension_count"]


def test_cells_carry_anchors():
    m = build_compare_matrix([_DOC_BERT])
    param_row = next(r for r in m["rows"] if r["dimension"] == "parameter_count")
    cell = param_row["cells"][0]
    assert cell["anchored"] is True
    assert cell["value"] == "110M"
    assert len(cell["anchors"]) >= 1
    assert cell["anchors"][0]["document_id"] == "p-bert"
    assert cell["anchors"][0]["snippet"] != ""


def test_no_anchor_means_no_conclusion():
    """某文档对某维度无原文锚点 → anchored=false、value=None、附 note。"""
    doc = {
        "document_id": "p-empty",
        "title": "No Meta",
        "pages": [
            {
                "page_number": 1,
                "text": "this paper has no relevant dimension text at all.",
            }
        ],
    }
    m = build_compare_matrix([doc], dimensions=["parameter_count"])
    cell = m["rows"][0]["cells"][0]
    assert cell["anchored"] is False
    assert cell["value"] is None
    assert "无锚点" in cell["note"]


def test_parameter_count_regex_from_text():
    m = build_compare_matrix([_DOC_GPT])
    cell = next(r for r in m["rows"] if r["dimension"] == "parameter_count")["cells"][0]
    assert cell["anchored"] is True
    assert cell["value"].startswith("175B") or cell["value"] == "175B"


def test_context_window_from_text():
    m = build_compare_matrix([_DOC_GPT])
    cell = next(r for r in m["rows"] if r["dimension"] == "context_window")["cells"][0]
    assert cell["anchored"] is True
    assert "2048" in cell["value"]


def test_taxonomy_model_type_and_architecture():
    m = build_compare_matrix([_DOC_BERT, _DOC_GPT])
    model_row = next(r for r in m["rows"] if r["dimension"] == "model_type")
    arch_row = next(r for r in m["rows"] if r["dimension"] == "architecture")
    bert_model = model_row["cells"][0]
    gpt_arch = arch_row["cells"][1]
    assert bert_model["anchored"] is True
    assert bert_model["value"] == "BERT"
    assert gpt_arch["anchored"] is True


def test_enhance_degrade_rule_when_llm_off(monkeypatch):
    monkeypatch.setattr(settings, "LLM_ENABLED", False)
    matrix = build_compare_matrix([_DOC_BERT, _DOC_GPT])
    out = enhance_insights(matrix)
    assert out["backend"] == "rule"
    assert out["insight"]


def test_enhance_llm_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "LLM_ENABLED", True)
    monkeypatch.setattr(settings, "LLM_ENDPOINT", "http://127.0.0.1:1234/v1")
    monkeypatch.setattr(settings, "LLM_TIMEOUT", 5.0)
    matrix = build_compare_matrix([_DOC_BERT, _DOC_GPT])
    with patch(
        "app.services.multi_paper_compare_service._llm_chat_completion",
        return_value="架构从 encoder 演进到 decoder，参数量与上下文窗口持续递增。",
    ):
        out = enhance_insights(matrix)
    assert out["backend"] == "llm"
    assert out["insight"]


def test_service_build_matrix():
    svc = MultiPaperCompareService()
    m = svc.build_matrix([_DOC_TF])
    assert m["dimension_count"] >= 5
    assert svc.enhance(m)["backend"] in ("rule", "llm")


async def test_compare_matrix_api(client, token, monkeypatch):
    """端到端：compare-matrix 接口返回矩阵，含锚点；无锚点不出结论、LLM 未配置洞察降级 rule。"""
    from conftest import API_PREFIX

    monkeypatch.setattr(settings, "LLM_ENABLED", False)
    resp = await client.post(
        f"{API_PREFIX}/source-anchor/compare-matrix",
        json={
            "documents": [
                {
                    "document_id": "p-bert",
                    "title": "BERT",
                    "pages": [
                        "BERT is a bidirectional encoder representations from transformers "
                        "transformer encoder with 110M parameters and 512 tokens."
                    ],
                },
                {
                    "document_id": "p-gpt3",
                    "title": "GPT-3",
                    "pages": [
                        "GPT-3 is a generative pre-trained transformer causal decoder with "
                        "175B parameters and a context window of 2048 tokens."
                    ],
                },
            ]
        },
        headers=token(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["dimension_count"] >= 5
    assert len(body["rows"]) >= 5
    ids = {c["document_id"] for c in body["document_columns"]}
    assert ids == {"p-bert", "p-gpt3"}
    # 参数量行两单元均应锚定
    param_row = next(r for r in body["rows"] if r["dimension"] == "parameter_count")
    assert all(c["anchored"] for c in param_row["cells"])
    assert body["insight"]["backend"] == "rule"


async def test_compare_matrix_api_requires_permission(client, token):
    """无 document:read 权限 → 403。"""
    from conftest import API_PREFIX

    resp = await client.post(
        f"{API_PREFIX}/source-anchor/compare-matrix",
        json={"documents": []},
        headers=token(user_id="u1", role="viewer_unauthorized"),
    )
    # viewer_unauthorized（非 admin）无 document:read → 403
    assert resp.status_code == 403
