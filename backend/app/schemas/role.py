from typing import List

from pydantic import BaseModel


class PermissionInfo(BaseModel):
    code: str
    description: str


class PermissionListResponse(BaseModel):
    items: List[PermissionInfo]
    total: int


class MyPermissionsResponse(BaseModel):
    role: str
    permissions: List[str]


class RoleResponse(BaseModel):
    id: str
    name: str
    description: str
    permissions: List[str]


class RoleListResponse(BaseModel):
    items: List[RoleResponse]
    total: int


class RolePermissionsUpdate(BaseModel):
    permissions: List[str]
