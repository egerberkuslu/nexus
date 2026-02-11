"""
Database models for AI gateway configuration
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text

from .base import Base


class AIProviderConfig(Base):
    __tablename__ = "ai_provider_config"

    provider = Column(String(32), primary_key=True)  # openai/anthropic/gemini/ollama
    api_key_encrypted = Column(Text, nullable=True)
    default_model = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
