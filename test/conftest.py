# -*- coding: utf-8 -*-
"""
pytest 共享 fixtures
- 将 backend 加入 sys.path，便于 import app.*
- 提供基于 SQLite(aiosqlite) 的临时异步数据库 session，避免污染真实 MySQL
- 异步 DB 依赖（pytest-asyncio / sqlalchemy / aiosqlite）缺失时自动跳过相关 fixture，
  同步测试（如 vector_store、parsing_service）仍可正常运行。
"""
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

try:
    import pytest_asyncio  # noqa: F401
    import sqlalchemy  # noqa: F401
    import aiosqlite  # noqa: F401

    _HAS_ASYNC_DEPS = True
except Exception:  # pragma: no cover - 环境未安装异步测试依赖
    _HAS_ASYNC_DEPS = False


import pytest  # noqa: E402

API_PREFIX = "/api/v1"


@pytest.fixture
def token():
    """返回构造真实 JWT Authorization 头的工厂函数。"""
    from app.core.security import create_access_token

    def _token(user_id: str = "u1", role: str = "admin"):
        access = create_access_token({"sub": user_id, "role": role})
        return {"Authorization": f"Bearer {access}"}

    return _token


if _HAS_ASYNC_DEPS:
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    from app.models.base import Base
    import app.models  # noqa: F401  注册所有模型到 Base.metadata

    @pytest_asyncio.fixture
    async def engine(tmp_path):
        """每个测试函数一个独立的临时 SQLite 数据库。"""
        db_path = tmp_path / "test.db"
        _engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield _engine
        await _engine.dispose()

    @pytest_asyncio.fixture
    async def db(engine):
        """提供 AsyncSession，供 service 层调用。"""
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            yield session

    @pytest_asyncio.fixture
    async def client(engine, monkeypatch):
        """提供基于 httpx(ASGI) 的 HTTP 测试客户端。

        - 用 SQLite 测试库覆盖 app 的 get_db 依赖
        - mock MinIO 上传/下载/删除，避免依赖真实对象存储
        - 认证使用真实 JWT（见各测试内 token() helper），权限依赖据此解析
        """
        import httpx

        from app.main import app
        from app.core.database import get_db
        from app.utils.minio_client import MinioClient

        monkeypatch.setattr(
            MinioClient, "upload_file",
            lambda self, object_name, data, content_type="application/pdf": object_name,
        )
        monkeypatch.setattr(MinioClient, "delete_file", lambda self, object_name: None)
        monkeypatch.setattr(MinioClient, "download_file", lambda self, object_name: b"fake-pdf")

        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async def override_get_db():
            async with session_factory() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

        app.dependency_overrides[get_db] = override_get_db
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
        app.dependency_overrides.clear()