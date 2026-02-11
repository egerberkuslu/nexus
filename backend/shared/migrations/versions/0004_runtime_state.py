"""runtime state tables

Revision ID: 0004_runtime_state
Revises: 0003_mano_vnfm_vnf
Create Date: 2025-12-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_runtime_state"
down_revision = "0003_mano_vnfm_vnf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    has_runtime_device = inspector.has_table("runtime_device")
    if not has_runtime_device:
        op.create_table(
            "runtime_device",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("topology_id", sa.String(length=64), nullable=True),
            sa.Column("ns_instance_id", sa.String(length=64), nullable=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("runtime_name", sa.String(length=64), nullable=True),
            sa.Column("device_type", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("properties", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        )

        has_runtime_device = True

    if has_runtime_device:
        op.execute("CREATE INDEX IF NOT EXISTS ix_runtime_device_topology_id ON runtime_device (topology_id)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_runtime_device_ns_instance_id ON runtime_device (ns_instance_id)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_runtime_device_name ON runtime_device (name)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_runtime_device_runtime_name ON runtime_device (runtime_name)")

    has_runtime_link = inspector.has_table("runtime_link")
    if not has_runtime_link:
        op.create_table(
            "runtime_link",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("topology_id", sa.String(length=64), nullable=True),
            sa.Column("ns_instance_id", sa.String(length=64), nullable=True),
            sa.Column("node1", sa.String(length=255), nullable=False),
            sa.Column("node2", sa.String(length=255), nullable=False),
            sa.Column("runtime_node1", sa.String(length=64), nullable=True),
            sa.Column("runtime_node2", sa.String(length=64), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("properties", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        )

        has_runtime_link = True

    if has_runtime_link:
        op.execute("CREATE INDEX IF NOT EXISTS ix_runtime_link_topology_id ON runtime_link (topology_id)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_runtime_link_ns_instance_id ON runtime_link (ns_instance_id)")


def downgrade() -> None:
    op.drop_index("ix_runtime_link_ns_instance_id", table_name="runtime_link")
    op.drop_index("ix_runtime_link_topology_id", table_name="runtime_link")
    op.drop_table("runtime_link")

    op.drop_index("ix_runtime_device_runtime_name", table_name="runtime_device")
    op.drop_index("ix_runtime_device_name", table_name="runtime_device")
    op.drop_index("ix_runtime_device_ns_instance_id", table_name="runtime_device")
    op.drop_index("ix_runtime_device_topology_id", table_name="runtime_device")
    op.drop_table("runtime_device")
