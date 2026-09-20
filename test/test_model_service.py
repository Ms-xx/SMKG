# -*- coding: utf-8 -*-
"""模型服务 DB 集成测试。"""
import os
import sys

import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.schemas.model import ModelCreate
from app.services.model_service import ModelService


@pytest.mark.asyncio
async def test_create_and_get_model(db):
    svc = ModelService()
    data = ModelCreate(name="scibert-ner", version="1.0", model_type="ner", framework="pytorch")
    m = await svc.create_model(db, data, created_by="u1")
    assert m.id is not None
    assert m.is_active is False

    found = await svc.get_model(db, m.id)
    assert found.name == "scibert-ner"
    assert await svc.get_model(db, "no-id") is None


@pytest.mark.asyncio
async def test_list_models_filters(db):
    svc = ModelService()
    await svc.create_model(db, ModelCreate(name="a", version="1", model_type="ner"), "u1")
    await svc.create_model(db, ModelCreate(name="b", version="1", model_type="re"), "u1")

    all_models = await svc.list_models(db)
    assert len(all_models) == 2
    ner_models = await svc.list_models(db, model_type="ner")
    assert len(ner_models) == 1


@pytest.mark.asyncio
async def test_update_status_and_delete(db):
    svc = ModelService()
    m = await svc.create_model(db, ModelCreate(name="a", version="1", model_type="ner"), "u1")

    updated = await svc.update_status(db, m.id, True)
    assert updated.is_active is True
    assert await svc.update_status(db, "no-id", True) is None

    assert await svc.delete_model(db, m.id) is True
    assert await svc.delete_model(db, m.id) is False