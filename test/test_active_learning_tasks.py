# -*- coding: utf-8 -*-
"""active_learning_tasks 任务注册与路由测试（步骤 14.5）。"""
from app.core.celery_app import celery_app
from app.workers.active_learning_tasks import (
    run_active_learning_cycle,
    run_finetune_job,
)


def test_task_registered():
    """任务应在 Celery 注册表中。"""
    assert "run_active_learning_cycle" in celery_app.tasks
    assert "run_finetune_job" in celery_app.tasks


def test_task_queue_routing():
    """训练任务应路由到 training 队列。"""
    routes = celery_app.conf.task_routes
    assert "app.workers.active_learning_tasks.*" in routes
    assert routes["app.workers.active_learning_tasks.*"]["queue"] == "training"


def test_task_module_importable():
    """任务模块可导入且为可调用对象。"""
    assert callable(run_active_learning_cycle)
    assert callable(run_finetune_job)


def test_all_four_queues_configured():
    """4 个队列均应出现在路由配置中。"""
    queues = set()
    for key, val in celery_app.conf.task_routes.items():
        queues.add(val["queue"])
    assert "parsing" in queues
    assert "extraction" in queues
    assert "graph" in queues
    assert "training" in queues
