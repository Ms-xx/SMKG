# -*- coding: utf-8 -*-
"""节点类型注册表服务：管理知识图谱节点类型（默认 + 自定义），持久化到 JSON。

底层图谱已支持动态 label，本服务仅维护一个可扩展的节点类型清单，
供前端渲染图例、类型筛选下拉与自定义节点类型使用。

数据保存在 ``backend/app/data/node_types.json``；启动时读入内存，操作后写回。
"""
import json
import threading
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DATA_FILE = _DATA_DIR / "node_types.json"

# 预置色板（默认/自定义类型按序分配，保证颜色各不相同）
_COLOR_PALETTE = [
    "#1890ff",
    "#52c41a",
    "#faad14",
    "#13c2c2",
    "#eb2f96",
    "#722ed1",
    "#f5222d",
    "#ff7a45",
    "#a0d911",
    "#08979c",
    "#2f54eb",
    "#531dab",
    "#c41d7f",
    "#d48806",
    "#389e0d",
    "#096dd9",
    "#7cb305",
    "#f759ab",
    "#597ef7",
    "#874d00",
]

# 默认种子类型：现有 6 种 + 常用科学/工程领域节点类型
_DEFAULT_TYPES = [
    {"label": "Material", "name": "材料", "color": "#1890ff", "is_default": True},
    {"label": "Property", "name": "性能", "color": "#52c41a", "is_default": True},
    {"label": "Method", "name": "方法", "color": "#faad14", "is_default": True},
    {"label": "Document", "name": "文档", "color": "#13c2c2", "is_default": True},
    {"label": "Result", "name": "结果", "color": "#eb2f96", "is_default": True},
    {"label": "Parameter", "name": "参数", "color": "#722ed1", "is_default": True},
    {"label": "Theory", "name": "理论", "color": "#f5222d", "is_default": True},
    {"label": "Model", "name": "模型", "color": "#ff7a45", "is_default": True},
    {"label": "Formula", "name": "化学式/分子式", "color": "#a0d911", "is_default": True},
    {"label": "Equation", "name": "公式", "color": "#08979c", "is_default": True},
    {"label": "Experiment", "name": "实验", "color": "#2f54eb", "is_default": True},
    {"label": "Dataset", "name": "数据集", "color": "#531dab", "is_default": True},
    {"label": "Tool", "name": "工具/仪器", "color": "#c41d7f", "is_default": True},
    {"label": "Technique", "name": "技术", "color": "#d48806", "is_default": True},
    {"label": "Application", "name": "应用", "color": "#389e0d", "is_default": True},
    {"label": "Author", "name": "作者", "color": "#096dd9", "is_default": True},
    {"label": "Organization", "name": "机构", "color": "#7cb305", "is_default": True},
    {"label": "Concept", "name": "概念", "color": "#f759ab", "is_default": True},
    {"label": "Discipline", "name": "学科", "color": "#597ef7", "is_default": True},
    {"label": "Condition", "name": "条件", "color": "#874d00", "is_default": True},
]


class NodeTypeNotFoundError(ValueError):
    """节点类型不存在。"""


class NodeTypeConflictError(ValueError):
    """节点类型冲突：已存在，或默认类型不可删除。"""


class NodeTypeService:
    def __init__(self, data_file: Path = _DATA_FILE):
        self._data_file = data_file
        self._lock = threading.Lock()
        self._types = []
        self._load()

    def _load(self):
        try:
            raw = self._data_file.read_text(encoding="utf-8")
        except FileNotFoundError:
            self._types = list(_DEFAULT_TYPES)
        else:
            loaded = json.loads(raw or "[]")
            if not loaded:
                self._types = list(_DEFAULT_TYPES)
            else:
                self._types = loaded
        self._persist()

    def _persist(self):
        self._data_file.parent.mkdir(parents=True, exist_ok=True)
        self._data_file.write_text(
            json.dumps(self._types, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _normalize_label(label):
        label = (label or "").strip()
        if not label:
            raise ValueError("label 不能为空")
        return label[0].upper() + label[1:]

    def list_types(self):
        """返回全部节点类型：默认在前（保持种子顺序）自定义在后，含 is_default 标记。"""
        with self._lock:
            # 稳定排序：默认(is_default=True)在前且保持原有顺序，自定义在后
            return sorted(self._types, key=lambda t: not t.get("is_default"))

    def create_type(self, label, name=None, color=None):
        """新增自定义节点类型；label 必填并统一为首字母大写，已存在则抛 ValueError。"""
        label = self._normalize_label(label)
        with self._lock:
            if any(t["label"] == label for t in self._types):
                raise NodeTypeConflictError(f"节点类型 {label!r} 已存在")
            item = {
                "label": label,
                "name": name or label,
                "color": color or self._next_color(),
                "is_default": False,
            }
            self._types.append(item)
            self._persist()
            return dict(item)

    def update_type(self, label, name=None, color=None):
        """更新节点类型的名称/颜色；不存在则抛 ValueError（NotFound）。"""
        label = self._normalize_label(label)
        with self._lock:
            item = next((t for t in self._types if t["label"] == label), None)
            if item is None:
                raise NodeTypeNotFoundError(f"节点类型 {label!r} 不存在")
            if name is not None:
                item["name"] = name
            if color is not None:
                item["color"] = color
            self._persist()
            return dict(item)

    def delete_type(self, label):
        """删除自定义节点类型；不存在抛 NotFound，默认类型不可删抛 Conflict。"""
        with self._lock:
            item = next((t for t in self._types if t["label"] == label), None)
            if item is None:
                raise NodeTypeNotFoundError(f"节点类型 {label!r} 不存在")
            if item.get("is_default"):
                raise NodeTypeConflictError(f"默认节点类型 {label!r} 不可删除")
            self._types.remove(item)
            self._persist()
            return {"deleted": label}

    def _next_color(self):
        used = {t.get("color") for t in self._types}
        for color in _COLOR_PALETTE:
            if color not in used:
                return color
        return _COLOR_PALETTE[0]


node_type_service = NodeTypeService()
