from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_mano_vnfm_vnf"
down_revision = "0002_mano_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    has_mano_vnf_instance = inspector.has_table("mano_vnf_instance")
    if not has_mano_vnf_instance:
        op.create_table(
            "mano_vnf_instance",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("ns_instance_id", sa.String(length=64), nullable=True),
            sa.Column("vnfd_id", sa.String(length=64), nullable=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("device_type", sa.String(length=32), nullable=False, server_default="container"),
            sa.Column("device_name", sa.String(length=255), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="CREATED"),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("properties", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

        has_mano_vnf_instance = True

    if has_mano_vnf_instance:
        op.execute(
            "CREATE INDEX IF NOT EXISTS mano_vnf_instance_ns_instance_id_idx "
            "ON mano_vnf_instance (ns_instance_id)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS mano_vnf_instance_status_idx "
            "ON mano_vnf_instance (status)"
        )


def downgrade() -> None:
    op.drop_index("mano_vnf_instance_status_idx", table_name="mano_vnf_instance")
    op.drop_index("mano_vnf_instance_ns_instance_id_idx", table_name="mano_vnf_instance")
    op.drop_table("mano_vnf_instance")
