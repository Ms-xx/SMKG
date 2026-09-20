"""增加标注多级审核（初审 → 终审）字段

Revision ID: 002_multi_level_review
Create Date: 2026-09-08
"""

import sqlalchemy as sa

from alembic import op

revision = "002_multi_level_review"
down_revision = "initial_schema"
branch_labels = None
depends_on = None


def upgrade():
    # 初审字段
    op.add_column("annotations", sa.Column("first_reviewed_by", sa.String(36), nullable=True))
    op.add_column("annotations", sa.Column("first_review_comment", sa.Text(), nullable=True))
    op.add_column("annotations", sa.Column("first_reviewed_at", sa.DateTime(), nullable=True))
    # 终审字段
    op.add_column("annotations", sa.Column("final_reviewed_by", sa.String(36), nullable=True))
    op.add_column("annotations", sa.Column("final_review_comment", sa.Text(), nullable=True))
    op.add_column("annotations", sa.Column("final_reviewed_at", sa.DateTime(), nullable=True))
    # 移除旧的单级审核字段（被初审/终审取代）
    op.drop_column("annotations", "reviewed_by")
    op.drop_column("annotations", "review_comment")


def downgrade():
    op.add_column("annotations", sa.Column("reviewed_by", sa.String(36), nullable=True))
    op.add_column("annotations", sa.Column("review_comment", sa.Text(), nullable=True))
    op.drop_column("annotations", "final_reviewed_at")
    op.drop_column("annotations", "final_review_comment")
    op.drop_column("annotations", "final_reviewed_by")
    op.drop_column("annotations", "first_reviewed_at")
    op.drop_column("annotations", "first_review_comment")
    op.drop_column("annotations", "first_reviewed_by")
