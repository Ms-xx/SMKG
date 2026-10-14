"""
命名实体识别服务门面（插件化架构迁移：实现已迁至 `app/plugins/ner/service.py`）。

- 兼容再导出：既有 `from app.services.ner_service import NERService / ner_service /
  merge_bio_spans` 不受影响。
- 重型模型服务（SciBERT checkpoint）：运行期仅冷替换/重启；消费者经 `registry.get("ner")`
  动态寻址。
"""

from __future__ import annotations

from app.plugins.ner.service import (
    NERService,
    extract_english_gazetteer,
    merge_bio_spans,
    ner_service,
)

__all__ = ["NERService", "ner_service", "merge_bio_spans", "extract_english_gazetteer"]
