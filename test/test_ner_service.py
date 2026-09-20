# -*- coding: utf-8 -*-
"""
命名实体识别服务（SciBERT NER）单元测试
覆盖：空文本短路、模型缺失安全降级、BIO→实体合并（纯函数）。
"""
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.ner_service import NERService, merge_bio_spans


def test_extract_empty_text():
    svc = NERService()
    assert svc.extract("") == []
    assert svc.extract("   ") == []


def test_extract_degrades_without_model():
    svc = NERService()
    svc.backend = "unavailable"  # 模拟无微调 checkpoint，避免触发真实下载
    assert svc.extract("钙钛矿太阳能电池具有高效率") == []


def test_merge_bio_spans():
    words = ["钙", "钛", "矿", "具有", "高", "效率"]
    tags = ["B-Material", "I-Material", "I-Material", "O", "B-Property", "I-Property"]
    starts = [0, 1, 2, 3, 5, 6]
    ends = [1, 2, 3, 5, 6, 8]

    entities = merge_bio_spans(words, tags, starts, ends)
    assert len(entities) == 2
    assert entities[0] == {"text": "钙钛矿", "type": "MATERIAL", "start": 0, "end": 3}
    assert entities[1] == {"text": "高效率", "type": "PROPERTY", "start": 5, "end": 8}