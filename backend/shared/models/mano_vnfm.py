"""
Database models for MANO VNFM layer (VNF/CNF instance tracking).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, JSON, String, Text

from .base import Base


class ManoVNFInstance(Base):
    __tablename__ = "mano_vnf_instance"

    id = Column(String(64), primary_key=True)  # vnf_instance_id
    ns_instance_id = Column(String(64), nullable=True)
    vnfd_id = Column(String(64), nullable=True)

    name = Column(String(255), nullable=False)
    device_type = Column(String(32), nullable=False, default="container")
    device_name = Column(String(255), nullable=True)  # runtime identifier in emulation

    status = Column(String(32), nullable=False, default="CREATED")
    message = Column(Text, nullable=True)

    properties = Column(JSON, nullable=False, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
