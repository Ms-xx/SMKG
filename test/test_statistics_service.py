# -*- coding: utf-8 -*-
"""工作量统计服务单元测试（_build_stats 纯逻辑）。"""
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.statistics_service import StatisticsService


def test_build_stats_empty():
    svc = StatisticsService()
    user = {"id": "u1", "username": "alice", "full_name": "Alice", "role": "annotator"}
    out = svc._build_stats(user, {}, {})
    assert out["user_id"] == "u1"
    assert out["annotation_total"] == 0
    assert out["accuracy_rate"] is None
    assert out["task_total"] == 0


def test_build_stats_accuracy_rate():
    svc = StatisticsService()
    user = {"id": "u1", "username": "alice", "full_name": None, "role": "annotator"}
    ann = {"approved": 8, "rejected": 2, "submitted": 3, "draft": 1}
    task = {"completed": 5, "pending": 2, "failed": 1}
    out = svc._build_stats(user, ann, task)
    assert out["annotation_total"] == 14
    assert out["annotation_approved"] == 8
    assert out["annotation_rejected"] == 2
    assert out["annotation_pending"] == 3
    assert out["annotation_draft"] == 1
    assert out["accuracy_rate"] == 80.0
    assert out["task_total"] == 8
    assert out["task_completed"] == 5
    assert out["task_in_progress"] == 2
    assert out["task_failed"] == 1


def test_build_stats_no_reviewed():
    svc = StatisticsService()
    user = {"id": "u1", "username": "alice", "full_name": "Alice", "role": "annotator"}
    out = svc._build_stats(user, {"draft": 2}, {})
    assert out["accuracy_rate"] is None
    assert out["annotation_total"] == 2