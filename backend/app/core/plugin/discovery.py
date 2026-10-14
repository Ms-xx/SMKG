# -*- coding: utf-8 -*-
"""插件发现：扫描官方 + 第三方插件目录并归约为统一候选清单。

目录（见 `08-插件化架构设计.md`）：
- 官方：`backend/app/plugins/<name>/plugin.py`
- 第三方：`<PLUGIN_EXTRA_DIR>/<name>/plugin.py`（默认 `third_party_plugins/`）
发现只做**定位**，加载/激活由 `loader`/`manager` 负责。
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PluginCandidate:
    name: str
    module_file: str
    source: str  # "official" | "third"


def scan_plugins(official_dir: str, extra_dir: str) -> list[PluginCandidate]:
    candidates: list[PluginCandidate] = []
    for source, root in (("official", official_dir), ("third", extra_dir)):
        if not root or not os.path.isdir(root):
            continue
        for entry in sorted(os.listdir(root)):
            module_file = os.path.join(root, entry, "plugin.py")
            if os.path.isfile(module_file):
                candidates.append(PluginCandidate(entry, module_file, source))
    return candidates
