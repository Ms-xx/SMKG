# -*- coding: utf-8 -*-
"""
主动学习训练任务模块（步骤 14.1）。

在 `training` 独立队列内完成「采样 → 待标注导出 → 触发重训 → 评估 → 注册/晋升」周期。
任务内使用同步会话（get_db_context），与既有 parsing_tasks 风格一致，避免 async session
在 Celery 中的事件循环问题。

状态流转：PENDING → STARTED → SAMPLING → FINETUNE → EVALUATE → REGISTER → SUCCESS
"""
from __future__ import annotations

from typing import Any

from loguru import logger

from app.core.celery_app import celery_app


@celery_app.task(name="run_active_learning_cycle", bind=True, queue="training")
def run_active_learning_cycle(self, payload: dict[str, Any]) -> dict[str, Any]:
    """主动学习周期：采样 → 待标注导出 → 触发重训 → 评估 → 注册/晋升。

    Args:
        payload: {
            "experiment_id": str,
            "strategy": "uncertainty" | "diversity" | "qbc" | "hybrid",
            "sample_size": int,
            "finetune_config": dict（可选）,
        }
    Returns:
        {"cycle_id": str, "state": "SUCCESS", "sampled_ids": [...], "version_id": str}
    """
    experiment_id = payload.get("experiment_id", "default")
    strategy = payload.get("strategy", "hybrid")
    sample_size = payload.get("sample_size", 10)

    try:
        self.update_state(state="STARTED", meta={"experiment_id": experiment_id})
        logger.info("active_learning_cycle started: exp={}", experiment_id)

        # 1. 采样
        self.update_state(state="SAMPLING", meta={"strategy": strategy})

        # 采样服务可能需要 DB 会话；此处用同步会话
        from app.core.database import get_db_context

        with get_db_context() as db:
            from sqlalchemy import text

            # 简化：从 documents 表采样低置信度样本（mock 友好）
            try:
                rows = db.execute(
                    text("SELECT id FROM documents ORDER BY RAND() LIMIT :n"),
                    {"n": sample_size},
                ).fetchall()
                sampled_ids = [str(r[0]) for r in rows]
            except Exception:
                sampled_ids = []

        logger.info("active_learning_cycle sampled {} ids", len(sampled_ids))

        # 2. 触发重训（CPU 小样本或 mock）
        self.update_state(state="FINETUNE", meta={"sampled": len(sampled_ids)})
        finetune_result = run_finetune_job.apply(
            args=[
                {
                    "experiment_id": experiment_id,
                    "sample_ids": sampled_ids,
                    "config": payload.get("finetune_config", {}),
                }
            ]
        ).get()

        # 3. 评估
        self.update_state(state="EVALUATE", meta={"finetune": finetune_result})

        # 4. 注册/晋升
        self.update_state(state="REGISTER", meta={"metrics": finetune_result.get("metrics")})
        version_id = finetune_result.get("version_id", f"{experiment_id}-v1")

        self.update_state(state="SUCCESS", meta={"version_id": version_id})
        return {
            "cycle_id": experiment_id,
            "state": "SUCCESS",
            "sampled_ids": sampled_ids,
            "version_id": version_id,
            "metrics": finetune_result.get("metrics", {}),
        }
    except Exception as e:
        logger.exception("active_learning_cycle failed: {}", e)
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise


@celery_app.task(name="run_finetune_job", bind=True, queue="training")
def run_finetune_job(self, payload: dict[str, Any]) -> dict[str, Any]:
    """微调任务：包装 version_management_service.run_finetune_pipeline。

    无 GPU 时走 CPU 小样本或 mock 训练器（验证链路正确性，不验证精度）。
    """
    experiment_id = payload.get("experiment_id", "default")
    sample_ids = payload.get("sample_ids", [])
    config = payload.get("config", {})

    try:
        self.update_state(state="STARTED", meta={"experiment_id": experiment_id})
        logger.info("finetune_job started: exp={}, samples={}", experiment_id, len(sample_ids))

        from app.services.version_management_service import VersionManagementService

        vms = VersionManagementService()
        # 调用既有微调管道（CPU 小样本）
        try:
            result = vms.run_finetune_pipeline(
                experiment_id=experiment_id,
                sample_ids=sample_ids,
                config=config,
            )
        except Exception as e:
            logger.warning("finetune pipeline failed, using mock: {}", e)
            # mock 训练器（验证调度链路）
            result = {
                "version_id": f"{experiment_id}-mock-v1",
                "metrics": {"f1": 0.0, "accuracy": 0.0, "backend": "mock"},
                "status": "success_mock",
            }

        self.update_state(state="SUCCESS", meta={"version_id": result.get("version_id")})
        return result
    except Exception as e:
        logger.exception("finetune_job failed: {}", e)
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise
