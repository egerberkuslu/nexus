"""
Database models for AI run observability and per-topology pinned context.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from .base import Base


class AIRun(Base):
    __tablename__ = "ai_run"

    id = Column(String(64), primary_key=True)
    thread_id = Column(String(64), ForeignKey("ai_thread.id", ondelete="CASCADE"), nullable=False)
    topology_id = Column(String(64), nullable=True)
    thread_agent_id = Column(String(64), nullable=False)
    agent_id = Column(String(64), nullable=False)
    provider = Column(String(16), nullable=False)
    model = Column(String(128), nullable=False)
    request_id = Column(String(64), nullable=False)

    route_json = Column(Text, nullable=True)
    usage_json = Column(Text, nullable=True)
    status = Column(String(16), nullable=False, default="success")
    error_json = Column(Text, nullable=True)

    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    duration_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AIPinnedContext(Base):
    __tablename__ = "ai_pinned_context"

    topology_id = Column(String(64), primary_key=True)
    emulation_id = Column(String(128), nullable=True)
    container_id = Column(String(128), nullable=True)
    container_name = Column(String(256), nullable=True)
    content_md = Column(Text, nullable=True)
    content_json = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
