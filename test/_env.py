# -*- coding: utf-8 -*-
"""从集中化配置目录（config/）读取测试所需配置。

真实值只存在于 `config/*.env`（已被 `.gitignore` 排除），测试脚本不再硬编码口令；
环境变量优先于文件，便于 CI/本地覆盖。用法见各脚本，例如：

    from _env import ADMIN_USERNAME, ADMIN_PASSWORD, BASE_URL
"""
import os
from pathlib import Path

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def _load(path: Path) -> "dict[str, str]":
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, _, value = s.partition("=")
        out[key.strip()] = value.strip()
    return out


_ENV = {**_load(_CONFIG_DIR / "common.env"), **_load(_CONFIG_DIR / "backend.env")}


def get(key: str, default: str) -> str:
    return os.environ.get(key) or _ENV.get(key) or default


BASE_URL: str = get("TEST_BASE_URL", "http://127.0.0.1:8000")
ADMIN_USERNAME: str = get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD: str = get("ADMIN_PASSWORD", "admin123")
