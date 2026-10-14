"""
模型服务门面（插件化架构迁移：实现已迁至 `app/plugins/model/service.py`）。

- 兼容再导出：既有 `from app.services.model_service import ModelService` 不受影响。
- 运行期消费者应经 `registry.get("model")` 动态寻址。
"""

from __future__ import annotations

from app.plugins.model.service import ModelService

__all__ = ["ModelService"]
