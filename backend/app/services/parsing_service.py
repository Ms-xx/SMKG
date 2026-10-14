"""
文档解析服务门面（插件化架构迁移：实现已迁至 `app/plugins/parsing/plugin.py`）。

- 兼容再导出：既有 `from app.services.parsing_service import ParsingService`
  不受影响（门面符号与插件注册实现同源）。
- 运行期热替换消费者应经 `registry.get("parsing")` 动态寻址。
"""

from __future__ import annotations

from app.plugins.parsing.plugin import ParsingService, parsing_service

__all__ = ["ParsingService", "parsing_service"]
