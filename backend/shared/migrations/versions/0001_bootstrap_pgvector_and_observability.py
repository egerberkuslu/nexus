from __future__ import annotations

import os

from alembic import op


# revision identifiers, used by Alembic.
# NOTE: Alembic's default `alembic_version.version_num` is VARCHAR(32), so keep this <= 32 chars.
revision = "0001_pgvector_observability"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    dim = int(os.getenv("AI_EMBED_DIM", "768"))
    # pgvector extension + schema bootstrap + vector columns + indexes (idempotent)
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector";')

    # Create all tables for a fresh database (no-op for existing tables).
    # This intentionally uses the current SQLAlchemy metadata to bootstrap the legacy create_all flow
    # into Alembic, so services don't mutate schema in init_db anymore.
    from shared.models.base import Base
    from shared.models import topology  # noqa: F401
    from shared.models import snapshot  # noqa: F401
    from shared.models import ai  # noqa: F401
    from shared.models import ai_agents  # noqa: F401
    from shared.models import ai_runs  # noqa: F401
    from shared.models import network_config  # noqa: F401

    Base.metadata.create_all(bind=op.get_bind())

    # Add vector columns if tables already exist (for older DBs).
    op.execute(f"ALTER TABLE IF EXISTS ai_message ADD COLUMN IF NOT EXISTS embedding_vec vector({dim});")
    op.execute(f"ALTER TABLE IF EXISTS ai_artifact ADD COLUMN IF NOT EXISTS embedding_vec vector({dim});")

    # Indexes (create only if table exists).
    op.execute(
        """
DO $$
BEGIN
  IF to_regclass('public.ai_message') IS NOT NULL THEN
    BEGIN
      CREATE INDEX IF NOT EXISTS ai_message_embedding_vec_hnsw
        ON ai_message USING hnsw (embedding_vec vector_cosine_ops);
    EXCEPTION WHEN OTHERS THEN
      -- HNSW may not be supported depending on pgvector version; keep startup resilient.
      NULL;
    END;
    BEGIN
      CREATE INDEX IF NOT EXISTS ai_message_embedding_vec_ivfflat
        ON ai_message USING ivfflat (embedding_vec vector_cosine_ops) WITH (lists = 100);
    EXCEPTION WHEN OTHERS THEN
      NULL;
    END;
  END IF;
END $$;
"""
    )
    op.execute(
        """
DO $$
BEGIN
  IF to_regclass('public.ai_artifact') IS NOT NULL THEN
    BEGIN
      CREATE INDEX IF NOT EXISTS ai_artifact_embedding_vec_hnsw
        ON ai_artifact USING hnsw (embedding_vec vector_cosine_ops);
    EXCEPTION WHEN OTHERS THEN
      NULL;
    END;
    BEGIN
      CREATE INDEX IF NOT EXISTS ai_artifact_embedding_vec_ivfflat
        ON ai_artifact USING ivfflat (embedding_vec vector_cosine_ops) WITH (lists = 50);
    EXCEPTION WHEN OTHERS THEN
      NULL;
    END;
  END IF;
END $$;
"""
    )

    # Observability: ai_run table (created only if ai_thread exists).
    op.execute(
        """
DO $$
BEGIN
  IF to_regclass('public.ai_thread') IS NOT NULL AND to_regclass('public.ai_run') IS NULL THEN
    CREATE TABLE ai_run (
      id varchar(64) PRIMARY KEY,
      thread_id varchar(64) NOT NULL REFERENCES ai_thread(id) ON DELETE CASCADE,
      topology_id varchar(64) NULL,
      thread_agent_id varchar(64) NOT NULL,
      agent_id varchar(64) NOT NULL,
      provider varchar(16) NOT NULL,
      model varchar(128) NOT NULL,
      request_id varchar(64) NOT NULL,
      route_json text NULL,
      usage_json text NULL,
      status varchar(16) NOT NULL DEFAULT 'success',
      error_json text NULL,
      started_at timestamp without time zone NOT NULL,
      finished_at timestamp without time zone NOT NULL,
      duration_ms integer NULL,
      created_at timestamp without time zone NOT NULL
    );
    CREATE INDEX ai_run_thread_id_idx ON ai_run(thread_id);
    CREATE INDEX ai_run_topology_id_idx ON ai_run(topology_id);
    CREATE INDEX ai_run_created_at_idx ON ai_run(created_at);
  END IF;
END $$;
"""
    )

    # Per-topology pinned context (to stop agent guessing).
    op.execute(
        """
DO $$
BEGIN
  IF to_regclass('public.ai_pinned_context') IS NULL THEN
    CREATE TABLE ai_pinned_context (
      topology_id varchar(64) PRIMARY KEY,
      emulation_id varchar(128) NULL,
      container_id varchar(128) NULL,
      container_name varchar(256) NULL,
      content_md text NULL,
      content_json text NULL,
      updated_at timestamp without time zone NOT NULL
    );
    CREATE INDEX ai_pinned_context_updated_at_idx ON ai_pinned_context(updated_at);
  END IF;
END $$;
"""
    )


def downgrade() -> None:
    # Best-effort down migration (keep extension).
    op.execute("DROP TABLE IF EXISTS ai_run;")
    op.execute("DROP TABLE IF EXISTS ai_pinned_context;")
    op.execute("DROP INDEX IF EXISTS ai_message_embedding_vec_hnsw;")
    op.execute("DROP INDEX IF EXISTS ai_message_embedding_vec_ivfflat;")
    op.execute("DROP INDEX IF EXISTS ai_artifact_embedding_vec_hnsw;")
    op.execute("DROP INDEX IF EXISTS ai_artifact_embedding_vec_ivfflat;")
