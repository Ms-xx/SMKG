"""
评论服务门面（插件化架构迁移：实现已迁至 `app/plugins/comment/service.py`）。

- 兼容再导出：既有 `from app.services.comment_service import CommentService, MENTION_RE`
  不受影响。
- 运行期消费者应经 `registry.get("comment")` 动态寻址。
"""

from __future__ import annotations

from app.plugins.comment.service import MENTION_RE, CommentService

__all__ = ["CommentService", "MENTION_RE"]
