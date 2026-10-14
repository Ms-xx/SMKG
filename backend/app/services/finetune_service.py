# -*- coding: utf-8 -*-
"""
领域微调服务门面（插件化架构迁移：实现已迁至 `app/plugins/finetune/service.py`）。

- 兼容再导出：既有 `from app.services.finetune_service import FinetuneService`、
  `finetune_service` 及纯函数符号不受影响。
- 运行期消费者应经 `registry.get("finetune")` 动态寻址。
"""

from __future__ import annotations

from app.plugins.finetune.service import (
    FinetuneService,
    build_bio_examples,
    entities_to_char_bio,
    export_ner_training_set,
    finetune_service,
    label_index,
    to_conll,
    token_level_metrics,
)

__all__ = [
    "FinetuneService",
    "finetune_service",
    "entities_to_char_bio",
    "export_ner_training_set",
    "build_bio_examples",
    "label_index",
    "to_conll",
    "token_level_metrics",
]
