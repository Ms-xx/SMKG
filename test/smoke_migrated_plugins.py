# -*- coding: utf-8 -*-
"""冒烟验证：全部已迁移的官方服务插件可随 PluginManager 发现并激活。

- 不依赖真实 MySQL/模型：仅验证框架发现、拓扑激活、实例可寻址、健康状态、
  运行期 reload 原子替换（对轻量服务）与 unload。
- 覆盖 P1~P6 全部迁移插件（含 P5/P6 的图、多Agent、写作、复现性推荐等）。
- 运行：D:\\workapp\\Anaconda\\anaconda3\\envs\\SciMKG\\python.exe test/smoke_migrated_plugins.py
"""
import asyncio
import sys
import os

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, BACKEND)

from app.core.plugin.manager import PluginManager  # noqa: E402

# 全部官方迁移插件（实现位于 app/plugins/<name>/plugin.py 入口）
MIGRATED = [
    "ab_test",
    "active_learning",
    "active_learning_loop",
    "alert",
    "annotation",
    "annotation_agreement",
    "anomaly_detection",
    "auth",
    "calibration_drift",
    "chart_description",
    "citation_graph",
    "citation_graph_match",
    "citation_link",
    "citation_quality",
    "comment",
    "deduplication",
    "document",
    "entity_linking",
    "extraction",
    "figure_detection",
    "finetune",
    "formula",
    "future_work",
    "graph",
    "graph_metadata",
    "graph_snapshot",
    "graph_snapshot_service",
    "graphrag_integration",
    "layout",
    "llm",
    "model",
    "multi_agent",
    "multi_paper_compare",
    "ner",
    "node_type",
    "notification",
    "ocr",
    "operation_log",
    "paper_retrieval",
    "parsing",
    "performance",
    "permission",
    "realtime",
    "rebel",
    "reference",
    "relation_inference",
    "repo_availability",
    "repo_recommend",
    "semantic_search",
    "source_anchor",
    "statistics",
    "task",
    "text_to_cypher",
    "translation",
    "trend_analysis",
    "user",
    "version_management",
    "writing_assistant",
]


class _FakeSettings:
    PLUGIN_OFFICIAL_DIR = os.path.join(BACKEND, "app", "plugins")
    PLUGIN_EXTRA_DIR = os.path.join(BACKEND, "..", "third_party_plugins")
    # 官方插件路径由官方目录给出时，manager 用 importlib.import_module("app.plugins.<name>.plugin")
    PLUGIN_DISABLED = ""


async def main():
    mgr = PluginManager(_FakeSettings())
    await mgr.boot()
    listed = {p["name"]: p for p in mgr.list_plugins()}
    print("已发现插件:", sorted(listed.keys()))

    ok = True
    for name in MIGRATED:
        if name not in listed:
            print(f"[FAIL] 未发现迁移插件 {name}")
            ok = False
            continue
        ip = listed[name]
        inst = mgr.get(name)
        if not ip["active"]:
            print(f"[FAIL] {name} 未激活: {ip.get('error')}")
            ok = False
            continue
        if inst is None:
            print(f"[FAIL] {name} registry.get 为 None")
            ok = False
            continue
        health = getattr(inst, "health", lambda: {})()
        print(f"[OK] {name:18} active backend={health.get('backend','-')}")

    # 运行期热替换：ocr/parsing/formula 等轻量服务 reload 应拿到新实例
    for name in ["ocr", "parsing", "formula"]:
        if name in listed:
            before = mgr.get(name)
            await mgr.reload(name)
            after = mgr.get(name)
            mark = "OK" if after is not None and after is not before else "FAIL"
            print(
                f"[{mark}] reload {name}: 实例已替换 = {(after is not None and after is not before)}"
            )
            if after is None or after is before:
                ok = False

    # 卸载 parse（其依赖 ocr 不动）；再确认 registry 已清
    if "ocr" in listed:
        await mgr.unload("ocr")
        after_unload = mgr.get("ocr")
        print(
            f"[{'OK' if after_unload is None else 'FAIL'}] unload ocr: registry 已清空 = {after_unload is None}"
        )
        if after_unload is not None:
            ok = False

    await mgr.shutdown()
    print("\n结论:", "全部通过 ✅" if ok else "存在失败 ❌")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
