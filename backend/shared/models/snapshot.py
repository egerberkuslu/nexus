"""
Database models for snapshot management with Docker checkpoint support
"""

from sqlalchemy import (
    Column, String, Integer, BigInteger, Float, Boolean, DateTime,
    JSON, ForeignKey, Enum, Text
)
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from uuid import uuid4

from .base import Base


class SnapshotType(enum.Enum):
    """Snapshot type enumeration"""
    TOPOLOGY_ONLY = "topology_only"      # Quick topology export only
    DOCKER_COMMIT = "docker_commit"      # Docker filesystem snapshots
    CRIU_LIVE = "criu_live"              # CRIU live process checkpoints
    HYBRID_FULL = "hybrid_full"          # Combined Docker + CRIU


class SnapshotStatus(enum.Enum):
    """Snapshot lifecycle status"""
    PENDING = "pending"          # Created, waiting to start
    CAPTURING = "capturing"      # Capture in progress
    CAPTURED = "captured"        # Successfully captured
    FAILED = "failed"            # Capture failed
    RESTORING = "restoring"      # Restore in progress
    RESTORED = "restored"        # Successfully restored
    ARCHIVED = "archived"        # Archived/old snapshot


class Snapshot(Base):
    """
    Snapshot model for PostgreSQL
    Stores metadata for network topology snapshots with Docker checkpoint support
    """
    __tablename__ = "snapshots"
    __table_args__ = {'extend_existing': True}

    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # Foreign keys
    topology_id = Column(String(36), ForeignKey("topologies.id"), nullable=False)
    emulation_id = Column(String(100), nullable=True)  # Running emulation reference

    # Basic info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Snapshot type and status
    snapshot_type = Column(
        Enum(SnapshotType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=SnapshotType.TOPOLOGY_ONLY
    )
    status = Column(
        Enum(SnapshotStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=SnapshotStatus.PENDING
    )

    # Storage references
    mongo_state_id = Column(String(36), nullable=True)  # MongoDB document ID for state data
    checkpoint_path = Column(String(512), nullable=True)  # Local filesystem path

    # Size tracking
    size_bytes = Column(BigInteger, default=0)
    compressed = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    captured_at = Column(DateTime, nullable=True)
    restored_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)  # For retention policy

    # Capture metadata
    device_count = Column(Integer, default=0)
    container_count = Column(Integer, default=0)
    criu_available = Column(Boolean, default=False)
    capture_duration_seconds = Column(Float, nullable=True)

    # Target containers (optional - null means all)
    target_containers = Column(JSON, nullable=True)  # List of container names to snapshot

    # Error handling
    error_message = Column(Text, nullable=True)

    # Additional metadata
    extra_metadata = Column(JSON, default=dict)

    # Relationships
    topology = relationship("Topology", back_populates="snapshots")
    restore_history = relationship(
        "SnapshotRestoreHistory",
        back_populates="snapshot",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Snapshot(id={self.id}, name={self.name}, type={self.snapshot_type.value}, status={self.status.value})>"

    @property
    def size_mb(self) -> float:
        """Get size in megabytes"""
        return self.size_bytes / (1024 * 1024) if self.size_bytes else 0.0

    @property
    def is_complete(self) -> bool:
        """Check if snapshot capture is complete"""
        return self.status in [SnapshotStatus.CAPTURED, SnapshotStatus.RESTORED]

    @property
    def can_restore(self) -> bool:
        """Check if snapshot can be restored"""
        return self.status == SnapshotStatus.CAPTURED


class SnapshotRestoreHistory(Base):
    """
    Tracks restoration attempts for snapshots
    """
    __tablename__ = "snapshot_restore_history"
    __table_args__ = {'extend_existing': True}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    snapshot_id = Column(String(36), ForeignKey("snapshots.id"), nullable=False)

    # Restore info
    restored_at = Column(DateTime, default=datetime.utcnow)
    restored_by = Column(String(255), nullable=True)  # User or system
    target_topology_id = Column(String(36), nullable=True)  # If restoring to different topology

    # Status
    status = Column(String(50), nullable=False)  # success, failed, partial
    duration_seconds = Column(Float, nullable=True)

    # Details
    devices_restored = Column(Integer, default=0)
    containers_restored = Column(Integer, default=0)
    network_state_restored = Column(Boolean, default=False)

    # Error handling
    error_message = Column(Text, nullable=True)
    warnings = Column(JSON, default=list)
    rollback_performed = Column(Boolean, default=False)

    # Relationships
    snapshot = relationship("Snapshot", back_populates="restore_history")

    def __repr__(self):
        return f"<SnapshotRestoreHistory(id={self.id}, snapshot_id={self.snapshot_id}, status={self.status})>"


class SnapshotSchedule(Base):
    """
    Automatic snapshot scheduling configuration
    """
    __tablename__ = "snapshot_schedules"
    __table_args__ = {'extend_existing': True}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # Basic info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Target - null topology_id means global (all topologies)
    topology_id = Column(String(36), ForeignKey("topologies.id"), nullable=True)
    target_containers = Column(JSON, nullable=True)  # List of container names, null = all

    # Schedule configuration
    cron_expression = Column(String(100), nullable=False)  # e.g., "0 */6 * * *"
    snapshot_type = Column(
        Enum(SnapshotType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=SnapshotType.TOPOLOGY_ONLY
    )

    # Active state
    is_active = Column(Boolean, default=True)

    # Retention policy
    retention_count = Column(Integer, default=10)  # Keep N most recent
    retention_days = Column(Integer, nullable=True)  # Delete older than X days

    # Snapshot options
    compression = Column(Boolean, default=True)
    include_routing_tables = Column(Boolean, default=True)
    include_flow_tables = Column(Boolean, default=True)
    include_arp_tables = Column(Boolean, default=True)

    # Tracking
    last_run_at = Column(DateTime, nullable=True)
    last_snapshot_id = Column(String(36), nullable=True)  # Most recent snapshot created
    next_run_at = Column(DateTime, nullable=True)
    run_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    topology = relationship("Topology")

    def __repr__(self):
        return f"<SnapshotSchedule(id={self.id}, name={self.name}, cron={self.cron_expression}, active={self.is_active})>"

    @property
    def is_global(self) -> bool:
        """Check if schedule applies to all topologies"""
        return self.topology_id is None


# Export models
__all__ = [
    'SnapshotType',
    'SnapshotStatus',
    'Snapshot',
    'SnapshotRestoreHistory',
    'SnapshotSchedule'
]
