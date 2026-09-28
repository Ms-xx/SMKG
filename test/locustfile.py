# -*- coding: utf-8 -*-
"""
Locust 压测脚本（步骤 10.3）。

业务读写混合场景，权重比 6:2:1:1（业务读写占比 ≥ 80%）：
- 登录 → 文档列表（分页/筛选）→ 文档详情（权重 6，读路径）
- 团队统计（命中缓存）（权重 2）
- 图谱搜索（权重 1）
- 问答轻量请求（权重 1）

用法：
    locust -f test/locustfile.py --headless -u 10 -r 5 -t 3m --html outputs/perf/locust_10.html
    locust -f test/locustfile.py --headless -u 50 -r 5 -t 3m --html outputs/perf/locust_50.html
    locust -f test/locustfile.py --headless -u 100 -r 5 -t 3m --html outputs/perf/locust_100.html

对比实验（缓存/索引开关）：
    1. 基线轮：默认配置执行三档梯度；
    2. 优化轮：开启缓存（REDIS_URL 已配置）/确认索引后重跑；
    3. 回滚：关闭缓存（设置 CACHE_ENABLED=false）或删除索引即可。
"""
from __future__ import annotations

import os
import random

try:
    from locust import HttpUser, between, task
except ImportError:
    # locust 未安装时允许模块导入（供静态检查），实际执行需安装 locust
    HttpUser = object  # type: ignore

    def task(weight=1):  # type: ignore
        def deco(f):
            return f

        return deco

    def between(a, b):  # type: ignore
        return (a + b) / 2


# 测试账号（与 test/citation_graph_e2e.py:22-24 对齐）
TEST_USERNAME = os.environ.get("PERF_USERNAME", "admin")
TEST_PASSWORD = os.environ.get("PERF_PASSWORD", "admin123")
API_PREFIX = "/api/v1"


class PlatformUser(HttpUser):  # type: ignore
    """平台压测用户：登录获取 Token 后执行业务读写混合任务。"""

    wait_time = between(1, 3)
    token: str | None = None
    doc_ids: list[str] = []

    def on_start(self) -> None:
        """登录获取 Token。"""
        resp = self.client.post(
            f"{API_PREFIX}/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
            name="登录",
        )
        if resp.status_code == 200:
            data = resp.json()
            self.token = data.get("access_token") or data.get("token")
            self.client.headers.update({"Authorization": f"Bearer {self.token}"})
            # 预取文档 id 列表
            self._fetch_doc_ids()

    def _fetch_doc_ids(self) -> None:
        resp = self.client.get(
            f"{API_PREFIX}/documents",
            params={"page": 1, "page_size": 20},
            name="预取文档列表",
        )
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items") or data.get("data") or []
            self.doc_ids = [str(d.get("id")) for d in items if d.get("id")]

    @task(6)
    def browse_documents(self) -> None:
        """文档列表（分页/筛选）+ 文档详情（读路径，权重 6）。"""
        page = random.randint(1, 5)
        self.client.get(
            f"{API_PREFIX}/documents",
            params={"page": page, "page_size": 10},
            name="文档列表(分页)",
        )
        if self.doc_ids:
            doc_id = random.choice(self.doc_ids)
            self.client.get(
                f"{API_PREFIX}/documents/{doc_id}",
                name="文档详情",
            )

    @task(2)
    def team_statistics(self) -> None:
        """团队统计（命中缓存路径，权重 2）。"""
        self.client.get(f"{API_PREFIX}/statistics/team", name="团队统计(缓存)")

    @task(1)
    def graph_search(self) -> None:
        """图谱搜索（权重 1）。"""
        # 关键词与当前真实语料对齐（arXiv 机器学习方向），保证搜索确实打到数据而非空结果
        keywords = [
            "Attention",
            "Neural Machine Translation",
            "Layer Normalization",
            "LSTM",
            "perovskite",
        ]
        kw = random.choice(keywords)
        # 注：接口参数为 query（非 keyword），limit 上限 100，见 knowledge_graph.search_graph
        self.client.get(
            f"{API_PREFIX}/knowledge-graph/search",
            params={"query": kw, "limit": 10},
            name="图谱搜索",
        )

    @task(1)
    def lightweight_qa(self) -> None:
        """问答轻量请求（权重 1）：走 /multi-agent/run 的 builtin 编排（不接 LLM，毫秒级）。"""
        questions = [
            "什么是 Transformer？",
            "GNN 的原理是什么？",
            "层归一化的作用是什么？",
        ]
        q = random.choice(questions)
        # 注：多 Agent 接口为 POST /multi-agent/run，mode 取 vote|merge|arbitrate
        self.client.post(
            f"{API_PREFIX}/multi-agent/run",
            json={"query": q, "mode": "vote"},
            name="问答轻量请求",
        )
