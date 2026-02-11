"""
Database models for AI agents, threads, messages, tool calls, and artifacts.
"""

import os
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .base import Base

from pgvector.sqlalchemy import Vector

AI_EMBED_DIM = int(os.getenv("AI_EMBED_DIM", "768"))


class AIAgent(Base):
    __tablename__ = "ai_agent"

    id = Column(String(64), primary_key=True)  # stable id e.g. "diagnostics"
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    scope = Column(String(16), nullable=False, default="both")  # global|topology|both
    allowed_prefixes_json = Column(Text, nullable=False, default="[]")
    allowed_methods_json = Column(Text, nullable=False, default='["GET"]')
    system_prompt = Column(Text, nullable=False, default="")
    is_builtin = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class AIThread(Base):
    __tablename__ = "ai_thread"

    id = Column(String(64), primary_key=True)  # uuid string
    agent_id = Column(String(64), ForeignKey("ai_agent.id"), nullable=False)
    topology_id = Column(String(64), nullable=True)  # null => global thread
    title = Column(String(200), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    agent = relationship("AIAgent")


class AIMessage(Base):
    __tablename__ = "ai_message"

    id = Column(String(64), primary_key=True)  # uuid string
    thread_id = Column(String(64), ForeignKey("ai_thread.id"), nullable=False)
    role = Column(String(16), nullable=False)  # user|assistant|system
    content_md = Column(Text, nullable=False, default="")
    meta_json = Column(Text, nullable=True)
    embedding_json = Column(Text, nullable=True)  # optional vector (JSON list[float])
    embedding_vec = Column(Vector(AI_EMBED_DIM), nullable=True)  # pgvector

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AIToolCall(Base):
    __tablename__ = "ai_tool_call"

    id = Column(String(64), primary_key=True)  # uuid string
    message_id = Column(String(64), ForeignKey("ai_message.id"), nullable=False)
    toon = Column(Text, nullable=False, default="")
    status = Column(String(16), nullable=False, default="success")  # running|success|error
    result_json = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AIArtifact(Base):
    __tablename__ = "ai_artifact"

    id = Column(String(64), primary_key=True)  # uuid string
    thread_id = Column(String(64), ForeignKey("ai_thread.id"), nullable=False)
    type = Column(String(64), nullable=False)  # report|diagnostic_summary|...
    title = Column(String(200), nullable=True)
    content_md = Column(Text, nullable=True)
    content_json = Column(Text, nullable=True)
    embedding_vec = Column(Vector(AI_EMBED_DIM), nullable=True)  # pgvector

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
