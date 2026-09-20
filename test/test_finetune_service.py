# -*- coding: utf-8 -*-
"""
领域微调服务（finetune_service）单元测试
覆盖：BIO 映射、训练集导出、标签索引、CoNLL 导出、token 级指标、多数类基线降级、
以及 version_management_service 的真实微调闭环（强制走基线，避免下载真实模型）。
"""
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.finetune_service import (
    FinetuneService,
    build_bio_examples,
    entities_to_char_bio,
    export_ner_training_set,
    label_index,
    to_conll,
    token_level_metrics,
)
from app.services.version_management_service import VersionManagementService


class _AnnotationRow:
    """模拟 SQLAlchemy Annotation ORM 行（仅含 content 属性）。"""

    def __init__(self, content):
        self.content = content


def _force_baseline(monkeypatch):
    """强制 _probe_peft 返回 False，使训练确定性走多数类基线。"""
    monkeypatch.setattr(FinetuneService, "_probe_peft", lambda self: False)


def test_entities_to_char_bio():
    text = "钙钛矿电池"
    entities = [{"text": "钙钛矿", "type": "Material", "start": 0, "end": 3}]
    tags = entities_to_char_bio(text, entities)
    assert tags == ["B-MATERIAL", "I-MATERIAL", "I-MATERIAL", "O", "O"]


def test_entities_to_char_bio_no_entity():
    assert entities_to_char_bio("abc", []) == ["O", "O", "O"]


def test_export_training_set_from_dict():
    records = [
        {"content": {"text": "钙钛矿电池", "entities": [{"type": "M", "start": 0, "end": 3}]}},
        {"content": {"text": "no entities", "entities": []}},
        {"content": {}},  # 无 text，应被跳过
    ]
    samples = export_ner_training_set(records)
    assert len(samples) == 2
    assert samples[0]["text"] == "钙钛矿电池"
    assert samples[1]["entities"] == []


def test_export_training_set_from_orm():
    row = _AnnotationRow({"text": "石墨烯", "entities": [{"type": "Material", "start": 0, "end": 3}]})
    samples = export_ner_training_set([row])
    assert samples == [{"text": "石墨烯", "entities": [{"type": "Material", "start": 0, "end": 3}]}]


def test_build_bio_examples():
    samples = [{"text": "钙钛矿", "entities": [{"type": "M", "start": 0, "end": 3}]}]
    exs = build_bio_examples(samples)
    assert exs[0]["char_tags"] == ["B-M", "I-M", "I-M"]


def test_label_index_O_first():
    label2id, id2label = label_index(["B-X", "O", "I-X", "B-Y"])
    assert label2id["O"] == 0
    assert id2label[0] == "O"
    assert set(label2id.keys()) == {"O", "B-X", "B-Y", "I-X"}


def test_to_conll_format():
    exs = [{"text": "ab", "char_tags": ["B-X", "O"]}]
    assert to_conll(exs) == "a\tB-X\nb\tO\n"


def test_token_level_metrics_perfect():
    assert token_level_metrics(["B-X", "I-X"], ["B-X", "I-X"])["f1"] == 1.0


def test_token_level_metrics_all_O_zero_f1():
    m = token_level_metrics(["B-X", "I-X"], ["O", "O"])
    assert m["f1"] == 0.0 and m["precision"] == 0.0 and m["recall"] == 0.0


def test_token_level_metrics_mixed():
    m = token_level_metrics(["B-X", "O", "B-Y"], ["B-X", "B-Y", "B-Y"])
    assert 0.0 < m["f1"] < 1.0


def test_token_level_metrics_empty():
    assert token_level_metrics([], []) == {
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "tp": 0,
        "fp": 0,
        "fn": 0,
        "support": 0,
    }


def test_train_ner_baseline_empty(monkeypatch, tmp_path):
    _force_baseline(monkeypatch)
    out = FinetuneService().train_ner([], output_dir=str(tmp_path / "m"))
    assert out["backend"] == "baseline"
    assert out["samples"] == 0
    assert out["metrics"]["f1"] == 0.0


def test_train_ner_baseline_majority(monkeypatch, tmp_path):
    _force_baseline(monkeypatch)
    records = [{"content": {"text": "钙钛矿材料", "entities": [{"type": "M", "start": 0, "end": 3}]}}]
    out = FinetuneService().train_ner(records, output_dir=str(tmp_path / "m"))
    assert out["backend"] == "baseline"
    assert out["samples"] == 1
    assert "B-M" in out["labels"]


def test_run_finetune_pipeline_baseline(monkeypatch):
    _force_baseline(monkeypatch)
    svc = VersionManagementService()
    records = [
        {"content": {"text": "钙钛矿电池", "entities": [{"type": "M", "start": 0, "end": 3}]}}
    ]
    run = svc.run_finetune_pipeline("ner", records=records, trigger_reason="manual", f1_threshold=0.0)
    assert run["status"] == "completed"
    steps = [s["step"] for s in run["steps"]]
    assert steps == ["data_prep", "training", "evaluation", "registration", "deployment"]
    # F1 阈值 0：应晋升 Production
    assert svc.list_models()["ner"][-1]["stage"] == "production"


def test_run_finetune_pipeline_stays_staging(monkeypatch):
    _force_baseline(monkeypatch)
    svc = VersionManagementService()
    records = [
        {"content": {"text": "钙钛矿电池", "entities": [{"type": "M", "start": 0, "end": 3}]}}
    ]
    run = svc.run_finetune_pipeline("ner", records=records, f1_threshold=1.0)
    assert run["status"] == "completed"
    assert svc.list_models()["ner"][-1]["stage"] == "staging"


def test_run_finetune_pipeline_empty_no_crash(monkeypatch):
    _force_baseline(monkeypatch)
    svc = VersionManagementService()
    run = svc.run_finetune_pipeline("ner", records=[], f1_threshold=0.0)
    assert run["status"] == "completed"
    # 无有效样本时基线指标 f1=0，但仍完成注册（staging）
    assert svc.list_models()["ner"][-1]["stage"] == "staging"