"""
External MANO resources (mirrors) for bidirectional integrations like ETSI OSM.

We keep a generic table so we can mirror multiple OSM resource types (VIM/WIM/SDN, packages,
instances, etc.) without coupling the core MANO tables to one backend.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, JSON, String

from .base import Base


class ManoExternalResource(Base):
    __tablename__ = "mano_external_resource"

    id = Column(String(64), primary_key=True)  # internal id (uuid hex)

    backend = Column(String(32), nullable=False)  # e.g. "osm"
    topology_id = Column(String(64), nullable=True)
    resource_type = Column(String(64), nullable=False)  # e.g. "vim_account", "ns_instance"

    external_id = Column(String(128), nullable=False)  # e.g. OSM _id
    name = Column(String(255), nullable=True)

    payload = Column(JSON, nullable=False, default=dict)  # full backend payload (best-effort)
    checksum = Column(String(64), nullable=True)
    deleted = Column(Boolean, nullable=False, default=False)

    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
