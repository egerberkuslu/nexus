"""mano external resource mirror

Revision ID: 0006_mano_external_mirror
Revises: 0005_mano_external_backend
Create Date: 2025-12-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006_mano_external_mirror"
down_revision = "0005_mano_external_backend"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    has_mano_external_resource = inspector.has_table("mano_external_resource")
    if not has_mano_external_resource:
        op.create_table(
            "mano_external_resource",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("backend", sa.String(length=32), nullable=False),
            sa.Column("topology_id", sa.String(length=64), nullable=True),
            sa.Column("resource_type", sa.String(length=64), nullable=False),
            sa.Column("external_id", sa.String(length=128), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("checksum", sa.String(length=64), nullable=True),
            sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("first_seen_at", sa.DateTime(), nullable=True),
            sa.Column("last_seen_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("backend", "topology_id", "resource_type", "external_id", name="uq_mano_external_resource_key"),
        )
        has_mano_external_resource = True

    if has_mano_external_resource:
        op.execute(
            """
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'uq_mano_external_resource_key'
  ) THEN
    ALTER TABLE mano_external_resource
      ADD CONSTRAINT uq_mano_external_resource_key
      UNIQUE (backend, topology_id, resource_type, external_id);
  END IF;
END $$;
"""
        )
        op.execute("CREATE INDEX IF NOT EXISTS ix_mano_external_resource_backend ON mano_external_resource (backend)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_mano_external_resource_topology_id ON mano_external_resource (topology_id)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_mano_external_resource_resource_type ON mano_external_resource (resource_type)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_mano_external_resource_external_id ON mano_external_resource (external_id)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_mano_external_resource_deleted ON mano_external_resource (deleted)")


def downgrade() -> None:
    op.drop_index("ix_mano_external_resource_deleted", table_name="mano_external_resource")
    op.drop_index("ix_mano_external_resource_external_id", table_name="mano_external_resource")
    op.drop_index("ix_mano_external_resource_resource_type", table_name="mano_external_resource")
    op.drop_index("ix_mano_external_resource_topology_id", table_name="mano_external_resource")
    op.drop_index("ix_mano_external_resource_backend", table_name="mano_external_resource")
    op.drop_table("mano_external_resource")
