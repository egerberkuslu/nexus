from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _load_metadata():
    from shared.models.base import Base
    from shared.models import topology  # noqa: F401
    from shared.models import snapshot  # noqa: F401
    from shared.models import ai  # noqa: F401
    from shared.models import ai_agents  # noqa: F401
    from shared.models import ai_runs  # noqa: F401
    from shared.models import ml_models  # noqa: F401
    from shared.models import network_config  # noqa: F401
    from shared.models import mano  # noqa: F401
    from shared.models import mano_vnfm  # noqa: F401
    from shared.models import mano_external  # noqa: F401
    from shared.models import runtime  # noqa: F401

    return Base.metadata


target_metadata = _load_metadata()


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("sqlalchemy.url is not configured for offline migrations")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = config.attributes.get("connection", None)

    if connectable is None:
        cfg_section = config.get_section(config.config_ini_section, {})
        url = cfg_section.get("sqlalchemy.url") or os.getenv("DATABASE_URL")
        if url:
            cfg_section["sqlalchemy.url"] = url
        connectable = engine_from_config(cfg_section, prefix="sqlalchemy.", poolclass=pool.NullPool)

        with connectable.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
            with context.begin_transaction():
                context.run_migrations()
        return

    # connectable provided by the caller (already an open Connection)
    connection = connectable
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
