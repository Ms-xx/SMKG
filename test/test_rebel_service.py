# -*- coding: utf-8 -*-
"""
REBEL 关系抽取服务单元测试
覆盖：输出解析（纯函数）、关系类型规范化、模型缺失安全降级、实体对齐、
以及与 extraction_service 规则抽取的合并/去重（与 NER 输出对齐）。
"""
from app.services.extraction_service import ExtractionService
from app.services.rebel_service import (
    RebelService,
    normalize_relation_type,
    parse_rebel_output,
)


def test_parse_rebel_output():
    text = (
        "<s><triplet> Perovskite <subj> solar cell <obj> subclass of "
        "<triplet> Solar cell <subj> high efficiency <obj> has property "
        "<triplet> Solar cell <subj> China <obj> located in </s>"
    )
    triplets = parse_rebel_output(text)
    assert len(triplets) == 3
    assert triplets[0] == {
        "head": "Perovskite",
        "tail": "solar cell",
        "type": "subclass of",
    }
    assert triplets[1]["head"] == "Solar cell"
    assert triplets[1]["type"] == "has property"
    # 三类以上不同关系类型
    assert len({t["type"] for t in triplets}) >= 3


def test_parse_rebel_output_empty_and_pad():
    assert parse_rebel_output("<s><pad></s>") == []
    assert parse_rebel_output("") == []


def test_normalize_relation_type():
    assert normalize_relation_type("subclass of") == "SUBCLASS_OF"
    assert normalize_relation_type(
        "located in the administrative territorial entity"
    ) == ("LOCATED_IN_THE_ADMINISTRATIVE_TERRITORIAL_ENTITY")
    assert normalize_relation_type("has property") == "HAS_PROPERTY"
    assert normalize_relation_type("") == ""


def test_extract_empty_and_degrades():
    svc = RebelService()
    assert svc.extract("") == []
    assert svc.extract("   ") == []
    svc.backend = "unavailable"  # 模拟无模型，避免触发真实下载
    assert svc.extract("Perovskite is a material.") == []


def test_match_entity_type():
    entities = [
        {"text": "Perovskite", "type": "Material"},
        {"text": "solar cell", "type": "Device"},
    ]
    assert RebelService._match_entity_type("Perovskite", entities) == "Material"
    assert RebelService._match_entity_type("solar cell", entities) == "Device"
    assert RebelService._match_entity_type("unknown", entities) == "ENTITY"
    assert RebelService._match_entity_type("x", None) == "ENTITY"


async def test_extract_relations_merges_rebel(monkeypatch):
    def fake_rebel(self, text, entities):
        return [
            {
                "source": "钙钛矿材料",
                "source_type": "Material",
                "target": "溶液法",
                "target_type": "Method",
                "relation_type": "PRODUCED_BY",
                "confidence": 0.85,
                "context": text,
            },
            {
                "source": "钙钛矿材料",
                "source_type": "Material",
                "target": "高效率",
                "target_type": "Property",
                "relation_type": "HAS_PROPERTY",
                "confidence": 0.85,
                "context": text,
            },
        ]

    monkeypatch.setattr(ExtractionService, "_extract_by_ner", lambda self, text: [])
    monkeypatch.setattr(ExtractionService, "_extract_relations_by_rebel", fake_rebel)
    svc = ExtractionService()

    text = "钙钛矿材料由溶液法制备"
    entities = [
        {"text": "钙钛矿材料", "type": "Material"},
        {"text": "溶液法", "type": "Method"},
    ]
    relations = await svc.extract_relations(text, entities)

    types = {r["relation_type"] for r in relations}
    assert "PRODUCED_BY" in types  # 规则产生
    assert "HAS_PROPERTY" in types  # REBEL 产生
    # 规则与 REBEL 产生相同 PRODUCED_BY，按 source/target/relation 去重后仅一条
    produced = [r for r in relations if r["relation_type"] == "PRODUCED_BY"]
    assert len(produced) == 1


async def test_extract_relations_rebel_disabled_keeps_rules(monkeypatch):
    # REBEL 不可用时降级：仅规则关系，不报错
    monkeypatch.setattr(ExtractionService, "_extract_by_ner", lambda self, text: [])
    monkeypatch.setattr(
        ExtractionService, "_extract_relations_by_rebel", lambda self, t, e: []
    )
    svc = ExtractionService()

    text = "钙钛矿材料由溶液法制备"
    entities = [
        {"text": "钙钛矿材料", "type": "Material"},
        {"text": "溶液法", "type": "Method"},
    ]
    relations = await svc.extract_relations(text, entities)
    assert any(r["relation_type"] == "PRODUCED_BY" for r in relations)
