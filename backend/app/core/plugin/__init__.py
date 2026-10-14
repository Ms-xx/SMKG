# -*- coding: utf-8 -*-
"""插件化架构核心框架。

统一插件注册、发现、生命周期、依赖解析、运行期热替换的契约与基础设施。
文档见 `others/PROJECT/08-插件化架构设计.md`。
"""
from app.core.plugin.base import Plugin, ServicePlugin
from app.core.plugin.manager import PluginManager
from app.core.plugin.registry import ServiceRegistry

__all__ = [
    "Plugin",
    "ServicePlugin",
    "PluginManager",
    "ServiceRegistry",
]
