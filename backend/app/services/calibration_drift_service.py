"""
校准漂移服务门面（插件化架构迁移：实现已迁至 `app/plugins/calibration_drift/service.py`）。

- 兼容再导出：既有 `from app.services.calibration_drift_service import CalibrationDriftService,
  softmax, ...` 不受影响。
- 运行期消费者应经 `registry.get("calibration_drift")` 动态寻址。
"""

from __future__ import annotations

from app.plugins.calibration_drift.service import (
    DRIFT_STATUS,
    CalibrationDriftService,
    calibration_drift_service,
    chi_square_drift,
    classify_psi,
    expected_calibration_error,
    fit_platt,
    fit_temperature,
    ks_statistic,
    platt_calibrate,
    psi,
    reliability_curve,
    sigmoid,
    softmax,
)

__all__ = [
    "DRIFT_STATUS",
    "softmax",
    "sigmoid",
    "fit_temperature",
    "fit_platt",
    "platt_calibrate",
    "expected_calibration_error",
    "reliability_curve",
    "psi",
    "ks_statistic",
    "chi_square_drift",
    "classify_psi",
    "CalibrationDriftService",
    "calibration_drift_service",
]
