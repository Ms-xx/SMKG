# -*- coding: utf-8 -*-
"""插件框架单元测试：拓扑/环、注册表热替换、前缀配置、manager 生命周期。

运行：SciMKG python -m pytest test/test_plugin_framework.py -q
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))


from app.core.plugin.deps import resolve_order
from app.core.plugin.manager import InstalledPlugin, PluginManager
from app.core.plugin.registry import ServiceRegistry
from app.core.plugin.settings import build_plugin_settings


# ── 1. 依赖拓扑：顺序 + 环检测 ─────────────────────────────────────


def test_topo_requires_first():
    order, rings = resolve_order({"a": [], "b": ["a"], "c": ["a", "b"]})
    assert rings == []
    assert order.index("a") < order.index("b") < order.index("c")


def test_topo_stable_by_declaration():
    order, _ = resolve_order({"x": [], "y": ["x"], "z": []}, name_order=["x", "z", "y"])
    assert order.index("x") < order.index("y")


def test_topo_cycle_detected():
    order, rings = resolve_order({"a": ["b"], "b": ["a"], "c": []})
    # c 无依赖先出队；a/b 成环留在 ring
    assert "a" in rings and "b" in rings
    assert set(order) == {"c"}


def test_topo_ignores_unknown_dependency():
    order, rings = resolve_order({"a": ["missing"], "b": ["a"]})
    assert rings == []
    assert order == ["a", "b"]


# ── 2. 注册表：动态寻址 + 原子替换 ────────────────────────────────


class _Svc:
    def __init__(self, tag):
        self.tag = tag
        self.stopped = False

    async def on_start(self):
        pass

    async def on_stop(self):
        self.stopped = True

    def echo(self):
        return self.tag


def test_registry_get_set_swap():
    reg = ServiceRegistry()
    reg.set("demo", _Svc("v1"))
    assert reg.get("demo").echo() == "v1"
    assert reg.has("demo")
    old = asyncio.run(reg.atomic_swap("demo", _Svc("v2")))
    assert old.echo() == "v1"
    assert old.stopped is True  # 旧实例 on_stop 被调用
    assert reg.get("demo").echo() == "v2"
    reg.set("demo", None)
    assert not reg.has("demo")


def test_registry_listener_notified():
    reg = ServiceRegistry()
    events = []
    reg.add_listener(
        lambda name, old, new: events.append(
            (name, old.echo() if old else None, new.echo() if new else None)
        )
    )
    reg.set("demo", _Svc("a"))

    async def _swap():
        await reg.atomic_swap("demo", _Svc("b"))

    asyncio.run(_swap())
    assert ("demo", "a", "b") in events
    assert ("demo", None, "a") in events


# ── 3. 前缀配置扇出 ──────────────────────────────────────────────


def test_prefix_fanout():
    env = {"LLM_ENABLED": "true", "LLM_MODEL": "qwen", "OCR_ENGINE": "paddle"}
    out = build_plugin_settings("LLM_", _DemoSettings, env)
    assert isinstance(out, _DemoSettings)
    assert out.enabled is True
    assert out.model == "qwen"


def test_prefix_none_when_blank():
    assert build_plugin_settings("", _DemoSettings, {}) is None


class _DemoSettings:
    def __init__(self, enabled: bool = False, model: str = ""):
        # 模拟 pydantic 对 env 字符串的布尔强制
        if isinstance(enabled, str):
            enabled = enabled.strip().lower() in ("true", "1")
        self.enabled = enabled
        self.model = model


# ── 4. manager：激活/卸载/热替换（内存插件，无盘依赖） ─────────────


class _FakePlugin:
    name = "demo"
    version = "1.0.0"
    type = "service"
    config_prefix = ""
    requires = []
    optional_requires = []
    settings_cls = None

    def __init__(self, tag):
        self.tag = tag
        self._n = 0

    def create(self, registry, settings):
        self._n += 1
        return _Svc(f"{self.tag}{self._n}")


def _make_manager():
    registry = ServiceRegistry()

    class Mgr(PluginManager):
        pass

    class _FakeSettings:
        PLUGIN_DISABLED = ""

    manager = Mgr(_FakeSettings(), registry=registry)
    return manager


async def _arun(coro):
    return await coro


def test_manager_activate_and_get():
    manager = _make_manager()
    ip = _register(manager, _make_ip(_FakePlugin("v1")))
    asyncio.run(manager._activate_async(ip))
    assert manager.get("demo").echo() == "v11"
    assert ip.active


def test_manager_reload_swap_consumer_view():
    manager = _make_manager()
    ip = _register(manager, _make_ip(_FakePlugin("v1")))
    asyncio.run(manager._activate_async(ip))
    # 消费者持 registry 引用，读到的是活动实例
    consumer_ref = manager.registry.get("demo")
    assert consumer_ref.echo() == "v11"
    # 热替换
    asyncio.run(manager.reload("demo", fresh_code=False))
    assert consumer_ref is not manager.registry.get("demo")  # 新实例
    assert manager.get("demo").echo() == "v12"


def test_manager_unload_clears():
    manager = _make_manager()
    ip = _register(manager, _make_ip(_FakePlugin("v1")))
    asyncio.run(manager._activate_async(ip))
    asyncio.run(manager.unload("demo"))
    assert not manager.registry.has("demo")
    assert not ip.active


def _make_ip(plugin):
    return InstalledPlugin(
        name=plugin.name,
        module_file="<fake>",
        source="official",
        plugin=plugin,
        module=object(),
        unique_mod_name="fake",
    )


def _register(manager, ip):
    manager._plugins[ip.name] = ip
    return ip


# ── 5. 全量冒烟：manager.boot 读取真实配置对象 ─────────────────────


def test_settings_defaults():
    from app.core.config import settings as s

    assert hasattr(s, "PLUGIN_ENABLED")
    assert hasattr(s, "PLUGIN_EXTRA_DIR")
    assert s.PLUGIN_OFFICIAL_DIR.endswith("plugins")
