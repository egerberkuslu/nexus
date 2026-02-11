"""
Database models for topology management
"""

from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, JSON, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship, synonym
from sqlalchemy.ext.hybrid import hybrid_property
from datetime import datetime
import enum

from .base import Base


class DeviceType(enum.Enum):
    HOST = "host"
    SWITCH = "switch"
    ROUTER = "router"
    ACCESS_POINT = "ap"
    STATION = "station"
    P4SWITCH = "p4switch"
    CONTROLLER = "controller"


class LinkStatus(enum.Enum):
    UP = "up"
    DOWN = "down"


class EmulationStatus(enum.Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    owner = Column(String(255))

    topologies = relationship("Topology", back_populates="project", cascade="all, delete-orphan")


class Topology(Base):
    __tablename__ = "topologies"

    id = Column(String(36), primary_key=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=False)
    emulation_status = Column(Enum(EmulationStatus), default=EmulationStatus.STOPPED)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    topology_metadata = Column('metadata', JSON, default=dict)

    project = relationship("Project", back_populates="topologies")
    nodes = relationship("Node", back_populates="topology", cascade="all, delete-orphan")
    links = relationship("Link", back_populates="topology", cascade="all, delete-orphan")
    controllers = relationship("Controller", back_populates="topology", cascade="all, delete-orphan")
    snapshots = relationship("Snapshot", back_populates="topology", cascade="all, delete-orphan")


class Node(Base):
    __tablename__ = "nodes"

    id = Column(String(36), primary_key=True)
    topology_id = Column(String(36), ForeignKey("topologies.id"), nullable=False)
    name = Column(String(255), nullable=False)
    device_type = Column(Enum(DeviceType, values_callable=lambda x: [e.value for e in x]), nullable=False)
    x = Column(Float, default=0)
    y = Column(Float, default=0)
    properties = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    topology = relationship("Topology", back_populates="nodes")
    source_links = relationship("Link", foreign_keys="Link.source_node_id", back_populates="source_node")
    target_links = relationship("Link", foreign_keys="Link.target_node_id", back_populates="target_node")


class Link(Base):
    __tablename__ = "links"

    id = Column(String(36), primary_key=True)
    topology_id = Column(String(36), ForeignKey("topologies.id"), nullable=False)
    source_node_id = Column(String(36), ForeignKey("nodes.id"), nullable=False)
    target_node_id = Column(String(36), ForeignKey("nodes.id"), nullable=False)
    source_port = Column(String(50))
    target_port = Column(String(50))
    bandwidth = Column(Float)  # Mbps
    delay = Column(Float)  # ms
    loss = Column(Float)  # percentage
    max_queue_size = Column(Integer)
    status = Column(Enum(LinkStatus), default=LinkStatus.UP)
    properties = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    topology = relationship("Topology", back_populates="links")
    source_node = relationship("Node", foreign_keys=[source_node_id], back_populates="source_links")
    target_node = relationship("Node", foreign_keys=[target_node_id], back_populates="target_links")


class Controller(Base):
    __tablename__ = "controllers"

    id = Column(String(36), primary_key=True)
    topology_id = Column(String(36), ForeignKey("topologies.id"), nullable=False)
    name = Column(String(255), nullable=False)
    controller_type = Column(String(50))  # osken, ryu, odl, onos
    ip = Column(String(45))
    port = Column(Integer)
    is_active = Column(Boolean, default=True)
    properties = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)

    topology = relationship("Topology", back_populates="controllers")



# The Snapshot model is defined in snapshot.py to avoid circular imports
# Import it there and reference it in the Topology relationship
#
# NOTE: SQLAlchemy needs the Snapshot class to be imported/registered before mapper
# configuration, otherwise relationships like Topology.snapshots will fail to resolve.
from .snapshot import Snapshot  # noqa: F401


class Protocol(Base):
    __tablename__ = "protocols"

    id = Column(String(36), primary_key=True)
    node_id = Column(String(36), ForeignKey("nodes.id"), nullable=False)
    protocol_name = Column(String(50), nullable=False)  # ospf, bgp, rip, openflow, etc.
    protocol_version = Column(String(20))
    is_enabled = Column(Boolean, default=True)
    configuration = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProtocolPlugin(Base):
    __tablename__ = "protocol_plugins"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    plugin_type = Column(String(50))  # routing, openflow, wireless, etc.
    version = Column(String(20))
    description = Column(Text)
    config_schema = Column(JSON)  # JSON Schema for configuration
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
