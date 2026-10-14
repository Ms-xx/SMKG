# -*- coding: utf-8 -*-
"""官方插件包。每个子包是一个标准插件，见 `others/PROJECT/08-插件化架构设计.md`。

插件约定：
- 子包内 `plugin.py` 必须暴露 `plugin = <Plugin 实例>`；
- 每个插件在 `app/plugins/<name>/plugin.py` 中自包含 Plugin 子类 + 服务实现；
- 跨模块解耦：消费者 via `registry.get(name)`，不 import 具体类。
"""
