# -*- coding: utf-8 -*-
"""
关系推理与图谱补全服务单元测试
覆盖：规则推理（组合/逆关系/传递）、统计共现降级、TransE 链路预测与打分。
均为内存三元组，不触发网络与 Neo4j。
"""
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.relation_inference_service import (
    RelationInferenceService,
    TransELinkPredictor,
    StatisticalLinkPredictor,
    infer_triples,
)

FACTS = [
    {"head": "method_A", "relation": "PRODUCES", "tail": "mat_A"},
    {"head": "method_B", "relation": "PRODUCES", "tail": "mat_B"},
    {"head": "mat_A", "relation": "ACHIEVES", "tail": "prop_A"},
    {"head": "mat_B", "relation": "ACHIEVES", "tail": "prop_B"},
    {"head": "mat_A", "relation": "EXHIBITS", "tail": "prop_C"},
    {"head": "etl_A", "relation": "TRANSPORTS_HOLE", "tail": "mat_A"},
    {"head": "etl_B", "relation": "TRANSPORTS_ELECTRON", "tail": "mat_B"},
    {"head": "prop_A", "relation": "REQUIRES", "tail": "prop_C"},
]


def _pairs(inferred):
    return {(d["head"], d["relation"], d["tail"]) for d in inferred}


def test_infer_composition():
    """组合规则：PRODUCES + ACHIEVES ⇒ ENABLES；TRANSPORTS_HOLE + ACHIEVES ⇒ CONTRIBUTES_TO。"""
    inferred = infer_triples(FACTS)
    pairs = _pairs(inferred)
    assert ("method_A", "ENABLES", "prop_A") in pairs
    assert ("etl_A", "CONTRIBUTES_TO", "prop_A") in pairs


def test_infer_inverse():
    """逆关系规则：PRODUCES ⇒ PRODUCED_BY。"""
    pairs = _pairs(infer_triples(FACTS))
    assert ("mat_A", "PRODUCED_BY", "method_A") in pairs
    assert ("mat_B", "HAS_ELECTRON_TRANSPORTER", "etl_B") in pairs


def test_infer_transitive():
    """传递关系规则：REQUIRES 传递闭包。"""
    triples = [("a", "REQUIRES", "b"), ("b", "REQUIRES", "c")]
    pairs = _pairs(infer_triples(triples))
    assert ("a", "REQUIRES", "c") in pairs


def test_infer_no_duplicate_facts():
    """推断不重复已有事实。"""
    pairs = _pairs(infer_triples(FACTS))
    assert ("method_A", "PRODUCES", "mat_A") not in pairs


def test_statistical_score_exact_match():
    """统计降级：已存在三元组打 1.0，无关三元组打 0.0。"""
    pred = StatisticalLinkPredictor().fit(FACTS)
    assert pred.score_triple("method_A", "PRODUCES", "mat_A") == 1.0
    assert pred.score_triple("method_A", "PRODUCES", "不相关实体") == 0.0


def test_transe_trains_and_ranks_known_tail():
    """TransE 训练后：正样本打分应高于明显无关的尾实体。"""
    pred = TransELinkPredictor(dim=20, epochs=300).fit(FACTS)
    assert pred.trained is True
    pos = pred.score_triple("method_A", "PRODUCES", "mat_A")
    neg = pred.score_triple("method_A", "PRODUCES", "prop_A")
    assert pos > neg


def test_service_reason_and_predict():
    """门面服务：规则推理返回结果；链路预测返回候选（backend 标记）。"""
    svc = RelationInferenceService()
    inferred = svc.reason(FACTS)
    assert len(inferred) > 0

    result = svc.predict_links("method_A", "PRODUCES", FACTS, top_k=3)
    assert result["head"] == "method_A"
    assert result["relation"] == "PRODUCES"
    assert result["backend"] in {"transe", "statistical"}
    for c in result["candidates"]:
        assert "entity" in c and "score" in c


def test_predict_links_excludes_existing():
    """链路预测（补全）不返回已存在的事实。"""
    svc = RelationInferenceService()
    result = svc.predict_links("etl_A", "TRANSPORTS_HOLE", FACTS, top_k=5)
    existing = {c["entity"] for c in result["candidates"]}
    assert "mat_A" not in existing


def test_score_triple_empty_triples_degrades():
    """三元组过少时降级到统计基线，仍返回有限分数。"""
    svc = RelationInferenceService()
    score = svc.score_triple("x", "r", "y", [("x", "r", "y")])
    assert score == 1.0