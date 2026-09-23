# -*- coding: utf-8 -*-
"""查询 8.3 实测文档的解析状态（判断 Celery worker 是否消化任务）。"""
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from sqlalchemy import text  # noqa: E402

from app.core.database import sync_engine  # noqa: E402

with sync_engine.connect() as c:
    rows = c.execute(
        text(
            "SELECT id, title, status, page_count FROM documents "
            "WHERE title LIKE '%Attention%' ORDER BY created_at DESC LIMIT 3"
        )
    ).all()
    print("docs:", [(x[0][:8], x[1], x[2], x[3]) for x in rows])