# -*- coding: utf-8 -*-
"""实例寻址与原子热替换注册表。

- 读取（`get`）是热路径：同步内存 dict 直连，**永不经过 pluggy**。
- 替换（`atomic_swap`）先原子改表再停旧/启新，保证在途异步调用走旧实例自然完成、
  新调用立即取得新实例；新旧产资源可短暂重叠（文档明示，不做破坏性等待）。
- 注册/替换/卸载时向监听方派发 `on_change(name, old, new)`，供有依赖的插件做重握持。
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class ServiceRegistry:
    """按名注册业务服务实例，支持运行期原子替换/卸载。"""

    def __init__(self) -> None:
        self._services: dict[str, Any] = {}
        self._listeners: list[Callable[[str, Any | None, Any | None], None]] = []

    def add_listener(self, fn: Callable[[str, Any | None, Any | None], None]) -> None:
        self._listeners.append(fn)

    def _notify(self, name: str, old: Any | None, new: Any | None) -> None:
        for fn in self._listeners:
            try:
                fn(name, old, new)
            except Exception:  # pragma: no cover - 监听方失败不影响主流程
                logger.exception("registry listener error for %r", name)

    def set(self, name: str, instance: Any | None) -> None:
        """写入/清空（非原子语义，供启动期批量装配）。"""
        old = self._services.get(name)
        if instance is None:
            self._services.pop(name, None)
        else:
            self._services[name] = instance
        self._notify(name, old, instance)

    def get(self, name: str) -> Any:
        """动态寻址当前活动实例（热路径）。"""
        return self._services.get(name)

    def has(self, name: str) -> bool:
        return name in self._services

    def list(self) -> dict[str, Any]:
        return dict(self._services)

    def names(self) -> list[str]:
        return list(self._services)

    async def atomic_swap(self, name: str, new: Any, *, stop_old: bool = True) -> Any | None:
        """原子替换实例。

        流程：先替换表项并通知 → 调旧实例 on_stop（若 stop_old）。
        `on_start(new)` 由 PluginManager 在构造后接管（保证构造-激活-注册序）。
        返回被替换掉的旧实例（可能为 None）。
        """
        old = self._services.get(name)
        self._services[name] = new
        self._notify(name, old, new)
        if stop_old and old is not None and hasattr(old, "on_stop"):
            try:
                result = old.on_stop()
                if asyncio.iscoroutine(result):
                    await result
            except Exception:  # pragma: no cover - 清理失败不阻断替换
                logger.exception("atomic_swap on_stop failed for %r", name)
        return old

    def clear(self) -> None:
        self._services.clear()
