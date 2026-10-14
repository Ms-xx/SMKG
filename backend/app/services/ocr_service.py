"""
OCR 服务门面（插件化架构迁移：实现已迁至 `app/plugins/ocr/plugin.py`）。

- 兼容再导出：既有 `from app.services.ocr_service import OCRService / ocr_service`
  不受影响（门面符号与插件注册实现同源）。
- 运行期热替换消费者应经 `registry.get("ocr")` 动态寻址，而非持有本门面单例。
- 依赖策略（可插拔、可降级）同原实现：未安装 `paddleocr` 时自动降级为空文本。
"""

from __future__ import annotations

from app.plugins.ocr.plugin import OCRService, ocr_service

__all__ = ["OCRService", "ocr_service"]
