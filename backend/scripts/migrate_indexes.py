# -*- coding: utf-8 -*-
"""
XiangMu 步骤 10.1：为存量 MySQL 幂等补充性能索引（基于 information_schema 判断，已存在则跳过）。

用法（在 backend 目录，需本地 backend/.env 提供 DATABASE_URL）：
    python -m scripts.migrate_indexes
"""
import sys
from contextlib import contextmanager

from sqlalchemy import create_engine, text

from app.core.config import settings

INDEXES = {
    "documents": [
        ("ix_documents_uploaded_by", "uploaded_by"),
        ("ix_documents_status", "status"),
        ("ix_documents_created_at", "created_at"),
    ],
    "document_pages": [
        ("ix_pages_doc_page", "document_id, page_number"),
        ("ix_pages_document_id", "document_id"),
    ],
    "document_elements": [
        ("ix_elements_page_id", "page_id"),
        ("ix_elements_type", "element_type"),
    ],
    "tasks": [
        ("ix_tasks_document_id", "document_id"),
        ("ix_tasks_assigned_status", "assigned_to, status"),
    ],
    "annotations": [
        ("ix_annotations_document_id", "document_id"),
        ("ix_annotations_annotator_status", "annotated_by, status"),
    ],
}

engine = create_engine(settings.DATABASE_URL.replace("+aiomysql", "+pymysql"))


@contextmanager
def conn():
    c = engine.connect()
    try:
        yield c
        c.commit()
    finally:
        c.close()


def existing_indexes(c) -> set[str]:
    return {
        r[0]
        for r in c.execute(
            text(
                "SELECT INDEX_NAME FROM information_schema.statistics "
                "WHERE TABLE_SCHEMA = DATABASE() GROUP BY TABLE_NAME, INDEX_NAME"
            )
        ).all()
    }


def main() -> None:
    with conn() as c:
        has = existing_indexes(c)
        created, skipped = 0, 0
        for table, indexes in INDEXES.items():
            for name, cols in indexes:
                if name in has:  # 幂等：existing+已存在的列
                    existing_cols = {
                        r[0]
                        for r in c.execute(
                            text(
                                "SELECT COLUMN_NAME FROM information_schema.statistics "
                                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t "
                                "AND INDEX_NAME = :n"
                            ),
                            {"t": table, "n": name},
                        ).all()
                    }
                    if cols.replace(" ", "").startswith(",".join(existing_cols).replace(" ", "")):
                        skipped += 1
                        print(f"SKIP  {table}.{name} 已存在")
                        continue
                c.execute(text(f"ALTER TABLE `{table}` ADD INDEX `{name}` ({cols})"))
                created += 1
                print(f"OK    {table}.{name} ({cols})")
        print(f"\n完成：新建 {created} 个索引，跳过 {skipped} 个已存在索引。")


if __name__ == "__main__":
    sys.exit(main())