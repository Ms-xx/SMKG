"""
为 documents 表补充 `authors` / `affiliations` 结构化 JSON 列（幂等迁移脚本）。

背景：Base.metadata.create_all() 不会为已有表新增列，必须在既有数据库上手工 ALTER TABLE。
本脚本：
  1. 检查 documents 表是否已含 authors / affiliations 列，缺失则 ADD COLUMN；
  2. 对已存在的 JSON 列做 NULL → JSON_ARRAY() 回填，避免 Pydantic 读取 NULL 报错。

用法（在 backend 目录或设置好 DATABASE_URL 后执行）：
    python -m scripts.migrate_document_affiliations
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, inspect, text  # noqa: E402

from app.core.config import settings  # noqa: E402

_COLUMNS = ("authors", "affiliations")


def migrate() -> None:
    sync_url = settings.DATABASE_URL.replace("+aiomysql", "+pymysql")
    engine = create_engine(sync_url)

    with engine.begin() as conn:
        existing = {c["name"] for c in inspect(conn).get_columns("documents")}

        for col in _COLUMNS:
            if col in existing:
                print(f"[skip] documents.{col} 已存在")
                continue
            # authors/affiliations 均为 JSON 数组，新增后仍需回填
            conn.execute(text(f"ALTER TABLE documents ADD COLUMN `{col}` JSON NULL"))
            print(f"[add ] documents.{col} 已新增 JSON 列")

        # 重新读取最新列集合，统一回填 NULL → JSON_ARRAY()
        existing = {c["name"] for c in inspect(conn).get_columns("documents")}
        for col in _COLUMNS:
            if col in existing:
                conn.execute(
                    text(f"UPDATE documents SET `{col}` = JSON_ARRAY() WHERE `{col}` IS NULL")
                )
                print(f"[backfill] documents.{col} NULL → JSON_ARRAY()")

    print("迁移完成")


if __name__ == "__main__":
    migrate()
