# -*- coding: utf-8 -*-
"""插件模块加载器。

热替换安全前提的实现：
- **每次加载用全新 module namespace**（以唯一名字写入 sys.modules，而非原地
  `importlib.reload`），从而 `class` 对象是全新标识；配合"消费方只持 Protocol +
  registry.get()、不持具体类"的契约，旧类/旧实例不会被外部持有，reload 才是真生效。
- 官方插件位于 app 包内，用常规包导入（供门面静态再导出溯源）；第三方插件以
  `_sc_plugin_<name>[_<counter>]` 唯一名逐字节加载。
"""
from __future__ import annotations

import importlib.util
import logging
import sys
import types

logger = logging.getLogger(__name__)


def import_module_by_path(abs_path: str, unique_name: str) -> types.ModuleType:
    """按文件路径 + 唯一模块名加载模块（全新 namespace，非 reload）。"""
    spec = importlib.util.spec_from_file_location(unique_name, abs_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot build spec for {abs_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = module
    spec.loader.exec_module(module)
    return module


def drop_module(unique_name: str) -> None:
    """卸载时移出 sys.modules，交由 GC 回收。"""
    sys.modules.pop(unique_name, None)


def get_plugin_instance(module: types.ModuleType):
    """从插件模块取 `plugin` 声明的 Plugin 实例。"""
    plugin = getattr(module, "plugin", None)
    if plugin is None:
        raise ValueError(
            f"插件模块 {module.__name__} 未暴露 `plugin`（应定义 `plugin = <Plugin>()`）"
        )
    return plugin
