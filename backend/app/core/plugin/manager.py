# -*- coding: utf-8 -*-
"""插件管理器（PluginManager）：发现 → 依赖解析 → 激活 → 生命周期 → 运行期插拔。

组合关系（详见 `08-插件化架构设计.md`）：
- `pluggy.PluginManager`：扩展点/发现/生命周期 hook 分派 + hook 调用排序；
- `ServiceRegistry`：实例动态寻址与原子热替换（读取热路径不过 pluggy）；
- `deps.resolve_order`：插件间 requires DAG 的激活顺序与环检测。

本管理器把三者编排起来，是"不改核心/不重启即可换模块"的入口。
"""
from __future__ import annotations

import asyncio
import importlib
import logging
from dataclasses import dataclass, field
from typing import Any

from app.core.plugin.deps import validate
from app.core.plugin.discovery import PluginCandidate, scan_plugins
from app.core.plugin.hooks import build_plugin_manager
from app.core.plugin.loader import drop_module, get_plugin_instance, import_module_by_path
from app.core.plugin.registry import ServiceRegistry
from app.core.plugin.settings import build_plugin_settings

logger = logging.getLogger(__name__)


@dataclass
class InstalledPlugin:
    name: str
    module_file: str
    source: str
    plugin: Any
    module: Any
    unique_mod_name: str
    instance: Any = None
    active: bool = False
    error: str | None = None
    routers: list = field(default_factory=list)

    @property
    def type(self) -> str:
        return self.plugin.type

    @property
    def version(self) -> str:
        return self.plugin.version

    @property
    def requires(self) -> list[str]:
        return self.plugin.requires

    @property
    def config_prefix(self) -> str:
        return self.plugin.config_prefix

    def info(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "type": self.type,
            "source": self.source,
            "active": self.active,
            "enabled": self.active or self.error is not None,
            "requires": list(self.requires),
            "optional_requires": list(self.plugin.optional_requires),
            "config_prefix": self.config_prefix,
            "has_routers": bool(self.routers),
            "error": self.error,
        }


class PluginManager:
    def __init__(
        self,
        settings: Any,
        registry: ServiceRegistry | None = None,
        pm=None,
    ) -> None:
        self.settings = settings
        self.registry = registry or ServiceRegistry()
        self._pm = pm or build_plugin_manager()
        self._plugins: dict[str, InstalledPlugin] = {}
        self._booted = False

    @property
    def pm(self):
        return self._pm

    # ── 路径 ──
    @property
    def official_dir(self) -> str:
        return getattr(self.settings, "PLUGIN_OFFICIAL_DIR", "") or ""

    @property
    def extra_dir(self) -> str:
        return getattr(self.settings, "PLUGIN_EXTRA_DIR", "") or ""

    def discover(self) -> list[PluginCandidate]:
        return scan_plugins(self.official_dir, self.extra_dir)

    # ── 导入 ──
    def _import(self, cand: PluginCandidate):
        if cand.source == "official":
            unique = f"app.plugins.{cand.name}.plugin"
            module = importlib.import_module(unique)
        else:
            unique = f"_sc_plugin_{cand.name}"
            module = import_module_by_path(cand.module_file, unique)
        plugin = get_plugin_instance(module)
        return module, plugin, unique

    # ── 生命周期 ──
    def _plugin_settings(self, ip: InstalledPlugin) -> Any:
        cls = getattr(ip.plugin, "settings_cls", None)
        if cls is None or not ip.config_prefix:
            return None
        return build_plugin_settings(ip.config_prefix, cls)

    async def _activate_async(self, ip: InstalledPlugin) -> None:
        instance = ip.plugin.create(self.registry, self._plugin_settings(ip))
        ip.instance = instance
        self.registry.set(ip.name, instance)
        if hasattr(instance, "on_start"):
            result = instance.on_start()
            if asyncio.iscoroutine(result):
                await result
        ip.active = True
        ip.error = None
        self._pm.register(ip.module)
        self._pm.hook.plugin_loaded(ctx={"name": ip.name, "instance": instance})

    async def boot(self) -> None:
        """发现 + 依赖解析 + 按拓扑激活（启动调用一次）。"""
        self._booted = True
        disabled = self._parse_disabled()
        candidates = self.discover()
        for cand in candidates:
            if cand.name in disabled:
                logger.info("skip disabled plugin: %s", cand.name)
                continue
            try:
                module, plugin, unique = self._import(cand)
            except Exception as e:
                logger.error("import plugin %s failed: %s", cand.name, e, exc_info=True)
                continue
            self._plugins[cand.name] = InstalledPlugin(
                name=cand.name,
                module_file=cand.module_file,
                source=cand.source,
                plugin=plugin,
                module=module,
                unique_mod_name=unique,
            )
        # 依赖图激活顺序
        names = [p.name for p in self._plugins.values()]
        graph = {p.name: list(p.requires) for p in self._plugins.values()}
        ok, order, rings = validate(graph, names)
        if not ok:
            raise RuntimeError(
                f"插件依赖存在环：{rings}；请修正每个插件的 requires（需求文档：激活顺序先依赖后依赖方）"
            )
        for name in order:
            ip = self._plugins[name]
            try:
                await self._activate_async(ip)
            except Exception as e:
                logger.error("activate plugin %s failed: %s", name, e, exc_info=True)
            else:
                logger.info("plugin activated: %s (%s)", name, ip.version)

    def _parse_disabled(self) -> set[str]:
        raw = getattr(self.settings, "PLUGIN_DISABLED", "") or ""
        if isinstance(raw, list):
            return {str(x).strip() for x in raw}
        return {x.strip() for x in str(raw).split(",") if x.strip()}

    async def shutdown(self) -> None:
        """逆序停用所有活动插件（依赖方先于其依赖被停）。"""
        order = list(self._plugins.keys())
        for name in reversed(order):
            ip = self._plugins.get(name)
            if not ip or not ip.active:
                continue
            await self.unload(name)

    async def _build_instance(self, ip: InstalledPlugin, fresh_code: bool) -> Any:
        if fresh_code and ip.source == "third":
            # 第三方插件支持代码级热替换：重载全新模块 namespace
            module_file = ip.module_file
            unique = f"_sc_plugin_{ip.name}_r{getattr(ip, '_rev', 0)}"
            module = import_module_by_path(module_file, unique)
            plugin = get_plugin_instance(module)
            ip.plugin = plugin
            ip.module = module
            importlib.invalidate_caches()
        instance = ip.plugin.create(self.registry, self._plugin_settings(ip))
        return instance

    async def load(self, name: str) -> InstalledPlugin:
        ip = self._plugins.get(name)
        if ip is None:
            # 尝试按已发现的外挂插件加载（未激活）
            cand = next((c for c in self.discover() if c.name == name), None)
            if cand is None:
                raise ValueError(f"未发现插件: {name}")
            module, plugin, unique = self._import(cand)
            ip = InstalledPlugin(
                name=cand.name,
                module_file=cand.module_file,
                source=cand.source,
                plugin=plugin,
                module=module,
                unique_mod_name=unique,
            )
            self._plugins[name] = ip
        if ip.active:
            return ip
        await self._activate_async(ip)
        return ip

    async def unload(self, name: str) -> None:
        ip = self._plugins.get(name)
        if ip is None:
            raise ValueError(f"未发现插件: {name}")
        if not ip.active:
            return
        if ip.instance is not None and hasattr(ip.instance, "on_stop"):
            result = ip.instance.on_stop()
            if asyncio.iscoroutine(result):
                await result
        self.registry.set(name, None)
        self._pm.unregister(ip.module)
        drop_module(ip.unique_mod_name)
        ip.active = False
        ip.instance = None
        self._pm.hook.plugin_unloaded(ctx={"name": name, "old": ip})

    async def reload(self, name: str, *, fresh_code: bool = True) -> InstalledPlugin:
        """运行期热替换：构造新实例 → registry 原子交换 → 启动新实例。"""
        ip = self._plugins.get(name)
        if ip is None:
            raise ValueError(f"未发现插件: {name}")
        fresh = await self._build_instance(ip, fresh_code=fresh_code)
        old = await self.registry.atomic_swap(name, fresh, stop_old=True)
        if hasattr(fresh, "on_start"):
            result = fresh.on_start()
            if asyncio.iscoroutine(result):
                await result
        ip.instance = fresh
        ip.active = True
        ip.error = None
        ip._rev = getattr(ip, "_rev", 0) + 1
        self._pm.hook.plugin_loaded(
            ctx={"name": name, "instance": fresh, "old": old, "reloaded": True}
        )
        return ip

    def rescan(self) -> list[dict[str, Any]]:
        """重扫发现新第三方插件；返回新发现（未注册）清单。"""
        found = []
        for cand in self.discover():
            if cand.source == "third" and cand.name not in self._plugins:
                found.append({"name": cand.name, "module_file": cand.module_file})
        return found

    def list_plugins(self) -> list[dict[str, Any]]:
        return [ip.info() for ip in self._plugins.values()]

    def get(self, name: str) -> Any:
        return self.registry.get(name)

    # ── 路由汇总（核心挂载用） ──
    def collect_routers(self):
        routers = []
        for ip in self._plugins.values():
            if getattr(ip.plugin, "type", "") == "router":
                try:
                    r = ip.plugin.router()
                    if r is not None:
                        routers.append((ip.name, r))
                except Exception as e:  # pragma: no cover
                    logger.warning("collect router %s failed: %s", ip.name, e)
        return routers
