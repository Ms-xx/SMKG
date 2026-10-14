# -*- coding: utf-8 -*-
"""pluggy 插件生命周期总线：扩展点（Hookspec）定义。

职责分工（与 `ServiceRegistry` 正交）：
- pluggy 负责 发现 / 生命周期钩子分派 / hook 调用排序；
- registry 负责 实例寻址与原子热替换，**读取不过 pluggy**。

仅"注册前/替换后/启动/停止"等生命周期事件经 pluggy 广播，供有依赖关系的插件重握持。
"""
from __future__ import annotations

import pluggy

# 全局唯一 project_name，与 pytest/shared 等隔离
PROJECT_NAME = "scientific-document-parser"

hookspec = pluggy.HookspecMarker(PROJECT_NAME)
hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


class PluginSpec:
    """核心框架声明的扩展点。插件通过 `@hookimpl` 提供实现。"""

    @hookspec
    def plugin_loaded(self, ctx: dict) -> None:
        """插件实例已构造并注册到 registry（ctx 含 name/instance）。"""

    @hookspec
    def plugin_unloaded(self, ctx: dict) -> None:
        """插件实例已被 registry 移除（ctx 含 name/old）。"""

    @hookspec
    def contribute_routers(self) -> list:
        """可选：贡献 APIRouter 列表。仅 `type == "router"` 的插件实现。"""

    @hookspec
    def on_app_startup(self, ctx: dict) -> None:
        """应用启动完成后通知（ctx 含 app）。"""

    @hookspec
    def on_app_shutdown(self, ctx: dict) -> None:
        """应用关闭前通知（ctx 含 app），用于释放资源。"""


def build_plugin_manager() -> pluggy.PluginManager:
    pm = pluggy.PluginManager(PROJECT_NAME)
    pm.add_hookspecs(PluginSpec)
    return pm
