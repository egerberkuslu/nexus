from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_mano_core"
down_revision = "0001_pgvector_observability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    has_mano_vnfd = inspector.has_table("mano_vnfd")
    if not has_mano_vnfd:
        op.create_table(
            "mano_vnfd",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("version", sa.String(length=64), nullable=False, server_default="1.0"),
            sa.Column("provider", sa.String(length=255), nullable=True),
            sa.Column("descriptor", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

    has_mano_nsd = inspector.has_table("mano_nsd")
    if not has_mano_nsd:
        op.create_table(
            "mano_nsd",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("version", sa.String(length=64), nullable=False, server_default="1.0"),
            sa.Column("provider", sa.String(length=255), nullable=True),
            sa.Column("descriptor", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

    has_mano_ns_instance = inspector.has_table("mano_ns_instance")
    if not has_mano_ns_instance:
        op.create_table(
            "mano_ns_instance",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("topology_id", sa.String(length=64), nullable=True),
            sa.Column("nsd_id", sa.String(length=64), nullable=True),
            sa.Column("emulation_id", sa.String(length=128), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="CREATED"),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

    has_mano_ns_instance = True
    if has_mano_ns_instance:
        op.execute(
            "CREATE INDEX IF NOT EXISTS mano_ns_instance_topology_id_idx "
            "ON mano_ns_instance (topology_id)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS mano_ns_instance_status_idx "
            "ON mano_ns_instance (status)"
        )

    has_mano_operation = inspector.has_table("mano_operation")
    if not has_mano_operation:
        op.create_table(
            "mano_operation",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("ns_instance_id", sa.String(length=64), nullable=True),
            sa.Column("kind", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="RUNNING"),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("request", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("result", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )

    has_mano_operation = True
    if has_mano_operation:
        op.execute(
            "CREATE INDEX IF NOT EXISTS mano_operation_ns_instance_id_idx "
            "ON mano_operation (ns_instance_id)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS mano_operation_status_idx "
            "ON mano_operation (status)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS mano_operation_kind_idx "
            "ON mano_operation (kind)"
        )


def downgrade() -> None:
    op.drop_index("mano_operation_kind_idx", table_name="mano_operation")
    op.drop_index("mano_operation_status_idx", table_name="mano_operation")
    op.drop_index("mano_operation_ns_instance_id_idx", table_name="mano_operation")
    op.drop_table("mano_operation")

    op.drop_index("mano_ns_instance_status_idx", table_name="mano_ns_instance")
    op.drop_index("mano_ns_instance_topology_id_idx", table_name="mano_ns_instance")
    op.drop_table("mano_ns_instance")

    op.drop_table("mano_nsd")
    op.drop_table("mano_vnfd")
