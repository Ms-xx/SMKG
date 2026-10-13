# -*- coding: utf-8 -*-
"""步骤 21 幂等迁移：为真实 DB 创建 recommend_records / recommend_feedback 两张表。

新表对现有库无需 ALTER；用 SQLAlchemy inspect 判断存在性，缺失才 create_all（create_all
天然只补缺失表，幂等）。运行：SciMKG python test/migrate_recommend_tables.py
"""
import asyncio
import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
)


async def main() -> int:
    from sqlalchemy import inspect
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.core.config import settings
    from app.models.base import Base
    import app.models  # noqa: F401  注册所有模型

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    need: list[str] = []
    async with engine.connect() as conn:
        insp = await conn.run_sync(lambda sync_conn: inspect(sync_conn))
        existing = set(insp.get_table_names())
        for t in ("recommend_records", "recommend_feedback"):
            status = "已存在" if t in existing else "缺失"
            print(f"[{status}] {t}")
            if t not in existing:
                need.append(t)
    if need:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("已创建：", ", ".join(need))
    else:
        print("无需迁移：两张推荐表均存在（幂等跳过）。")
    await engine.dispose()
    return 0


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:  # noqa: BLE001
        print("迁移失败：", e)
        sys.exit(1)
