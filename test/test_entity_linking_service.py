# -*- coding: utf-8 -*-
"""
实体链接服务单元测试
覆盖：文本归一化、相似度纯函数、消歧、本地同义词降级、外部查询禁用降级。
均不触发真实网络请求。
"""
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.entity_linking_service import (
    EntityLinkingService,
    normalize_text,
    levenshtein_ratio,
    jaccard_similarity,
    string_similarity,
)


def test_normalize_text():
    assert normalize_text("  钙钛矿-结构 ") == "钙钛矿 结构"
    assert normalize_text("  TiO2  ") == "tio2"
    assert normalize_text("") == ""


def test_levenshtein_ratio():
    assert levenshtein_ratio("钙钛矿", "钙钛矿") == 1.0
    assert levenshtein_ratio("", "") == 1.0
    assert 0.0 <= levenshtein_ratio("钙钛矿", "二氧化钛") < 1.0


def test_jaccard_similarity():
    assert jaccard_similarity("钙钛矿", "钙钛矿") == 1.0
    assert jaccard_similarity("abc", "xyz") == 0.0


def test_string_similarity():
    s = string_similarity("perovskite", "perovskite")
    assert s == 1.0
    assert string_similarity("钙钛矿", "不相关的词") < 0.5


def test_disambiguate_picks_alias_exact_match():
    svc = EntityLinkingService()
    candidates = [
        {"source": "wikidata", "id": "Q1", "label": "Perovskite",
         "description": "material", "aliases": ["calcium titanate"]},
        {"source": "wikidata", "id": "Q2", "label": "Perovskite solar cell",
         "description": "device", "aliases": []},
    ]
    best = svc.disambiguate("perovskite", candidates, "Material")
    assert best is not None
    assert best["id"] == "Q1"


def test_disambiguate_returns_none_for_empty():
    svc = EntityLinkingService()
    assert svc.disambiguate("x", [], None) is None


def test_link_entity_local_synonym_fallback():
    """无网络时，本地领域同义词表应直接返回规范结果（source=local）。"""
    svc = EntityLinkingService()
    svc.backend = "none"
    result = svc.link_entity("二氧化钛", "Material")
    assert result is not None
    assert result["canonical_name"] == "titanium dioxide"
    assert result["source"] == "local"
    assert "tio2" in result["aliases"]


def test_link_entity_degrades_without_backend():
    """禁用外部查询且本地无同义词时，返回未链接标记（source=none）。"""
    svc = EntityLinkingService()
    svc.backend = "none"
    result = svc.link_entity("某个未收录的实体名", "Material")
    assert result is not None
    assert result["source"] == "none"
    assert result["canonical_id"] is None


def test_link_entity_empty_text():
    svc = EntityLinkingService()
    assert svc.link_entity("", None) is None
    assert svc.link_entity("   ", None) is None


def test_link_entities_merges_synonyms():
    """同义词合并：同一 canonical_id 的实体应归并为一条，别名去重合并。"""
    svc = EntityLinkingService()
    svc.backend = "none"
    entities = [
        {"text": "二氧化钛", "entity_type": "Material"},
        {"text": "TiO2", "entity_type": "Material"},
    ]
    results = svc.link_entities(entities)
    # 两者指向同一 local canonical
    assert len(results) == 1
    assert results[0]["canonical_name"] == "titanium dioxide"
    assert set(results[0]["aliases"]) >= {"二氧化钛", "TiO2", "titanium dioxide"}