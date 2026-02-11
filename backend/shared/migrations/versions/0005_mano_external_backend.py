"""mano external backend fields

Revision ID: 0005_mano_external_backend
Revises: 0004_runtime_state
Create Date: 2025-12-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_mano_external_backend"
down_revision = "0004_runtime_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("mano_ns_instance"):
        return

    existing_columns = {col["name"] for col in inspector.get_columns("mano_ns_instance")}
    if "backend" not in existing_columns:
        op.add_column("mano_ns_instance", sa.Column("backend", sa.String(length=32), nullable=False, server_default="local"))
    if "external_id" not in existing_columns:
        op.add_column("mano_ns_instance", sa.Column("external_id", sa.String(length=128), nullable=True))
    if "external_ref" not in existing_columns:
        op.add_column("mano_ns_instance", sa.Column("external_ref", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")))

    op.execute("CREATE INDEX IF NOT EXISTS ix_mano_ns_instance_backend ON mano_ns_instance (backend)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_mano_ns_instance_external_id ON mano_ns_instance (external_id)")


def downgrade() -> None:
    op.drop_index("ix_mano_ns_instance_external_id", table_name="mano_ns_instance")
    op.drop_index("ix_mano_ns_instance_backend", table_name="mano_ns_instance")
    op.drop_column("mano_ns_instance", "external_ref")
    op.drop_column("mano_ns_instance", "external_id")
    op.drop_column("mano_ns_instance", "backend")
