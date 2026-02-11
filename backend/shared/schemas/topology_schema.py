"""
Pydantic schemas for topology API requests/responses
"""

from pydantic import BaseModel, Field, field_serializer, model_validator
from typing import Optional, Dict, List, Any
from datetime import datetime
from enum import Enum


class DeviceTypeEnum(str, Enum):
    HOST = "host"
    SWITCH = "switch"
    ROUTER = "router"
    ACCESS_POINT = "ap"
    STATION = "station"
    CONTAINER = "container"
    P4_SWITCH = "p4switch"
    CONTROLLER = "controller"


class LinkStatusEnum(str, Enum):
    UP = "up"
    DOWN = "down"


class EmulationStatusEnum(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"


# Node Schemas
class NodeBase(BaseModel):
    name: str
    device_type: DeviceTypeEnum
    x: float = 0
    y: float = 0
    properties: Dict[str, Any] = Field(default_factory=dict)


class NodeCreate(NodeBase):
    pass


class NodeUpdate(BaseModel):
    name: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    properties: Optional[Dict[str, Any]] = None


class NodeResponse(NodeBase):
    id: str
    topology_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Link Schemas
class LinkBase(BaseModel):
    source_node_id: str
    target_node_id: str
    source_port: Optional[str] = None
    target_port: Optional[str] = None
    bandwidth: Optional[float] = None  # Mbps
    delay: Optional[float] = None  # ms
    loss: Optional[float] = None  # percentage
    max_queue_size: Optional[int] = None
    properties: Dict[str, Any] = Field(default_factory=dict)


class LinkCreate(LinkBase):
    pass


class LinkUpdate(BaseModel):
    bandwidth: Optional[float] = None
    delay: Optional[float] = None
    loss: Optional[float] = None
    max_queue_size: Optional[int] = None
    status: Optional[LinkStatusEnum] = None
    properties: Optional[Dict[str, Any]] = None


class LinkResponse(LinkBase):
    id: str
    topology_id: str
    status: LinkStatusEnum
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Controller Schemas
class ControllerBase(BaseModel):
    name: str
    controller_type: str
    ip: str
    port: int
    properties: Dict[str, Any] = Field(default_factory=dict)


class ControllerCreate(ControllerBase):
    pass


class ControllerResponse(ControllerBase):
    id: str
    topology_id: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Topology Schemas
class TopologyBase(BaseModel):
    name: str
    description: Optional[str] = None


class TopologyCreate(TopologyBase):
    project_id: str
    nodes: List[NodeCreate] = Field(default_factory=list)
    links: List[LinkCreate] = Field(default_factory=list)
    controllers: List[ControllerCreate] = Field(default_factory=list)


class TopologyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class TopologyResponse(TopologyBase):
    id: str
    project_id: str
    version: int
    is_active: bool
    emulation_status: EmulationStatusEnum
    emulation_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    nodes: List[NodeResponse] = Field(default_factory=list)
    links: List[LinkResponse] = Field(default_factory=list)
    controllers: List[ControllerResponse] = Field(default_factory=list)
    container_id: Optional[str] = None
    container_name: Optional[str] = None

    class Config:
        from_attributes = True
        populate_by_name = True


# Complete Topology Definition (for import/export)
class TopologyDefinition(BaseModel):
    """Complete topology definition for JSON import/export"""
    name: str
    description: Optional[str] = None
    version: str = "1.0"
    metadata: Dict[str, Any] = Field(default_factory=dict)

    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    links: List[Dict[str, Any]] = Field(default_factory=list)
    controllers: List[Dict[str, Any]] = Field(default_factory=list)

    # Protocol configurations
    protocols: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    # Network-wide options
    options: Dict[str, Any] = Field(default_factory=dict)


class NodeIdentifier(BaseModel):
    """Reference to a node by ID or name."""
    id: Optional[str] = None
    name: Optional[str] = None


class NodeDelta(NodeBase):
    """Node payload for staged addition."""
    id: Optional[str] = None


class NodeUpdateDelta(BaseModel):
    """Node payload for staged update."""
    id: str
    name: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    properties: Optional[Dict[str, Any]] = None


class LinkIdentifier(BaseModel):
    """Reference to a link by ID and endpoints."""
    id: Optional[str] = None
    source_node_id: Optional[str] = None
    target_node_id: Optional[str] = None


class LinkDelta(LinkBase):
    """Link payload for staged addition."""
    id: Optional[str] = None


class LinkUpdateDelta(LinkUpdate):
    """Link payload for staged update."""
    id: str
    source_node_id: Optional[str] = None
    target_node_id: Optional[str] = None


class TopologyChangeSet(BaseModel):
    """Group of staged topology changes."""
    add_devices: List[NodeDelta] = Field(default_factory=list)
    update_devices: List[NodeUpdateDelta] = Field(default_factory=list)
    remove_devices: List[NodeIdentifier] = Field(default_factory=list)
    add_links: List[LinkDelta] = Field(default_factory=list)
    update_links: List[LinkUpdateDelta] = Field(default_factory=list)
    remove_links: List[LinkIdentifier] = Field(default_factory=list)

    def is_empty(self) -> bool:
        """Return True when no staged operations are present."""
        return not any((
            self.add_devices,
            self.update_devices,
            self.remove_devices,
            self.add_links,
            self.update_links,
            self.remove_links,
        ))


class TopologyApplyRequest(BaseModel):
    """Request payload for staged topology apply operations."""
    changes: TopologyChangeSet = Field(default_factory=TopologyChangeSet)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    options: Dict[str, Any] = Field(default_factory=dict)
    commit: bool = True


# Project Schemas
class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectCreate(ProjectBase):
    owner: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class ProjectResponse(ProjectBase):
    id: str
    owner: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Snapshot Schemas
class SnapshotCreate(BaseModel):
    name: str
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SnapshotResponse(BaseModel):
    id: str
    topology_id: str
    name: str
    description: Optional[str]
    state_id: str
    size_bytes: int
    created_at: datetime
    metadata: Dict[str, Any]

    class Config:
        from_attributes = True


# Apply Changes Request/Response Schemas
class ApplyChangesRequest(BaseModel):
    """Request payload for button-triggered apply changes"""
    topology_id: str
    changes: Dict[str, Any] = Field(default_factory=dict)  # Contains add_devices, update_devices, etc.


class ApplyChangesResponse(BaseModel):
    """Response from apply changes operation"""
    success: bool
    message: str
    applied_count: int
    rolled_back_count: Optional[int] = None
    results: Dict[str, Any] = Field(default_factory=dict)
    failed_operations: Optional[List[tuple]] = None


class BatchUpdateRequest(BaseModel):
    """Request payload for batch update to topology service"""
    add_devices: List[Dict[str, Any]] = Field(default_factory=list)
    update_devices: List[Dict[str, Any]] = Field(default_factory=list)
    remove_devices: List[Dict[str, Any]] = Field(default_factory=list)
    add_links: List[Dict[str, Any]] = Field(default_factory=list)
    update_links: List[Dict[str, Any]] = Field(default_factory=list)
    remove_links: List[Dict[str, Any]] = Field(default_factory=list)


# Protocol Schemas
class ProtocolConfig(BaseModel):
    protocol_name: str
    protocol_version: Optional[str] = None
    is_enabled: bool = True
    configuration: Dict[str, Any] = Field(default_factory=dict)


class ProtocolSwitchRequest(BaseModel):
    device: str
    from_protocol: str
    to_protocol: str
    preserve_config: bool = True


class ProtocolStatusResponse(BaseModel):
    protocol: str
    status: str
    version: Optional[str]
    details: Dict[str, Any] = Field(default_factory=dict)


# Emulation Control Schemas
class EmulationStartRequest(BaseModel):
    topology_id: str
    options: Dict[str, Any] = Field(default_factory=dict)


class EmulationControlResponse(BaseModel):
    success: bool
    message: str
    emulation_id: Optional[str] = None


class EmulationStatusResponse(BaseModel):
    status: EmulationStatusEnum
    uptime_seconds: int
    device_count: int
    link_count: int
    metadata: Dict[str, Any]


# Device Command Schemas
class CommandExecuteRequest(BaseModel):
    device: str
    command: str
    topology_id: Optional[str] = None
    emulation_id: Optional[str] = None


class CommandExecuteResponse(BaseModel):
    success: bool
    stdout: str
    stderr: str
    exit_code: int


# Metrics Schemas
class MetricsRequest(BaseModel):
    devices: List[str] = Field(default_factory=list)
    metrics: List[str] = Field(default_factory=list)
    interval_seconds: int = 5


class DeviceMetrics(BaseModel):
    bytes_sent: int
    bytes_received: int
    packets_sent: int
    packets_received: int
    errors_in: int
    errors_out: int
    drops_in: int
    drops_out: int
    cpu_percent: float
    memory_percent: float


class MetricsResponse(BaseModel):
    timestamp: datetime
    device_metrics: Dict[str, DeviceMetrics]

# Alias for backward compatibility
TopologyExport = TopologyDefinition
