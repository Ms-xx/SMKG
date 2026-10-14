from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plugin.base import Plugin
from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import UserCreate


class AuthService:
    # ─── 插件协议 ──────────────────────────────────────────────────────────
    async def on_start(self) -> None:
        logger.info("auth plugin started")

    async def on_stop(self) -> None:
        logger.info("auth plugin stopped")

    def health(self) -> dict:
        return {"backend": "auth", "available": True}

    async def authenticate_user(self, db: AsyncSession, username: str, password: str):
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if not user or not verify_password(password, user.password_hash):
            return None
        return user

    async def create_user(self, db: AsyncSession, user_data: UserCreate) -> User:
        user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=get_password_hash(user_data.password),
            full_name=user_data.full_name,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        return user

    async def get_user_by_username(self, db: AsyncSession, username: str):
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_user_by_email(self, db: AsyncSession, email: str):
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()


class AuthPlugin(Plugin):
    """官方插件：auth —— 认证服务（存量迁移自 app/services/auth_service.py）。"""

    name = "auth"
    version = "1.0.0"
    config_prefix = ""
    requires: list[str] = []
    type = "service"
    legacy_module = "app.services.auth_service"

    def create(self, registry, settings) -> AuthService:
        return AuthService()


plugin = AuthPlugin()
