# -*- coding: utf-8 -*-
"""知识图谱节点类型注册表的请求模型。"""
from typing import Optional

from pydantic import BaseModel


class NodeTypeCreate(BaseModel):
    label: str
    name: Optional[str] = None
    color: Optional[str] = None


class NodeTypeUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
