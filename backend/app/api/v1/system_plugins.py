# -*- coding: utf-8 -*-
"""插件管理 API（插件化架构）：运行期列表 / 加载 / 卸载 / 热替换 / 重扫。

- 仅管理员（`system:role:manage`）可操作；依赖 `app.state.plugin_manager`。
- 热替换语义：构造新实例 → registry 原子交换 → 启新停旧，不改核心代码、不重启进程。
- 重型模型插件（NER/OCR/微调）建议用 `reload`（冷换，见架构文档边界说明）。
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.permissions import require_permission
from app.core.plugin.manager import PluginManager

router = APIRouter()


def _get_manager(request: Request) -> PluginManager:
    mgr: PluginManager | None = getattr(request.app.state, "plugin_manager", None)
    if mgr is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="插件框架未启用（需设置 PLUGIN_ENABLED=true）",
        )
    return mgr


@router.get("/plugins")
async def list_plugins(
    request: Request,
    _: dict = Depends(require_permission("system:role:manage")),
):
    """列出已发现插件（含状态 / 依赖 / 类型 / 错误）。"""
    return {"plugins": _get_manager(request).list_plugins()}


@router.post("/plugins/rescan")
async def rescan_plugins(
    request: Request,
    _: dict = Depends(require_permission("system:role:manage")),
):
    """重扫第三方插件目录，返回新发现未注册的插件。"""
    return {"new": _get_manager(request).rescan()}


@router.post("/plugins/{name}/load")
async def load_plugin(
    name: str,
    request: Request,
    _: dict = Depends(require_permission("system:role:manage")),
):
    """运行期加载插件（未激活则激活）。"""
    mgr = _get_manager(request)
    try:
        ip = await mgr.load(name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"插件加载失败: {e}") from e
    return {"name": name, "active": ip.active, "version": ip.version}


@router.post("/plugins/{name}/unload")
async def unload_plugin(
    name: str,
    request: Request,
    _: dict = Depends(require_permission("system:role:manage")),
):
    """运行期卸载插件（registry 移除 + 资源清理）。"""
    mgr = _get_manager(request)
    try:
        await mgr.unload(name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"插件卸载失败: {e}") from e
    return {"name": name, "active": False}


@router.post("/plugins/{name}/reload")
async def reload_plugin(
    name: str,
    request: Request,
    _: dict = Depends(require_permission("system:role:manage")),
):
    """运行期热替换插件实例（消费者经 registry 立即切换，无需重启）。"""
    mgr = _get_manager(request)
    try:
        ip = await mgr.reload(name, fresh_code=True)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"插件热替换失败: {e}") from e
    return {
        "name": name,
        "active": ip.active,
        "version": ip.version,
        "reloaded": True,
    }


@router.get("/plugins/{name}/health")
async def plugin_health(
    name: str,
    request: Request,
    _: dict = Depends(require_permission("system:role:manage")),
):
    """查看插件健康状态（经协议 health()）。"""
    mgr = _get_manager(request)
    instance = mgr.registry.get(name)
    if instance is None:
        raise HTTPException(status_code=404, detail=f"插件未激活: {name}")
    health = instance.health() if hasattr(instance, "health") else {}
    return {"name": name, "health": health}
