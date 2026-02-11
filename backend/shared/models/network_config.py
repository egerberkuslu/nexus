"""
Network configuration models (runtime + persisted configs).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text

from .base import Base


class NetworkConfiguration(Base):
    __tablename__ = "network_configurations"

    id = Column(String(36), primary_key=True)
    topology_id = Column(String(36), ForeignKey("topologies.id"), nullable=False, index=True)

    name = Column(String(255), nullable=False, default="Network Configuration")
    description = Column(Text)

    version = Column(Integer, nullable=False, default=1)
    config = Column(JSON, nullable=False, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
