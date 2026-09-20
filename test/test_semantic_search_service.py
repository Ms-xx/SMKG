# -*- coding: utf-8 -*-
"""语义搜索服务单元测试：搜索建议 + 分面搜索。均纯内存、零依赖。"""
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.semantic_search_service import (
    SemanticSearchService,
    tokenize,
    keyword_score,
    suggest,
    facet_search,
)

RECORDS = [
    {"name": "钙钛矿", "label": "Material", "description": "吸光材料"},
    {"name": "二氧化钛", "label": "Material", "description": "电子传输层"},
    {"name": "高效率", "label": "Property", "description": "性能指标"},
    {"name": "反溶剂法", "label": "Method", "description": "制备方法"},
]


def test_tokenize():
    assert tokenize("TiO2 钙钛矿") == ["tio2", "钙", "钛", "矿"]


def test_suggest_prefix_first():
    result = suggest("钙", ["氧化钙", "钙钛矿", "碳酸钙"])
    assert result[0] == "钙钛矿"


def test_suggest_substring():
    result = suggest("钛矿", ["二氧化钛", "钙钛矿"])
    assert "钙钛矿" in result


def test_suggest_empty_prefix():
    assert suggest("", ["钙钛矿"]) == []


def test_keyword_score_ranks_relevant_higher():
    assert keyword_score("钙钛矿", "钙钛矿吸光材料") > keyword_score("钙钛矿", "二氧化钛电子传输层")


def test_facet_search_facets():
    result = facet_search("", RECORDS)
    facet_map = {f["value"]: f["count"] for f in result["facets"]}
    assert facet_map == {"Material": 2, "Property": 1, "Method": 1}


def test_facet_search_ranks_top():
    result = facet_search("钙钛矿", RECORDS)
    assert result["results"][0]["name"] == "钙钛矿"


def test_service_suggest():
    svc = SemanticSearchService()
    out = svc.suggest("钙", ["钙钛矿", "氧化钙"])
    assert out["suggestions"] and out["suggestions"][0] == "钙钛矿"
    assert out["backend"] == "builtin"