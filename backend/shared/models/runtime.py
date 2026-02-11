"""
Database models for runtime state (devices/links) that exist in a running emulation.

These are not the same as Topology Nodes/Links (design-time). They represent what was
added dynamically at runtime (e.g. via Device Manager / MANO VNFM).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, JSON, String, Text

from .base import Base


class RuntimeDevice(Base):
    __tablename__ = "runtime_device"

    id = Column(String(64), primary_key=True)  # runtime_device_id (uuid)
    topology_id = Column(String(64), nullable=True, index=True)
    ns_instance_id = Column(String(64), nullable=True, index=True)

    name = Column(String(255), nullable=False, index=True)  # display name
    runtime_name = Column(String(64), nullable=True, index=True)  # mininet-safe runtime identifier
    device_type = Column(String(32), nullable=False)

    status = Column(String(32), nullable=False, default="active")
    properties = Column(JSON, nullable=False, default=dict)
    message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_seen_at = Column(DateTime, nullable=True)


class RuntimeLink(Base):
    __tablename__ = "runtime_link"

    id = Column(String(64), primary_key=True)  # runtime_link_id (uuid)
    topology_id = Column(String(64), nullable=True, index=True)
    ns_instance_id = Column(String(64), nullable=True, index=True)

    node1 = Column(String(255), nullable=False)
    node2 = Column(String(255), nullable=False)
    runtime_node1 = Column(String(64), nullable=True)
    runtime_node2 = Column(String(64), nullable=True)

    status = Column(String(32), nullable=False, default="active")
    properties = Column(JSON, nullable=False, default=dict)
    message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_seen_at = Column(DateTime, nullable=True)
