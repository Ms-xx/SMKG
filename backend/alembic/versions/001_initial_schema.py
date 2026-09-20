"""empty message

Revision ID: initial_schema
Create Date: 2026-04-06
"""

import sqlalchemy as sa

from alembic import op

revision = "initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(50), unique=True, nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(100)),
        sa.Column("avatar_url", sa.String(500)),
        sa.Column("role", sa.String(20), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.Column("last_login", sa.DateTime()),
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("doi", sa.String(100), unique=True),
        sa.Column("authors", sa.JSON(), server_default="[]"),
        sa.Column("abstract", sa.Text()),
        sa.Column("keywords", sa.JSON(), server_default="[]"),
        sa.Column("publication_date", sa.DateTime()),
        sa.Column("journal", sa.String(200)),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_size", sa.Integer()),
        sa.Column("page_count", sa.Integer()),
        sa.Column("status", sa.String(20), nullable=False, server_default="uploaded"),
        sa.Column("uploaded_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "document_pages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("image_path", sa.String(500)),
        sa.Column("elements", sa.JSON(), server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("document_id", "page_number"),
    )

    op.create_table(
        "document_elements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("page_id", sa.String(36), nullable=False),
        sa.Column("element_type", sa.String(20), nullable=False),
        sa.Column("bbox", sa.JSON(), nullable=False),
        sa.Column("content", sa.Text()),
        sa.Column("metadata", sa.JSON(), server_default="{}"),
        sa.Column("confidence", sa.Float()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_type", sa.String(30), nullable=False),
        sa.Column("document_id", sa.String(36)),
        sa.Column("assigned_to", sa.String(36)),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0"),
        sa.Column("params", sa.JSON(), server_default="{}"),
        sa.Column("result", sa.JSON(), server_default="{}"),
        sa.Column("error_message", sa.Text()),
        sa.Column("celery_task_id", sa.String(255)),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
    )

    op.create_table(
        "annotations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("element_id", sa.String(36)),
        sa.Column("annotation_type", sa.String(30), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("confidence", sa.Float()),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("annotated_by", sa.String(36), nullable=False),
        sa.Column("reviewed_by", sa.String(36)),
        sa.Column("review_comment", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "annotation_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("annotation_id", sa.String(36), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("changed_by", sa.String(36), nullable=False),
        sa.Column("change_type", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "operation_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36)),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("resource_type", sa.String(30), nullable=False),
        sa.Column("resource_id", sa.String(36)),
        sa.Column("details", sa.JSON(), server_default="{}"),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "models",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("model_type", sa.String(30), nullable=False),
        sa.Column("framework", sa.String(30)),
        sa.Column("file_path", sa.String(500)),
        sa.Column("metrics", sa.JSON(), server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(36)),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("name", "version"),
    )

    op.create_table(
        "training_experiments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("model_id", sa.String(36)),
        sa.Column("dataset_version", sa.String(50)),
        sa.Column("hyperparameters", sa.JSON(), server_default="{}"),
        sa.Column("metrics", sa.JSON(), server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("mlflow_run_id", sa.String(100)),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime()),
    )

    op.create_table(
        "system_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("key", sa.String(100), unique=True, nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("updated_by", sa.String(36)),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("refresh_token", sa.String(500), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("user_agent", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("user_sessions")
    op.drop_table("system_configs")
    op.drop_table("training_experiments")
    op.drop_table("models")
    op.drop_table("operation_logs")
    op.drop_table("annotation_versions")
    op.drop_table("annotations")
    op.drop_table("tasks")
    op.drop_table("document_elements")
    op.drop_table("document_pages")
    op.drop_table("documents")
    op.drop_table("users")
