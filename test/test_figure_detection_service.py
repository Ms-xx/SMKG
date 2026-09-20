# -*- coding: utf-8 -*-
"""
图表/公式检测服务（YOLOv8）单元测试
覆盖：无权重时安全降级、权重文件查找。
"""
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.figure_detection_service import FigureDetectionService


def test_detect_degrades_without_weights(tmp_path):
    svc = FigureDetectionService()
    # 未放置 YOLOv8 权重时应安全降级，返回空列表而非抛异常
    assert svc.detect(str(tmp_path / "page.png")) == []


def test_find_weights_empty_dir(tmp_path):
    svc = FigureDetectionService()
    from app.core import config

    original = config.settings.FIGURE_DETECT_MODEL_PATH
    config.settings.FIGURE_DETECT_MODEL_PATH = str(tmp_path)
    try:
        assert svc._find_weights() is None
    finally:
        config.settings.FIGURE_DETECT_MODEL_PATH = original


def test_find_weights_finds_pt(tmp_path):
    svc = FigureDetectionService()
    weights = tmp_path / "yolov8_doclaynet.pt"
    weights.write_bytes(b"dummy")

    from app.core import config

    original = config.settings.FIGURE_DETECT_MODEL_PATH
    config.settings.FIGURE_DETECT_MODEL_PATH = str(tmp_path)
    try:
        assert svc._find_weights() == str(weights)
    finally:
        config.settings.FIGURE_DETECT_MODEL_PATH = original