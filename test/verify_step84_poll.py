# -*- coding: utf-8 -*-
"""8.4 端到端验证：Redis 持久化跟踪 + paper_tracking_poll 真实检索。backend 目录运行。"""
import json
import os
import sys

sys.path.insert(0, os.path.abspath("."))

try:
    import redis
except ImportError:
    redis = None

from app.core.config import settings  # noqa: E402

if redis is None:
    print("SKIP: redis 库不可用")
    sys.exit(0)

r = redis.from_url(settings.REDIS_URL, decode_responses=True)

# 写入一条跟踪（模拟 /tracking 后的持久化）
r.set(
    "paper:tracking",
    json.dumps(
        {
            "items": [
                {
                    "id": "demo_track",
                    "query": "attention is all you need",
                    "source": "arxiv",
                    "interval_days": 7,
                    "created_at": "",
                }
            ]
        }
    ),
)
print("== 触发 paper_tracking_poll ==")
from app.workers.paper_tasks import _run_poll  # noqa: E402

res = _run_poll()
print("status:", res["status"], "| checked:", res["checked"], "| new:", res["new_papers"], "| ingested:", res["ingested"])
for it in res["items"][:3]:
    print("  new title:", (it.get("title") or "")[:50], "| ingest:", it.get("ingest"))

# 再次运行应去重（new_papers=0）
res2 = _run_poll()
print("再次轮询 new:", res2["new_papers"], "(应去重为 0)")
# 清理演示数据
r.delete("paper:tracking", "paper:seen:demo_track")
print("清理演示数据完成")