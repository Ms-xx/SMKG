from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserUpdate


class UserService:
    async def get_user_by_id(self, db: AsyncSession, user_id: str):
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def list_users(
        self,
        db: AsyncSession,
        page: int,
        page_size: int,
        role: str = None,
        is_active: bool = None,
        keyword: str = None,
    ):
        query = select(User)
        if role:
            query = query.where(User.role == role)
        if is_active is not None:
            query = query.where(User.is_active == is_active)
        if keyword:
            query = query.where(User.username.ilike(f"%{keyword}%"))

        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query)

        query = (
            query.offset((page - 1) * page_size).limit(page_size).order_by(User.created_at.desc())
        )
        result = await db.execute(query)
        users = result.scalars().all()

        return users, total

    async def update_user(self, db: AsyncSession, user_id: str, update_data: UserUpdate):
        user = await self.get_user_by_id(db, user_id)
        if not user:
            return None
        for field, value in update_data.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        await db.flush()
        await db.refresh(user)
        return user

    async def update_role(self, db: AsyncSession, user_id: str, role: str):
        user = await self.get_user_by_id(db, user_id)
        if not user:
            return None
        user.role = role
        await db.flush()
        await db.refresh(user)
        return user

    async def update_status(self, db: AsyncSession, user_id: str, is_active: bool):
        user = await self.get_user_by_id(db, user_id)
        if not user:
            return None
        user.is_active = is_active
        await db.flush()
        await db.refresh(user)
        return user

    async def delete_user(self, db: AsyncSession, user_id: str):
        user = await self.get_user_by_id(db, user_id)
        if not user:
            return False
        await db.delete(user)
        return True

    async def list_mentionable(self, db: AsyncSession):
        """列出可被 @ 提及的活跃用户（id + username）。"""
        result = await db.execute(
            select(User.id, User.username, User.full_name)
            .where(User.is_active.is_(True))
            .order_by(User.username)
        )
        return [
            {"id": row.id, "username": row.username, "full_name": row.full_name}
            for row in result.all()
        ]
