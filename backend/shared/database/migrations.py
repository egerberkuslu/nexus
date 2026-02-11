"""
Alembic migration runner.

We keep this in shared/ so every microservice can run the same migrations.
"""

from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Engine
from sqlalchemy import text


def _alembic_config() -> Config:
    here = Path(__file__).resolve()
    shared_dir = here.parents[1]  # backend/shared
    migrations_dir = shared_dir / "migrations"
    cfg = Config()
    cfg.set_main_option("script_location", str(migrations_dir))
    cfg.set_main_option("version_locations", str(migrations_dir / "versions"))
    # keep log output quiet by default
    cfg.set_main_option("configure_logger", "false")
    return cfg


def run_migrations(engine: Engine) -> None:
    """
    Upgrade database schema to the latest Alembic head.

    Uses a Postgres advisory lock to avoid concurrent migration attempts across services.
    """
    cfg = _alembic_config()
    lock_key = int(os.getenv("ALEMBIC_ADVISORY_LOCK_KEY", "92831231"))
    with engine.connect() as conn:
        lock_conn = conn.execution_options(isolation_level="AUTOCOMMIT")
        lock_conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": lock_key})
        try:
            cfg.attributes["connection"] = conn
            command.upgrade(cfg, "head")
        finally:
            # If Alembic raised after executing SQL, the connection can be in an aborted transaction
            # state; clear it so the unlock always runs.
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                lock_conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": lock_key})
            except Exception:
                pass
