# -*- coding: utf-8 -*-
"""多 Agent 协作与冲突解决（步骤 9）服务层单元测试。"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.services.multi_agent_service import (  # noqa: E402
    AGENT_QA,
    AGENT_EXTRACT,
    _extract_fallback,
    multi_agent_service,
    resolve_conflicts,
)


def test_list_agents_has_four():
    agents = multi_agent_service.list_agents()
    names = {a["name"] for a in agents}
    assert names == {"parse", "extract", "qa", "summarize"}


def test_run_default_uses_all_agents():
    session = multi_agent_service.run(query="钙钛矿有哪些性能特点？")
    assert set(session["agents"]) == {"parse", "extract", "qa", "summarize"}
    assert len(session["agent_results"]) == 4
    assert session["resolution"]["final_text"] is not None


def test_run_subset_agents():
    session = multi_agent_service.run(query="你好", agents=["qa"])
    assert session["agents"] == ["qa"]
    assert len(session["agent_results"]) == 1
    assert session["agent_results"][0]["agent"] == "qa"


def test_extract_fallback_detects_entities():
    result = _extract_fallback("钙钛矿太阳能电池采用高效率的制备方法。")
    texts = {it["text"] for it in result["items"]}
    assert "钙钛矿" in texts
    assert "太阳能电池" in texts
    assert result["content"] == f"抽取到 {len(result['items'])} 个实体。"


def test_run_session_stored():
    session = multi_agent_service.run(query="存储测试")
    retrieved = multi_agent_service.get_session(session["session_id"])
    assert retrieved is not None
    assert retrieved["query"] == "存储测试"


def test_resolve_conflicts_merge_dedup():
    proposals = [
        {"agent": "a1", "items": [{"text": "钙钛矿", "type": "Material"}], "content": None},
        {"agent": "a2", "items": [{"text": "钙钛矿", "type": "Material"}], "content": None},
    ]
    out = resolve_conflicts(proposals, "merge")
    assert out["final_items"] == [{"text": "钙钛矿", "type": "Material"}]
    assert out["conflicts"] == []


def test_resolve_conflicts_vote_majority():
    proposals = [
        {"agent": "a1", "items": [{"text": "钙钛矿", "type": "Material"}], "content": None},
        {"agent": "a2", "items": [{"text": "钙钛矿", "type": "Material"}], "content": None},
        {"agent": "a3", "items": [{"text": "钙钛矿", "type": "Property"}], "content": None},
    ]
    out = resolve_conflicts(proposals, "vote")
    assert out["final_items"] == [{"text": "钙钛矿", "type": "Material"}]
    assert len(out["conflicts"]) == 1


def test_resolve_conflicts_arbitrate_highest_confidence():
    proposals = [
        {"agent": "a1", "items": [{"text": "钙钛矿", "type": "Material", "confidence": 0.6}], "content": None},
        {"agent": "a2", "items": [{"text": "钙钛矿", "type": "Device", "confidence": 0.9}], "content": None},
    ]
    out = resolve_conflicts(proposals, "arbitrate")
    assert out["final_items"] == [{"text": "钙钛矿", "type": "Device"}]
    assert len(out["conflicts"]) == 1


def test_resolve_conflicts_detects_entity_type_conflict():
    proposals = [
        {"agent": "a1", "items": [{"text": "钙钛矿", "type": "Material"}], "content": None},
        {"agent": "a2", "items": [{"text": "钙钛矿", "type": "Property"}], "content": None},
    ]
    out = resolve_conflicts(proposals, "merge")
    assert len(out["conflicts"]) == 1
    assert out["conflicts"][0]["type"] == "entity_type"


def test_resolve_conflicts_answer_conflict_detected():
    proposals = [
        {"agent": "qa", "content": "答案 A", "confidence": 0.9, "items": None},
        {"agent": "summarize", "content": "答案 B", "confidence": 0.8, "items": None},
    ]
    out = resolve_conflicts(proposals, "vote")
    assert len(out["conflicts"]) == 1
    assert out["conflicts"][0]["type"] == "answer"


def test_resolve_conflicts_answer_merge_joins():
    proposals = [
        {"agent": "qa", "content": "回答一", "confidence": 0.9, "items": None},
        {"agent": "summarize", "content": "回答二", "confidence": 0.8, "items": None},
    ]
    out = resolve_conflicts(proposals, "merge")
    assert out["final_text"] == "回答一；回答二"


def test_resolve_conflicts_answer_arbitrate_picks_highest_confidence():
    proposals = [
        {"agent": "qa", "content": "低置信答案", "confidence": 0.5, "items": None},
        {"agent": "summarize", "content": "高置信答案", "confidence": 0.95, "items": None},
    ]
    out = resolve_conflicts(proposals, "arbitrate")
    assert out["final_text"] == "高置信答案"


def test_resolve_conflicts_answer_vote_tie_unresolved():
    proposals = [
        {"agent": "qa", "content": "A", "confidence": 0.9, "items": None},
        {"agent": "summarize", "content": "B", "confidence": 0.9, "items": None},
    ]
    out = resolve_conflicts(proposals, "vote")
    assert out["unresolved"], "平票应标记为未解决"