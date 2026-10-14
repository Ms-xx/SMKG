# -*- coding: utf-8 -*-
"""
论文检索与推荐服务门面（插件化架构迁移：实现已迁至 `app/plugins/paper_retrieval/service.py`）。

- 兼容再导出：既有 `from app.services.paper_retrieval_service import PaperRetrievalService /
  paper_retrieval_service / search_arxiv / search_pubmed / recommend / pdf_url / re_findall /
  _http_get / _http_get_bytes` 不受影响。
- 测试经本门面对模块级辅助函数（`_http_get` / `_http_get_bytes`）打补丁，插件实现运行期经
  `_core()` 动态寻址门面读取补丁，保证打补丁生效。
"""

from __future__ import annotations

from app.plugins.paper_retrieval.service import (
    PaperRetrievalService,
    _http_get,
    _http_get_bytes,
    paper_retrieval_service,
    pdf_url,
    re_findall,
    recommend,
    search_arxiv,
    search_pubmed,
)

__all__ = [
    "PaperRetrievalService",
    "paper_retrieval_service",
    "search_arxiv",
    "search_pubmed",
    "recommend",
    "pdf_url",
    "re_findall",
    "_http_get",
    "_http_get_bytes",
]
