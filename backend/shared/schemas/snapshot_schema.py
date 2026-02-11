"""
Pydantic schemas for snapshot management API
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, List, Any
from datetime import datetime
from enum import Enum


class SnapshotTypeEnum(str, Enum):
    """Snapshot type enumeration for API"""
    TOPOLOGY_ONLY = "topology_only"
    DOCKER_COMMIT = "docker_commit"
    CRIU_LIVE = "criu_live"
    HYBRID_FULL = "hybrid_full"


class SnapshotStatusEnum(str, Enum):
    """Snapshot status enumeration for API"""
    PENDING = "pending"
    CAPTURING = "capturing"
    CAPTURED = "captured"
    FAILED = "failed"
    RESTORING = "restoring"
    RESTORED = "restored"
    ARCHIVED = "archived"


# ==================== Request Schemas ====================

class SnapshotCreateRequest(BaseModel):
    """Request schema for creating a snapshot"""
    name: str = Field(..., min_length=1, max_length=255, description="Snapshot name")
    topology_id: str = Field(..., description="ID of the topology to snapshot")
    emulation_id: Optional[str] = Field(None, description="ID of the running emulation")
    snapshot_type: SnapshotTypeEnum = Field(
        default=SnapshotTypeEnum.HYBRID_FULL,
        description="Type of snapshot to create"
    )
    description: Optional[str] = Field(None, max_length=1000, description="Optional description")
    compression: bool = Field(default=True, description="Whether to compress the snapshot")

    # Target selection
    target_containers: Optional[List[str]] = Field(
        None,
        description="List of container names to snapshot. Null/empty means all containers"
    )

    # Options
    include_routing_tables: bool = Field(default=True, description="Include routing tables in snapshot")
    include_flow_tables: bool = Field(default=True, description="Include OpenFlow flow tables")
    include_arp_tables: bool = Field(default=True, description="Include ARP tables")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        # Allow alphanumeric, underscores, hyphens, and spaces
        import re
        if not re.match(r'^[\w\-\s]+$', v):
            raise ValueError('Name can only contain letters, numbers, underscores, hyphens, and spaces')
        return v.strip()


class SnapshotRestoreRequest(BaseModel):
    """Request schema for restoring from a snapshot"""
    target_topology_id: Optional[str] = Field(
        None,
        description="Target topology ID. If not provided, restores to original topology"
    )
    target_containers: Optional[List[str]] = Field(
        None,
        description="List of containers to restore. Null means all"
    )
    restore_network_state: bool = Field(default=True, description="Restore network state (routes, ARP, flows)")
    restore_docker_images: bool = Field(default=True, description="Restore from Docker committed images")
    restore_criu_checkpoints: bool = Field(default=True, description="Restore from CRIU checkpoints")
    skip_validation: bool = Field(default=False, description="Skip pre-restore validation")
    stop_existing_emulation: bool = Field(default=True, description="Stop existing emulation before restore")


class SnapshotRenameRequest(BaseModel):
    """Request schema for renaming a snapshot"""
    name: str = Field(..., min_length=1, max_length=255, description="New snapshot name")


class ScheduleCreateRequest(BaseModel):
    """Request schema for creating a snapshot schedule"""
    name: str = Field(..., min_length=1, max_length=255, description="Schedule name")
    topology_id: Optional[str] = Field(None, description="Target topology ID. Null means global")
    target_containers: Optional[List[str]] = Field(
        None,
        description="Target containers. Null means all containers"
    )
    cron_expression: str = Field(
        ...,
        description="Cron expression for scheduling (e.g., '0 */6 * * *' for every 6 hours)"
    )
    snapshot_type: SnapshotTypeEnum = Field(
        default=SnapshotTypeEnum.TOPOLOGY_ONLY,
        description="Type of snapshots to create"
    )

    # Retention policy
    retention_count: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Number of most recent snapshots to keep"
    )
    retention_days: Optional[int] = Field(
        default=None,
        ge=1,
        le=365,
        description="Delete snapshots older than N days. Null means no age-based deletion"
    )

    # Options
    compression: bool = Field(default=True, description="Compress scheduled snapshots")
    include_routing_tables: bool = Field(default=True)
    include_flow_tables: bool = Field(default=True)
    include_arp_tables: bool = Field(default=True)
    description: Optional[str] = Field(None, max_length=1000)

    @field_validator('cron_expression')
    @classmethod
    def validate_cron(cls, v):
        # Basic cron validation (5 fields: minute hour day month weekday)
        parts = v.strip().split()
        if len(parts) != 5:
            raise ValueError('Cron expression must have 5 fields: minute hour day month weekday')
        return v.strip()


class ScheduleUpdateRequest(BaseModel):
    """Request schema for updating a snapshot schedule"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    cron_expression: Optional[str] = None
    snapshot_type: Optional[SnapshotTypeEnum] = None
    is_active: Optional[bool] = None
    retention_count: Optional[int] = Field(None, ge=1, le=1000)
    retention_days: Optional[int] = Field(None, ge=1, le=365)
    target_containers: Optional[List[str]] = None
    compression: Optional[bool] = None
    include_routing_tables: Optional[bool] = None
    include_flow_tables: Optional[bool] = None
    include_arp_tables: Optional[bool] = None
    description: Optional[str] = Field(None, max_length=1000)


# ==================== Response Schemas ====================

class SnapshotResponse(BaseModel):
    """Response schema for snapshot basic info"""
    id: str
    name: str
    topology_id: str
    emulation_id: Optional[str] = None
    snapshot_type: SnapshotTypeEnum
    status: SnapshotStatusEnum
    description: Optional[str] = None

    # Size info
    size_bytes: int = 0
    size_mb: float = 0.0
    compressed: bool = True

    # Counts
    device_count: int = 0
    container_count: int = 0

    # Flags
    criu_available: bool = False

    # Timestamps
    created_at: datetime
    captured_at: Optional[datetime] = None

    # Error info
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class SnapshotDetailResponse(SnapshotResponse):
    """Detailed snapshot response with additional metadata"""
    mongo_state_id: Optional[str] = None
    checkpoint_path: Optional[str] = None
    target_containers: Optional[List[str]] = None
    capture_duration_seconds: Optional[float] = None
    restored_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    extra_metadata: Dict[str, Any] = Field(default_factory=dict)
    restore_history: List[Dict[str, Any]] = Field(default_factory=list)


class SnapshotProgressResponse(BaseModel):
    """Real-time progress response for snapshot operations"""
    snapshot_id: str
    status: SnapshotStatusEnum
    progress_percent: int = Field(ge=0, le=100)
    current_step: str
    steps_completed: int
    total_steps: int
    current_device: Optional[str] = None
    elapsed_seconds: float = 0.0
    error_message: Optional[str] = None


class RestoreResultResponse(BaseModel):
    """Response schema for restore operation result"""
    snapshot_id: str
    success: bool
    status: str
    devices_restored: int = 0
    containers_restored: int = 0
    network_state_restored: bool = False
    duration_seconds: float = 0.0
    warnings: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None
    rollback_performed: bool = False


class ScheduleResponse(BaseModel):
    """Response schema for snapshot schedule"""
    id: str
    name: str
    topology_id: Optional[str] = None
    target_containers: Optional[List[str]] = None
    cron_expression: str
    snapshot_type: SnapshotTypeEnum
    is_active: bool

    # Retention
    retention_count: int
    retention_days: Optional[int] = None

    # Options
    compression: bool = True
    include_routing_tables: bool = True
    include_flow_tables: bool = True
    include_arp_tables: bool = True

    # Tracking
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    last_snapshot_id: Optional[str] = None
    run_count: int = 0
    failure_count: int = 0

    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True


class SnapshotListResponse(BaseModel):
    """Response schema for paginated snapshot list"""
    items: List[SnapshotResponse]
    total: int
    page: int = 1
    per_page: int = 20
    has_next: bool = False
    has_prev: bool = False


class ScheduleListResponse(BaseModel):
    """Response schema for schedule list"""
    items: List[ScheduleResponse]
    total: int


class SnapshotStatsResponse(BaseModel):
    """Response schema for snapshot statistics"""
    total_snapshots: int = 0
    total_size_bytes: int = 0
    total_size_mb: float = 0.0
    by_type: Dict[str, int] = Field(default_factory=dict)
    by_status: Dict[str, int] = Field(default_factory=dict)
    criu_enabled_count: int = 0
    oldest_snapshot: Optional[datetime] = None
    newest_snapshot: Optional[datetime] = None
    active_schedules: int = 0


class SnapshotTypeInfo(BaseModel):
    """Information about a snapshot type"""
    type: SnapshotTypeEnum
    name: str
    description: str
    estimated_size: str
    estimated_duration: str
    requires_criu: bool
    requires_running_emulation: bool


class SnapshotTypesResponse(BaseModel):
    """Response schema for available snapshot types"""
    types: List[SnapshotTypeInfo]
    criu_available: bool
    docker_experimental: bool


# ==================== Cron Presets ====================

class CronPreset(BaseModel):
    """Cron expression preset"""
    label: str
    cron: str
    description: str


CRON_PRESETS = [
    CronPreset(label="Every hour", cron="0 * * * *", description="At minute 0 of every hour"),
    CronPreset(label="Every 6 hours", cron="0 */6 * * *", description="At minute 0 every 6 hours"),
    CronPreset(label="Every 12 hours", cron="0 */12 * * *", description="At minute 0 every 12 hours"),
    CronPreset(label="Daily at midnight", cron="0 0 * * *", description="Every day at 00:00"),
    CronPreset(label="Daily at 6 AM", cron="0 6 * * *", description="Every day at 06:00"),
    CronPreset(label="Weekly on Sunday", cron="0 0 * * 0", description="Every Sunday at 00:00"),
    CronPreset(label="Weekly on Monday", cron="0 0 * * 1", description="Every Monday at 00:00"),
    CronPreset(label="Monthly", cron="0 0 1 * *", description="First day of every month at 00:00"),
]


# Export all schemas
__all__ = [
    # Enums
    'SnapshotTypeEnum',
    'SnapshotStatusEnum',

    # Request schemas
    'SnapshotCreateRequest',
    'SnapshotRestoreRequest',
    'SnapshotRenameRequest',
    'ScheduleCreateRequest',
    'ScheduleUpdateRequest',

    # Response schemas
    'SnapshotResponse',
    'SnapshotDetailResponse',
    'SnapshotProgressResponse',
    'RestoreResultResponse',
    'ScheduleResponse',
    'SnapshotListResponse',
    'ScheduleListResponse',
    'SnapshotStatsResponse',
    'SnapshotTypeInfo',
    'SnapshotTypesResponse',

    # Presets
    'CronPreset',
    'CRON_PRESETS',
]
