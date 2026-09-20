from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# 异步引擎用于FastAPI
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    echo=settings.DEBUG,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """异步数据库会话依赖注入"""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# 同步引擎用于Celery任务
sync_engine = create_engine(
    settings.DATABASE_URL.replace("+aiomysql", "+pymysql"),
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    echo=settings.DEBUG,
)

sync_session = sessionmaker(
    sync_engine,
    class_=Session,
    expire_on_commit=False,
)


@contextmanager
def get_db_context():
    """同步数据库会话上下文管理器,用于Celery任务"""
    session = sync_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
