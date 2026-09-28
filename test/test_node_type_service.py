# -*- coding: utf-8 -*-
"""node_type_service 测试：覆盖 list / create 去重抛错 / update / delete 默认不可删。"""
import json

import pytest

from app.services.node_type_service import (
    NodeTypeConflictError,
    NodeTypeNotFoundError,
    NodeTypeService,
    _DEFAULT_TYPES,
)


@pytest.fixture
def svc(tmp_path):
    """每个用例独立的临时数据文件，避免污染真实 registry。"""
    return NodeTypeService(data_file=tmp_path / "node_types.json")


def test_seed_types_include_required(svc):
    """默认种子包含现有 6 种及常用科学/工程领域类型。"""
    labels = {t["label"] for t in svc.list_types()}
    for required in [
        "Material",
        "Property",
        "Method",
        "Document",
        "Result",
        "Parameter",
        "Theory",
        "Model",
        "Formula",
        "Equation",
        "Experiment",
        "Dataset",
        "Tool",
        "Technique",
        "Application",
        "Author",
        "Organization",
        "Concept",
        "Discipline",
        "Condition",
    ]:
        assert required in labels
    # 默认在前，先于自定义
    order = [t["label"] for t in svc.list_types()]
    assert order == [t["label"] for t in _DEFAULT_TYPES]


def test_list_defaults_first_are_marked(svc):
    items = svc.list_types()
    assert all(t["is_default"] is True for t in items)


def test_create_type_appends_custom(svc):
    created = svc.create_type("Catalyst", name="催化剂", color="#111111")
    assert created["label"] == "Catalyst"
    assert created["name"] == "催化剂"
    assert created["is_default"] is False
    items = svc.list_types()
    assert items[-1]["label"] == "Catalyst"
    # 已写回磁盘
    raw = json.loads(svc._data_file.read_text(encoding="utf-8"))
    assert any(t["label"] == "Catalyst" for t in raw)


def test_create_type_normalizes_label(svc):
    created = svc.create_type("catalyst")
    assert created["label"] == "Catalyst"
    # 未提供 name 时回退为 label，未提供 color 时自动分配
    assert created["name"] == "Catalyst"
    assert created["color"]


def test_create_type_duplicate_raises(svc):
    svc.create_type("Catalyst")
    with pytest.raises(ValueError):
        svc.create_type("Catalyst")


def test_update_type(svc):
    svc.create_type("Catalyst", name="催化剂")
    updated = svc.update_type("Catalyst", name="新催化", color="#222222")
    assert updated["name"] == "新催化"
    assert updated["color"] == "#222222"


def test_update_type_not_found(svc):
    with pytest.raises(NodeTypeNotFoundError):
        svc.update_type("Ghost")


def test_delete_custom_type(svc):
    svc.create_type("Catalyst")
    result = svc.delete_type("Catalyst")
    assert result == {"deleted": "Catalyst"}
    assert all(t["label"] != "Catalyst" for t in svc.list_types())


def test_delete_default_type_raises(svc):
    with pytest.raises(NodeTypeConflictError) as exc_info:
        svc.delete_type("Material")
    assert "不可删除" in str(exc_info.value)


def test_delete_not_found(svc):
    with pytest.raises(NodeTypeNotFoundError):
        svc.delete_type("Ghost")
