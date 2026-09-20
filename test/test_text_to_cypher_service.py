# -*- coding: utf-8 -*-
"""Text-to-Cypher 服务单元测试：规则模板翻译 + 只读安全校验。零网络依赖。"""
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.text_to_cypher_service import TextToCypherService


def test_translate_count_by_label():
    out = TextToCypherService().translate("有多少种材料")
    assert out["intent"] == "count_by_label"
    assert "MATCH (n:`Material`)" in out["cypher"]
    assert "count" in out["cypher"]


def test_translate_list_by_label():
    out = TextToCypherService().translate("列出所有方法")
    assert out["intent"] == "list_by_label"
    assert "MATCH (n:`Method`)" in out["cypher"]
    assert "RETURN" in out["cypher"]


def test_translate_entity_relations():
    out = TextToCypherService().translate("MAPbI3 和 高效率 的关系")
    assert out["intent"] == "entity_relations"
    assert "MATCH (a)-[r]->(b)" in out["cypher"]
    assert out["params"]["a"] == "MAPbI3"


def test_translate_keyword_fallback():
    out = TextToCypherService().translate("钙钛矿")
    assert out["intent"] == "keyword_search"
    assert "CONTAINS" in out["cypher"]


def test_translate_empty():
    out = TextToCypherService().translate("")
    assert out["intent"] == "empty"
    assert out["cypher"] == ""


def test_validate_read_only_ok():
    svc = TextToCypherService()
    ok, _ = svc.validate("MATCH (n:Material) RETURN n LIMIT 10")
    assert ok is True


def test_validate_rejects_dangerous():
    svc = TextToCypherService()
    ok, msg = svc.validate("MATCH (n) DELETE n")
    assert ok is False
    assert "危险" in msg


def test_translate_always_read_only():
    svc = TextToCypherService()
    for q in ["有多少种材料", "列出所有方法", "MAPbI3 和 高效率 的关系", "钙钛矿"]:
        out = svc.translate(q)
        assert out["cypher"].upper().startswith("MATCH")
        ok, _ = svc.validate(out["cypher"])
        assert ok is True