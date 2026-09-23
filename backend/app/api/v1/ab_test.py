# -*- coding: utf-8 -*-
"""A/B 测试框架 API（步骤 8）：流量分流 / 指标采集 / 统计显著性判定。"""
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.services.ab_test_service import ab_test_service

router = APIRouter()


class CreateExperimentRequest(BaseModel):
    name: str = Field(..., description="实验名称")
    variants: list[str] = Field(..., description="变体标识列表，至少 2 个且唯一")
    weights: Optional[list[float]] = Field(None, description="各变体分流权重，缺省均分")
    metric_type: str = Field("binary", description="指标类型：binary | continuous")
    metric_name: str = Field("metric", description="目标指标名")
    minimize: bool = Field(False, description="True 表示指标越小越优（如延迟）")
    alpha: Optional[float] = Field(None, description="显著水平，缺省用配置 AB_TEST_ALPHA")


class AssignRequest(BaseModel):
    experiment_id: str = Field(..., description="实验 id")
    subject_id: str = Field(..., description="请求/用户标识，同一 subject 稳定路由到同一变体")


class RecordRequest(BaseModel):
    experiment_id: str = Field(..., description="实验 id")
    variant: str = Field(..., description="变体标识")
    value: Any = Field(..., description="观测值：binary 为 0/1/bool，continuous 为数值")
    metric_name: Optional[str] = Field(None, description="指标名，缺省用实验配置的目标指标")


class EvaluateRequest(BaseModel):
    experiment_id: str = Field(..., description="实验 id")
    metric_name: Optional[str] = Field(None, description="指标名，缺省用实验目标指标")
    variant_a: Optional[str] = Field(None, description="对照组变体，缺省取第一个变体")
    variant_b: Optional[str] = Field(None, description="实验组变体，缺省取第二个变体")
    alpha: Optional[float] = Field(None, description="显著水平覆盖")


@router.post("/experiments")
async def create_experiment(
    body: CreateExperimentRequest,
    current_user: dict = Depends(get_current_user),
):
    """创建 A/B 实验（变体 + 分流权重 + 指标类型方向）。"""
    return ab_test_service.create_experiment(
        name=body.name,
        variants=body.variants,
        weights=body.weights,
        metric_type=body.metric_type,
        metric_name=body.metric_name,
        minimize=body.minimize,
        alpha=body.alpha,
    )


@router.get("/experiments")
async def list_experiments(current_user: dict = Depends(get_current_user)):
    """列出全部 A/B 实验。"""
    return ab_test_service.list_experiments()


@router.get("/experiments/{experiment_id}")
async def get_experiment(
    experiment_id: str,
    current_user: dict = Depends(get_current_user),
):
    """查询单个 A/B 实验详情。"""
    return ab_test_service.get_experiment(experiment_id)


@router.post("/assign")
async def assign(
    body: AssignRequest,
    current_user: dict = Depends(get_current_user),
):
    """流量分流：按权重把 subject 确定性路由到某个变体（8.1）。"""
    return ab_test_service.assign(body.experiment_id, body.subject_id)


@router.post("/record")
async def record(
    body: RecordRequest,
    current_user: dict = Depends(get_current_user),
):
    """指标采集：记录某变体的一次观测（8.2）。"""
    return ab_test_service.record(
        body.experiment_id,
        body.variant,
        body.value,
        metric_name=body.metric_name,
    )


@router.post("/evaluate")
async def evaluate(
    body: EvaluateRequest,
    current_user: dict = Depends(get_current_user),
):
    """统计显著性判定与结论面板：对比两个变体并输出结论（8.3）。"""
    return ab_test_service.evaluate(
        body.experiment_id,
        metric_name=body.metric_name,
        variant_a=body.variant_a,
        variant_b=body.variant_b,
        alpha=body.alpha,
    )
