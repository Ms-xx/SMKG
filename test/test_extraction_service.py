# -*- coding: utf-8 -*-
"""extraction_service 单元/集成测试：规则抽取、NER 合并、关系抽取、文档处理、LLM 占位。"""
import pytest

from app.services.extraction_service import ExtractionService
from app.models.document import Document, DocumentPage, DocumentElement


@pytest.fixture
def svc(monkeypatch):
    # 关闭 NER / REBEL 模型加载，仅走规则匹配路径，保证测试确定性（离线、无下载）
    monkeypatch.setattr(ExtractionService, "_extract_by_ner", lambda self, text: [])
    monkeypatch.setattr(
        ExtractionService, "_extract_relations_by_rebel", lambda self, text, entities: []
    )
    return ExtractionService()


async def test_extract_entities_rule_match(svc):
    text = "钙钛矿材料具有优异的效率和稳定性"
    entities = await svc.extract_entities(text)

    types = {e["type"] for e in entities}
    assert "Material" in types
    assert "Property" in types
    assert any(e["text"] == "钙钛矿" for e in entities)
    # 按 start 排序
    starts = [e["start"] for e in entities]
    assert starts == sorted(starts)


async def test_extract_entities_ner_merge(monkeypatch):
    def fake_ner(self, text):
        return [{"text": "钙钛矿", "type": "Material", "start": 0, "end": 3, "confidence": 0.99}]

    monkeypatch.setattr(ExtractionService, "_extract_by_ner", fake_ner)
    svc = ExtractionService()
    entities = await svc.extract_entities("钙钛矿材料")

    matched = [e for e in entities if e["start"] == 0 and e["text"].lower() == "钙钛矿"]
    assert len(matched) == 1
    # NER 结果优先（覆盖规则结果）
    assert matched[0]["confidence"] == 0.99


async def test_extract_relations_produced_by(svc):
    text = "钙钛矿材料由溶液法制备"
    entities = [
        {"text": "钙钛矿材料", "type": "Material"},
        {"text": "溶液法", "type": "Method"},
    ]
    relations = await svc.extract_relations(text, entities)
    assert any(r["relation_type"] == "PRODUCED_BY" for r in relations)
    r = [x for x in relations if x["relation_type"] == "PRODUCED_BY"][0]
    assert r["source"] == "钙钛矿材料"
    assert r["target"] == "溶液法"


async def test_extract_relations_no_entity_match(svc):
    text = "A由B制备"
    # 实体列表为空 → 找不到任何实体 → 无关系
    relations = await svc.extract_relations(text, [])
    assert relations == []


def test_find_entity_by_text():
    svc = ExtractionService()
    entities = [{"text": "钙钛矿材料", "type": "Material"}]
    assert svc._find_entity_by_text(entities, "钙钛矿材料")["type"] == "Material"
    # 子串匹配
    assert svc._find_entity_by_text(entities, "钙钛矿")["type"] == "Material"
    assert svc._find_entity_by_text(entities, "不存在") is None


async def test_extract_with_llm_placeholder(svc):
    r = await svc.extract_with_llm("任意文本")
    assert r["confidence"] == 0.85
    assert r["entities"] == []
    assert r["relations"] == []


async def test_process_document(svc, db):
    doc = Document(id="d1", title="T", file_path="x.pdf", uploaded_by="u1")
    db.add(doc)
    await db.flush()

    page = DocumentPage(id="p1", document_id="d1", page_number=1)
    db.add(page)
    await db.flush()

    el = DocumentElement(
        page_id="p1", element_type="text", bbox=[0, 0, 1, 1],
        content="钙钛矿材料具有优异的效率和稳定性",
    )
    db.add(el)
    await db.flush()

    r = await svc.process_document("d1", db)
    assert r["document_id"] == "d1"
    assert r["total_entities"] > 0


async def test_process_document_not_found(svc, db):
    with pytest.raises(ValueError):
        await svc.process_document("missing-id", db)