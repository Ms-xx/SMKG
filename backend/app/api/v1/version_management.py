import asyncio
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.annotation import Annotation
from app.services.version_management_service import version_management_service

router = APIRouter()


class RecordDatasetRequest(BaseModel):
    name: str = Field(..., description="数据集名称")
    data: Optional[list[Any]] = Field(None, description="数据集记录；每项为 dict 或对象")
    source: Optional[str] = Field(None, description="数据来源")
    pipeline: Optional[str] = Field(None, description="处理流程")
    annotators: Optional[list[str]] = Field(None, description="标注员标识列表")
    label_key: str = Field("label", description="标签字段名（默认 label）")


class LogExperimentRequest(BaseModel):
    name: str = Field(..., description="实验名称")
    params: Optional[dict[str, Any]] = Field(None, description="训练参数")
    metrics: Optional[dict[str, Any]] = Field(None, description="评估指标")
    model_name: Optional[str] = Field(None, description="关联模型名")
    model_version: Optional[int] = Field(None, description="关联模型版本")
    tags: Optional[dict[str, Any]] = Field(None, description="标签")


class CompareExperimentsRequest(BaseModel):
    experiment_ids: Optional[list[str]] = Field(None, description="实验 id 列表；缺省对比全部")


class RegisterModelRequest(BaseModel):
    name: str = Field(..., description="模型名称")
    artifacts: Optional[dict[str, Any]] = Field(None, description="模型产物（文件路径/哈希等）")
    metrics: Optional[dict[str, Any]] = Field(None, description="模型评估指标")
    experiment_id: Optional[str] = Field(None, description="关联实验 id")
    description: Optional[str] = Field(None, description="版本描述")


class TransitionStageRequest(BaseModel):
    name: str = Field(..., description="模型名称")
    version: int = Field(..., description="模型版本号")
    stage: str = Field(..., description="目标阶段：staging | production | archived")


class CheckRetrainRequest(BaseModel):
    new_annotated: int = Field(0, description="新标注样本数")
    last_train_count: int = Field(0, description="上次训练时的样本数")
    threshold: Optional[int] = Field(None, description="触发阈值（缺省用配置 RETRAIN_THRESHOLD）")
    periodic_days: Optional[int] = Field(None, description="定期触发间隔（缺省用配置）")
    last_train_age_days: float = Field(0.0, description="距上次训练的天数")
    force: bool = Field(False, description="是否手动强制触发")


class RunPipelineRequest(BaseModel):
    model_name: str = Field(..., description="模型名称")
    trigger_reason: str = Field("manual", description="触发原因：manual | threshold | periodic")
    max_retries: Optional[int] = Field(None, description="分段失败最大重试次数（缺省用配置）")


class FinetuneRequest(BaseModel):
    model_name: str = Field(..., description="模型名称（如 ner）")
    trigger_reason: str = Field("manual", description="触发原因：manual | threshold | periodic")
    annotation_type: Optional[str] = Field(
        "ner", description="导出 DB 标注按此类型过滤；None 不过滤"
    )
    status: str = Field("approved", description="仅导出该状态的标注（如 approved）")
    records: Optional[list[Any]] = Field(None, description="直接传入训练样本（可选，覆盖 DB 读取）")
    epochs: int = Field(3, description="训练轮数")
    lr: float = Field(2e-4, description="学习率")
    lora_r: int = Field(8, description="LoRA rank")
    lora_alpha: int = Field(32, description="LoRA alpha")
    quantize: bool = Field(False, description="是否尝试 QLoRA 4bit（需 bitsandbytes）")
    f1_threshold: float = Field(0.0, description="F1 ≥ 阈值时自动晋升 Production")
    max_retries: Optional[int] = Field(None, description="缺省用配置 RETRAIN_MAX_RETRIES")


@router.post("/datasets")
async def record_dataset(
    body: RecordDatasetRequest,
    current_user: dict = Depends(get_current_user),
):
    """记录数据集版本（DVC 风格：内容哈希 + 血缘 + 质量评估快照）。"""
    return version_management_service.record_dataset(
        name=body.name,
        data=body.data,
        source=body.source,
        pipeline=body.pipeline,
        annotators=body.annotators,
        label_key=body.label_key,
    )


@router.get("/datasets")
async def list_datasets(current_user: dict = Depends(get_current_user)):
    """列出数据集版本历史。"""
    return version_management_service.list_datasets()


@router.post("/experiments")
async def log_experiment(
    body: LogExperimentRequest,
    current_user: dict = Depends(get_current_user),
):
    """记录实验（MLflow 风格：参数/指标/关联模型版本/标签）。"""
    return version_management_service.log_experiment(
        name=body.name,
        params=body.params,
        metrics=body.metrics,
        model_name=body.model_name,
        model_version=body.model_version,
        tags=body.tags,
    )


@router.get("/experiments")
async def list_experiments(
    name: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """列出实验记录。"""
    return version_management_service.list_experiments(name)


@router.post("/experiments/compare")
async def compare_experiments(
    body: CompareExperimentsRequest,
    current_user: dict = Depends(get_current_user),
):
    """多实验指标对比。"""
    return version_management_service.compare_experiments(body.experiment_ids)


@router.post("/models")
async def register_model(
    body: RegisterModelRequest,
    current_user: dict = Depends(get_current_user),
):
    """注册模型新版本（初始阶段 Staging）。"""
    return version_management_service.register_model(
        name=body.name,
        artifacts=body.artifacts,
        metrics=body.metrics,
        experiment_id=body.experiment_id,
        description=body.description,
    )


@router.get("/models")
async def list_models(current_user: dict = Depends(get_current_user)):
    """列出已注册模型及其版本/阶段。"""
    return version_management_service.list_models()


@router.post("/models/stage")
async def transition_stage(
    body: TransitionStageRequest,
    current_user: dict = Depends(get_current_user),
):
    """模型阶段流转：Staging → Production → Archived。"""
    return version_management_service.transition_stage(body.name, body.version, body.stage)


@router.post("/retrain/check")
async def check_retrain(
    body: CheckRetrainRequest,
    current_user: dict = Depends(get_current_user),
):
    """自动重训触发条件评估。"""
    return version_management_service.check_retrain(
        new_annotated=body.new_annotated,
        last_train_count=body.last_train_count,
        threshold=body.threshold,
        periodic_days=body.periodic_days,
        last_train_age_days=body.last_train_age_days,
        force=body.force,
    )


@router.post("/retrain/run")
async def run_pipeline(
    body: RunPipelineRequest,
    current_user: dict = Depends(get_current_user),
):
    """启动自动重训管道（分段推进 + 失败重试 + 回滚）。"""
    return version_management_service.run_pipeline(
        model_name=body.model_name,
        trigger_reason=body.trigger_reason,
        max_retries=body.max_retries,
    )


@router.post("/retrain/finetune")
async def run_finetune(
    body: FinetuneRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """真实微调闭环（步骤 2）：读取 DB 标注（或直接传样本）→ LoRA/QLoRA 微调 → 评估 → 注册 → 部署。"""
    records = body.records
    if records is None:
        records = await _load_annotations(db, body.annotation_type, body.status)
    return await asyncio.to_thread(
        version_management_service.run_finetune_pipeline,
        model_name=body.model_name,
        records=records,
        trigger_reason=body.trigger_reason,
        epochs=body.epochs,
        lr=body.lr,
        lora_r=body.lora_r,
        lora_alpha=body.lora_alpha,
        quantize=body.quantize,
        f1_threshold=body.f1_threshold,
        max_retries=body.max_retries,
    )


async def _load_annotations(
    db: AsyncSession, annotation_type: str | None, status: str
) -> list[Any]:
    """读取数据库标注（默认仅终审通过的样本），供微调导出使用。"""
    query = select(Annotation)
    if annotation_type:
        query = query.where(Annotation.annotation_type == annotation_type)
    if status:
        query = query.where(Annotation.status == status)
    result = await db.execute(query.order_by(Annotation.created_at.desc()))
    return list(result.scalars().all())


@router.get("/retrain/{run_id}")
async def pipeline_status(
    run_id: str,
    current_user: dict = Depends(get_current_user),
):
    """查询自动重训管道运行状态。"""
    return version_management_service.pipeline_status(run_id)
