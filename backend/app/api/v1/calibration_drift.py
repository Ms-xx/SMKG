from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.services.calibration_drift_service import calibration_drift_service

router = APIRouter()


class CalibrateRequest(BaseModel):
    method: str = Field("temperature", description="temperature | platt")
    logits: Optional[list[list[float]]] = Field(None, description="temperature 校准的 logits 矩阵")
    labels: Optional[list[int]] = Field(
        None, description="temperature 校准的真实类别（用于拟合 T）"
    )
    scores: Optional[list[float]] = Field(None, description="platt 校准的二分类置信度")
    binary_labels: Optional[list[int]] = Field(None, description="platt 校准的二分类标签（0/1）")
    temperature: Optional[float] = Field(None, description="显式温度（缺省自动拟合）")


class EvaluateCalibrationRequest(BaseModel):
    probs: list[float] = Field(..., description="预测概率（正类）")
    labels: list[int] = Field(..., description="真实标签（0/1）")
    n_bins: Optional[int] = Field(None, description="分箱数（缺省用配置 CALIBRATION_ECE_BINS）")


class DetectDriftRequest(BaseModel):
    reference: list[Any] = Field(..., description="参考分布（数值列表或类别列表）")
    current: list[Any] = Field(..., description="当前分布")
    method: str = Field("psi", description="数值漂移：psi | ks；类别漂移自动用卡方")
    categorical: bool = Field(False, description="是否为类别分布")


@router.post("/calibrate")
async def calibrate(
    body: CalibrateRequest,
    current_user: dict = Depends(get_current_user),
):
    """置信度校准：Temperature Scaling / Platt Scaling。"""
    return calibration_drift_service.calibrate(
        method=body.method,
        logits=body.logits,
        labels=body.labels,
        scores=body.scores,
        binary_labels=body.binary_labels,
        temperature=body.temperature,
    )


@router.post("/evaluate")
async def evaluate_calibration(
    body: EvaluateCalibrationRequest,
    current_user: dict = Depends(get_current_user),
):
    """校准质量评估：ECE + 可靠性曲线。"""
    return calibration_drift_service.evaluate_calibration(body.probs, body.labels, body.n_bins)


@router.post("/detect")
async def detect_drift(
    body: DetectDriftRequest,
    current_user: dict = Depends(get_current_user),
):
    """数据漂移检测：PSI / KS / 卡方，阈值分级告警。"""
    return calibration_drift_service.detect_drift(
        reference=body.reference,
        current=body.current,
        method=body.method,
        categorical=body.categorical,
    )
