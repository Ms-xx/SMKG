# -*- coding: utf-8 -*-
"""每插件独立配置空间：从合并 env 按前缀扇出注入插件的 pydantic settings。

遵循既有惯例：
- 配置集中在 `config/` 目录（common.env / backend.env），**不引入插件独立 .env**；
- 核心在**单一来源**加载合并 env dict（复用 python-dotenv），插件模型只消费各自
  `config_prefix` 前缀下的键，与全局 `Settings` 无重复加载、无值冲突；
- reload 时用同一 dict 快**重建**插件 settings（不回读文件）。
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import dotenv

from app.core.config import CONFIG_DIR


@lru_cache(maxsize=1)
def merged_env() -> dict[str, str]:
    """合并 config/common.env + config/backend.env 为一个大写键字典（后端优先）。"""
    common = os.path.join(CONFIG_DIR, "common.env")
    backend = os.path.join(CONFIG_DIR, "backend.env")
    merged: dict[str, str] = {}
    for path in (common, backend):
        if os.path.exists(path):
            merged.update(dotenv.dotenv_values(path))
    return merged


def build_plugin_settings(
    prefix: str, model_cls: type[Any], env: dict[str, str] | None = None
) -> Any:
    """按 `prefix` 从 env 抽取键注入 `model_cls`，返回其实例。

    - 无前缀 → 返回 None（插件自行读取全局 settings）；
    - 键匹配大小写不敏感（前缀统一转大写，与 case_sensitive 环境键对齐），
      抽取后去掉前缀作为模型字段。
    """
    if not prefix:
        return None
    prefix = prefix.upper()
    src = env if env is not None else merged_env()
    # 抽取前缀并统一小写为模型字段名（pydantic 直传 kwargs 按字段名匹配）
    sub = {k[len(prefix) :].lower(): v for k, v in src.items() if k.upper().startswith(prefix)}
    return model_cls(**sub)
