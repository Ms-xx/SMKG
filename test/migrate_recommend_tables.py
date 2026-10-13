# -*- coding: utf-8 -*-
"""步骤 21 幂等迁移：为真实 DB 创建 recommend_records / recommend_feedback 两张表。

用直接 DDL（CREATE TABLE IF NOT EXISTS）而非 ORM run_sync(create_all)：
后者在 aiomysql + 真实 MySQL 上会触发 MissingGreenlet 兼容问题；前者天然幂等且类型与
app/models/recommend.py 对齐。运行：SciMKG python test/migrate_recommend_tables.py
"""
import asyncio
import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
)

CREATE_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS recommend_records (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        user_id VARCHAR(36) NOT NULL,
        title VARCHAR(512) NOT NULL,
        correlation_score INT NOT NULL DEFAULT 0,
        reproducibility_score INT NOT NULL DEFAULT 0,
        feedback_score INT NOT NULL DEFAULT 0,
        total_score INT NOT NULL DEFAULT 0,
        repos JSON,
        reason VARCHAR(1000),
        backend VARCHAR(20) NOT NULL DEFAULT 'builtin',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_rec_user (user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS recommend_feedback (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        user_id VARCHAR(36) NOT NULL,
        record_id VARCHAR(36),
        repo VARCHAR(300) NOT NULL,
        sentiment VARCHAR(10) NOT NULL,
        comment VARCHAR(500),
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uq_rec_feedback_user_repo (user_id, repo),
        INDEX idx_rec_fb_record (record_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
]


async def main() -> int:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.core.config import settings

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            for ddl in CREATE_TABLES:
                await conn.execute(text(ddl))
            await conn.commit()
    finally:
        await engine.dispose()
    print("已建表/确认存在：recommend_records, recommend_feedback（幂等）")
    return 0


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:  # noqa: BLE001
        print("迁移失败：", e)
        sys.exit(1)
