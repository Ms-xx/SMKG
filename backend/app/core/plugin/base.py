# -*- coding: utf-8 -*-
"""插件统一契约：元数据 + 工厂 + 运行时服务协议。

设计约定（供插件作者遵循）：
- 每个官方插件位于 `backend/app/plugins/<name>/`，子包内 `plugin.py` 暴露
  `plugin = <Plugin子类实例>()`；第三方插件位于 `third_party_plugins/<name>/`，同规约。
- **跨模块解耦铁律**：消费者既不 `from 插件模块 import 具体类`、也不持单例引用，
  只依赖 `provides` 声明的 `Protocol`，并在运行时经 `registry.get(name)` 动态寻址。
  这是"运行期已加载实例可被原子替换"的正确性前提——否则旧类/旧实例会被外部持有，
  reload 退化为死切换。
"""
from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:  # pragma: no cover - 仅类型提示
    from fastapi import APIRouter

    from app.core.plugin.registry import ServiceRegistry


class ServicePlugin(Protocol):
    """插件供给侧暴露的运行时服务协议。

    跨插件消费者一律依赖本协议（而非具体类），从而在 `registry.atomic_swap` 后
    透明地切换到新实例。`ServicePlugin` 只要求三项稳定方法。
    """

    async def on_start(self) -> None:  # pragma: no cover - 协议方法
        """插件激活时回调（构造重型资源等）。"""
        ...

    async def on_stop(self) -> None:  # pragma: no cover - 协议方法
        """插件停用时清理（释放连接/句柄等）。不得抛未处理异常。"""
        ...

    def health(self) -> dict[str, Any]:  # pragma: no cover - 协议方法
        """返回健康状态快照，供 `/system/plugins/{name}/health` 与门面展示。"""
        ...


class Plugin(abc.ABC):
    """插件元数据 + 工厂的统一接口契约（一个插件 = 一个 Plugin 子类）。"""

    # 注册名（唯一），如 "llm"、"ocr"；也是 registry 寻址键
    name: str = ""
    version: str = "1.0.0"
    # 每插件独立配置空间前缀（大写，匹配 config/*.env 的 case_sensitive 键），如 "LLM_"
    config_prefix: str = ""
    # 必选依赖插件名：激活顺序按 requires 拓扑先依赖后依赖方
    requires: list[str] = []
    # 可选依赖插件名：缺失不阻断，消费方 registry.get() 得 None 自行降级
    optional_requires: list[str] = []
    # 插件类型：service=纯服务（运行期可真热替换）；router=贡献路由（走网关派发）
    type: str = "service"
    # 对外暴露的服务协议（消费者类型提示用）；注册为 None 则视为"无对外服务型插件"
    provides: type[Protocol] | None = None
    # 迁移自 app/services/<name> 的原始模块，供门面做静态再导出溯源（文档用途）
    legacy_module: str | None = None
    # 插件独立配置模型（pydantic BaseSettings 子类）；与 config_prefix 配合，
    # 由 build_plugin_settings 按前缀扇出注入。None = 插件自行读全局 settings。
    settings_cls: type[Any] | None = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

    @abc.abstractmethod
    def create(self, registry: "ServiceRegistry", settings: Any) -> Any:
        """工厂：构造（尚未激活的）服务实例。

        - `registry`: 全局 `ServiceRegistry`，跨服务调用在此动态寻址。
        - `settings`: 该插件前缀独立配置（由 `build_plugin_settings` 产生；无前缀时
          传入 None，插件可自行读取全局 settings）。
        返回一个实现 `ServicePlugin` 协议的对象。
        """
        raise NotImplementedError

    def router(self) -> "APIRouter | None":
        """可选：返回 APIRouter。仅 `type == "router"` 时生效，走网关派发。

        若返回 None 且 type == "router"，该插件降级为纯 service 型。
        """
        return None

    def describe(self) -> dict[str, Any]:
        """插件自述（列表接口展示用）。"""
        return {
            "name": self.name,
            "version": self.version,
            "type": self.type,
            "config_prefix": self.config_prefix,
            "requires": list(self.requires),
            "optional_requires": list(self.optional_requires),
            "legacy_module": self.legacy_module,
        }
