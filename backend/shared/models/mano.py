"""
Database models for MANO (OSM-like) catalog + lifecycle state.

These are "managed assets" MANO operates on: descriptors (VNFD/NSD), instances, and operations.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, JSON, String, Text

from .base import Base


class ManoVNFD(Base):
    __tablename__ = "mano_vnfd"

    id = Column(String(64), primary_key=True)  # vnfd_id
    name = Column(String(255), nullable=False)
    version = Column(String(64), nullable=False, default="1.0")
    provider = Column(String(255), nullable=True)
    descriptor = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ManoNSD(Base):
    __tablename__ = "mano_nsd"

    id = Column(String(64), primary_key=True)  # nsd_id
    name = Column(String(255), nullable=False)
    version = Column(String(64), nullable=False, default="1.0")
    provider = Column(String(255), nullable=True)
    descriptor = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ManoNSInstance(Base):
    __tablename__ = "mano_ns_instance"

    id = Column(String(64), primary_key=True)  # ns_instance_id
    name = Column(String(255), nullable=False)
    topology_id = Column(String(64), nullable=True)
    nsd_id = Column(String(64), nullable=True)
    emulation_id = Column(String(128), nullable=True)
    backend = Column(String(32), nullable=False, default="local")  # local|osm|...
    external_id = Column(String(128), nullable=True)  # ID in external NFVO (e.g., OSM)
    external_ref = Column(JSON, nullable=False, default=dict)  # extra external fields (project, vim_account_id, etc.)
    status = Column(String(32), nullable=False, default="CREATED")
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ManoOperation(Base):
    __tablename__ = "mano_operation"

    id = Column(String(64), primary_key=True)  # op_id
    ns_instance_id = Column(String(64), nullable=True)
    kind = Column(String(32), nullable=False)  # INSTANTIATE/TERMINATE/SCALE/HEAL...
    status = Column(String(32), nullable=False, default="RUNNING")  # RUNNING/SUCCESS/ERROR
    message = Column(Text, nullable=True)
    request = Column(JSON, nullable=False, default=dict)
    result = Column(JSON, nullable=False, default=dict)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
