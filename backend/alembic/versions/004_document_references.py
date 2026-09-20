"""文档参考文献解析：新增 references 字段

Revision ID: 004_document_references
Create Date: 2026-09-20
"""

import sqlalchemy as sa

from alembic import op

revision = "004_document_references"
down_revision = "003_task_assignment"
branch_labels = None
depends_on = None


def upgrade():
    # `references` 为 MySQL 保留字，SQLAlchemy 会自动加反引号
    op.add_column("documents", sa.Column("references", sa.JSON(), nullable=True))
    # 回填已有记录的 references 为空数组，避免 Pydantic 校验 NULL 失败
    op.execute("UPDATE documents SET `references` = JSON_ARRAY() WHERE `references` IS NULL")


def downgrade():
    op.drop_column("documents", "references")
