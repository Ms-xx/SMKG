# -*- coding: utf-8 -*-
"""插件管理 API 端到端测试（经真实 FastAPI app + auth + 运行期热替换）。

复用 conftest 的 `token` fixture（role=admin → 通过 system:role:manage 权限校验）。
直接驱动 `app.main.app` 实例：挂上启用态 PluginManager 并手动 boot，避开 TestClient 生命周期。
"""
import httpx
import pytest

import app.main as main_mod

API_PREFIX = "/api/v1"


@pytest.mark.usefixtures("token")
class TestPluginApi:
    @pytest.mark.asyncio
    async def test_plugin_manage_flow(self, token):
        from app.core.config import settings
        from app.core.plugin.manager import PluginManager

        mgr = PluginManager(settings)
        await mgr.boot()
        main_mod.app.state.plugin_manager = mgr
        hdr = token(role="admin")

        transport = httpx.ASGITransport(app=main_mod.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            # 1. 列表：官方 + 第三方均被发现
            r = await c.get(f"{API_PREFIX}/system/plugins", headers=hdr)
            assert r.status_code == 200, r.text
            names = {p["name"] for p in r.json()["plugins"]}
            assert {"llm", "translation"} <= names
            assert "sample_stats" in names  # 第三方

            # 2. 健康检查
            r = await c.get(f"{API_PREFIX}/system/plugins/translation/health", headers=hdr)
            assert r.status_code == 200, r.text
            assert r.json()["name"] == "translation"

            # 3. 运行期热替换（不重启）：实例标识变化
            before = mgr.registry.get("translation")
            r = await c.post(f"{API_PREFIX}/system/plugins/translation/reload", headers=hdr)
            assert r.status_code == 200, r.text
            assert r.json()["reloaded"] is True
            assert mgr.registry.get("translation") is not before

            # 4. 卸载第三方
            r = await c.post(f"{API_PREFIX}/system/plugins/sample_stats/unload", headers=hdr)
            assert r.status_code == 200, r.text
            assert not mgr.registry.has("sample_stats")

            # 5. 重载第三方
            r = await c.post(f"{API_PREFIX}/system/plugins/sample_stats/load", headers=hdr)
            assert r.status_code == 200, r.text
            assert mgr.registry.has("sample_stats")

        # 收尾：换回未启用态，避免污染其他用例
        main_mod.app.state.plugin_manager = None

    @pytest.mark.asyncio
    async def test_plugin_api_requires_admin(self, token):
        # 非 admin 角色无权操作：auth 依赖在读取 manager 前先被阻断。
        from app.core.permissions import get_current_user_permissions

        async def _no_admin():
            return {"id": "u-guest", "role": "guest", "permissions": []}

        main_mod.app.dependency_overrides[get_current_user_permissions] = _no_admin
        try:
            transport = httpx.ASGITransport(app=main_mod.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
                r = await c.get(f"{API_PREFIX}/system/plugins", headers=token(role="guest"))
                assert r.status_code == 403, r.text
        finally:
            main_mod.app.dependency_overrides.clear()
