# -*- coding: utf-8 -*-
"""统一日志配置。

- 输出到 stdout（12-factor），便于容器/Filebeat 采集。
- `LOG_JSON=true` 时输出 JSON 结构化日志（供 ELK 解析），依赖 python-json-logger；
  缺失时自动降级为纯文本格式。
"""
import logging
import sys

from app.core.config import settings


def setup_logging() -> None:
    """配置根日志器，输出统一格式（文本或 JSON），可选追加日志文件。"""
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    formatter = _build_formatter()

    # 清空已有 handler，避免重复输出
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)
        h.close()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root.setLevel(level)
    root.addHandler(handler)

    # 可选：追加 JSON 日志文件（供 Filebeat/ELK 采集），LOG_FILE 留空则不启用
    if settings.LOG_FILE:
        try:
            file_handler = logging.FileHandler(settings.LOG_FILE)
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
        except Exception:  # pragma: no cover - 路径不可写时降级
            root.warning("无法写入日志文件 %s，仅输出到 stdout", settings.LOG_FILE)


def _build_formatter() -> logging.Formatter:
    """按 LOG_JSON 返回 JSON 或文本格式器；依赖缺失时降级为文本。"""
    if not settings.LOG_JSON:
        return logging.Formatter(settings.LOG_FORMAT)
    try:
        from pythonjsonlogger.json import JsonFormatter  # type: ignore
    except ImportError:  # pragma: no cover - 旧版本兼容
        from pythonjsonlogger.jsonlogger import JsonFormatter  # type: ignore
    return JsonFormatter(settings.LOG_FORMAT)