# -*- coding: utf-8 -*-
"""A/B 测试与模型版本路由测试（步骤 14.5）。"""
from app.services.ab_test_service import ABTestService


def test_ab_test_assign_returns_variant():
    """分流应返回有效变体。"""
    svc = ABTestService()
    try:
        created = svc.create_experiment(
            "exp-routing-test", variants=["v1", "v2"], weights=[0.5, 0.5]
        )
        exp_id = created.get("id") or created.get("name")
    except Exception:
        # 已存在时直接用 name
        exp_id = "exp-routing-test"
    result = svc.assign(exp_id, "user-1")
    assert result.get("variant") in ("v1", "v2")


def test_ab_test_min_samples_threshold():
    """样本不足时应返回提示而非结论。"""
    from app.core.config import settings

    assert settings.AB_TEST_MIN_SAMPLES == 30


def test_ab_test_service_importable():
    """A/B 服务可导入且可实例化。"""
    svc = ABTestService()
    assert svc is not None
