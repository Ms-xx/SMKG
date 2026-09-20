from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import ALL_PERMISSIONS
from app.models.role import Role


class PermissionService:
    async def list_roles(self, db: AsyncSession):
        result = await db.execute(select(Role).order_by(Role.name))
        roles = result.scalars().all()
        return roles

    async def get_role_by_name(self, db: AsyncSession, name: str) -> Optional[Role]:
        result = await db.execute(select(Role).where(Role.name == name))
        return result.scalar_one_or_none()

    async def update_role_permissions(
        self, db: AsyncSession, name: str, permissions: List[str]
    ) -> Optional[Role]:
        role = await self.get_role_by_name(db, name)
        if not role:
            return None

        # 仅接受合法权限码，去重
        allowed = set(ALL_PERMISSIONS)
        cleaned = []
        for p in permissions:
            if p in allowed and p not in cleaned:
                cleaned.append(p)

        role.permissions = cleaned
        await db.flush()
        await db.refresh(role)
        return role
