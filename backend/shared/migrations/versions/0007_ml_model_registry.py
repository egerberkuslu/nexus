"""ml model registry

Revision ID: 0007_ml_model_registry
Revises: 0006_mano_external_mirror
Create Date: 2026-01-05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_ml_model_registry"
down_revision = "0006_mano_external_mirror"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "ml_model" not in existing_tables:
        op.create_table(
            "ml_model",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("task", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("algorithm", sa.String(length=128), nullable=True),
            sa.Column("framework", sa.String(length=32), nullable=False, server_default=sa.text("'builtin'")),
            sa.Column("version", sa.String(length=64), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("artifact_path", sa.Text(), nullable=True),
            sa.Column("artifact_filename", sa.String(length=255), nullable=True),
            sa.Column("artifact_sha256", sa.String(length=64), nullable=True),
            sa.Column("artifact_size_bytes", sa.Integer(), nullable=True),
            sa.Column("input_schema", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("output_schema", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("meta", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ml_model_task_idx", "ml_model", ["task"])
        op.create_index("ml_model_framework_idx", "ml_model", ["framework"])

    if "ml_model" in existing_tables or inspector.has_table("ml_model"):
        op.execute("CREATE INDEX IF NOT EXISTS ml_model_task_idx ON ml_model (task)")
        op.execute("CREATE INDEX IF NOT EXISTS ml_model_framework_idx ON ml_model (framework)")

    if "ml_model_assignment" not in existing_tables:
        op.create_table(
            "ml_model_assignment",
            sa.Column("task", sa.String(length=64), primary_key=True),
            sa.Column("model_id", sa.String(length=64), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ml_model_assignment_model_id_idx", "ml_model_assignment", ["model_id"])

    if "ml_model_assignment" in existing_tables or inspector.has_table("ml_model_assignment"):
        op.execute(
            "CREATE INDEX IF NOT EXISTS ml_model_assignment_model_id_idx "
            "ON ml_model_assignment (model_id)"
        )


def downgrade() -> None:
    op.drop_index("ml_model_assignment_model_id_idx", table_name="ml_model_assignment")
    op.drop_table("ml_model_assignment")
    op.drop_index("ml_model_framework_idx", table_name="ml_model")
    op.drop_index("ml_model_task_idx", table_name="ml_model")
    op.drop_table("ml_model")
