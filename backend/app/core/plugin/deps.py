# -*- coding: utf-8 -*-
"""插件依赖解析与加载顺序。

- 用基于度数的 Kahn 拓扑排序（按 manifest 声明顺序保持确定性），决定**激活顺序**：
  先依赖、后依赖方。此为跨插件 DAG 需求；pluggy 的 tryfirst/trylast 只管单 hook 的
  调用序，不替代本模块。
- **环检测**：排序后若入队数 < 总数即存在环，返回环上节点集合，由调用方 fail-fast。
- 必选依赖 `requires` 缺失/成环 → 阻断；可选依赖 `optional_requires` 不进拓扑（缺失
  由消费方 registry.get() 得 None 降级）。
"""
from __future__ import annotations

from collections import deque


def resolve_order(
    plugins: dict[str, list[str]], name_order: list[str] | None = None
) -> tuple[list[str], list[str]]:
    """返回 (拓扑激活顺序, 环上节点名列表)。

    参数：
    - `plugins`: {插件名: 必选依赖插件名列表}
    - `name_order`: 用于稳定排序的声明顺序；缺省用 plugins 的插入序。
    环上节点返回为这些节点名（可能含多个互成环的组件，统一列全）。
    """
    names = name_order or list(plugins)
    pending = {n: set(plugins.get(n, [])) & set(names) for n in names}
    if not names:
        return [], []

    indegree = {n: len(pending[n]) for n in names}
    adj: dict[str, list[str]] = {n: [] for n in names}
    for n in names:
        for dep in pending[n]:
            # 依赖不在已声明插件集合内：视为外部缺失，不影响本图（由上层判定缺失）
            if dep in indegree:
                adj[dep].append(n)

    ready = deque([n for n in names if indegree[n] == 0])
    order: list[str] = []
    while ready:
        cur = ready.popleft()
        order.append(cur)
        for child in adj[cur]:
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)

    remaining = [n for n in names if n not in set(order)]
    return order, remaining


def find_cycle_members(
    plugins: dict[str, list[str]], name_order: list[str] | None = None
) -> list[str]:
    """仅用于诊断：返回参与成环的插件名。"""
    _, remaining = resolve_order(plugins, name_order)
    return remaining


def validate(
    plugins: dict[str, list[str]], name_order: list[str] | None = None
) -> tuple[bool, list[str], list[str]]:
    """校验并返回 (是否无环, 激活顺序, 环成员)。供启动/CI fail-fast。"""
    order, rings = resolve_order(plugins, name_order)
    return (not rings), order, rings
