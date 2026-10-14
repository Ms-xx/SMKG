"""
标注一致性服务门面（插件化架构迁移：实现已迁至 `app/plugins/annotation_agreement/service.py`）。

- 兼容再导出：既有 `from app.services.annotation_agreement_service import AnnotationAgreementService,
  cohens_kappa, ...` 不受影响。
- 运行期消费者应经 `registry.get("annotation_agreement")` 动态寻址。
"""

from __future__ import annotations

from app.plugins.annotation_agreement.service import (
    KRIPPENDORFF_METRICS,
    METRICS,
    AnnotationAgreementService,
    annotation_agreement_service,
    cohens_kappa,
    fleiss_kappa,
    krippendorff_alpha,
)

__all__ = [
    "METRICS",
    "KRIPPENDORFF_METRICS",
    "cohens_kappa",
    "fleiss_kappa",
    "krippendorff_alpha",
    "AnnotationAgreementService",
    "annotation_agreement_service",
]
