"""任务分配系统：新增 assigned_by/due_at 字段

Revision ID: 003_task_assignment
Create Date: 2026-09-08
"""

import sqlalchemy as sa

from alembic import op

revision = "003_task_assignment"
down_revision = "002_multi_level_review"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tasks", sa.Column("assigned_by", sa.String(36), nullable=True))
    op.add_column("tasks", sa.Column("due_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("tasks", "due_at")
    op.drop_column("tasks", "assigned_by")
