# -*- coding: utf-8 -*-
"""
图表描述服务（BLIP-2）单元测试
覆盖：模型/依赖缺失时安全降级、描述文本清理。
"""
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.chart_description_service import ChartDescriptionService


def test_describe_degrades_without_model(tmp_path):
    svc = ChartDescriptionService()
    svc.backend = "unavailable"  # 模拟模型缺失，避免触发真实下载
    assert svc.describe(str(tmp_path / "chart.png")) == ""


def test_clean_caption_strips():
    assert ChartDescriptionService._clean_caption("  a caption  ") == "a caption"
    assert ChartDescriptionService._clean_caption(None) == ""