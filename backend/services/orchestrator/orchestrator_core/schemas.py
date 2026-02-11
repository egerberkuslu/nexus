from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EmulationStopRequest(BaseModel):
    """Request payload for stopping an emulation."""

    cleanup: bool = True
    stop_infra: bool = True
    preserve_infra_data: bool = True


class OrchestratorStartOptions(BaseModel):
    """UI-friendly wrapper: start by topology_id with optional options dict."""

    options: Dict[str, Any] = Field(default_factory=dict)


class TopologyInfraStopRequest(BaseModel):
    preserve_data: bool = True


class TopologyInfraPurgeRequest(BaseModel):
    confirm: bool = False


class TopologyInfraRestartRequest(BaseModel):
    service: Optional[str] = None
    controller_id: Optional[str] = None


class TopologyOsmStopRequest(BaseModel):
    preserve_data: bool = True


class TopologyOsmPurgeRequest(BaseModel):
    confirm: bool = False
    remove_volumes: bool = True


class TopologyControllerExecRequest(BaseModel):
    command: str
    timeout_seconds: int = 15


class TopologyControllerLifecycleRequest(BaseModel):
    timeout_seconds: int = 10


class ApplyChangesResponse(BaseModel):
    """Response payload for staged apply operations."""

    success: bool
    message: str
    applied: Dict[str, int] = Field(default_factory=dict)
    rollback_performed: bool = False


class NetworkConfigApplyRequestBody(BaseModel):
    topology_id: Optional[str] = None
    emulation_id: Optional[str] = None
    config: Dict[str, Any]
    dry_run: bool = False


class NetworkConfigApplyResponseBody(BaseModel):
    success: bool
    message: str
    topology_id: Optional[str] = None
    dry_run: bool = False
    results: List[Dict[str, Any]] = Field(default_factory=list)


class InfrastructureEnsureRequest(BaseModel):
    services: Optional[List[str]] = None


class TestRunStateEnum(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    canceled = "canceled"


class TestStepStateEnum(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class TestRunRequest(BaseModel):
    topology_id: str
    suite: str = Field(
        description="One of: full, metrics_snapshot, ping, iperf_tcp, iperf_udp, cpu_stress, cpu_stress_stop, memory_stress, memory_stress_stop, sdn_smoke, mano_local_smoke"
    )
    params: Dict[str, Any] = Field(default_factory=dict)


class TestRunStopRequest(BaseModel):
    cancel: bool = True


class TestRunStep(BaseModel):
    step_id: str
    name: str
    status: TestStepStateEnum = TestStepStateEnum.queued
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    message: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)


class TestRunStatusResponse(BaseModel):
    run_id: str
    topology_id: str
    suite: str
    status: TestRunStateEnum
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    message: str = ""
    steps: List[TestRunStep] = Field(default_factory=list)
    logs: List[str] = Field(default_factory=list)


class InfluxDiagnosticsFeaturesResponse(BaseModel):
    topology_id: str
    bucket: str
    measurement: str
    fields: List[str]
    devices: List[str]
    sources: List[str]
    emulation_ids: List[str]


class InfluxDiagnosticsQueryRequest(BaseModel):
    # Either provide window_minutes (relative) or start_ms/end_ms (absolute).
    window_minutes: Optional[int] = 60
    start_ms: Optional[int] = None
    end_ms: Optional[int] = None

    every_seconds: int = 5
    device: Optional[str] = None
    source: Optional[str] = None
    emulation_id: Optional[str] = None
    fields: List[str] = Field(default_factory=list)


class InfluxDiagnosticsQueryResponse(BaseModel):
    topology_id: str
    bucket: str
    measurement: str
    every_seconds: int
    start_ms: Optional[int]
    end_ms: Optional[int]
    device: Optional[str]
    source: Optional[str]
    emulation_id: Optional[str]
    fields: List[str]
    points: List[Dict[str, Any]]


class AlgorithmRunStartResponse(BaseModel):
    run_id: str
    topology_id: str
    status: str
    message: str = ""
    nodes_started: int = 0
    nodes_skipped: int = 0
    selected_algo_ids: List[int] = Field(default_factory=list)


class AlgorithmRunStatusResponse(BaseModel):
    run_id: str
    topology_id: str
    status: str
    created_at: float
    stopped_at: Optional[float] = None
    manifest: Dict[str, Any] = Field(default_factory=dict)
    transport: str = "udp"
    listen_port: int = 50000
    node_id_to_algo_id: Dict[str, int] = Field(default_factory=dict)
    algo_id_to_node_id: Dict[int, str] = Field(default_factory=dict)
    started_nodes: List[int] = Field(default_factory=list)
    skipped_nodes: List[int] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    mininet_baseline: Optional[Dict[str, int]] = None
    mininet_final: Optional[Dict[str, int]] = None
    mininet_delta: Optional[Dict[str, int]] = None
    persisted_to_influx: bool = False
    persisting_to_influx: bool = False
    persisted_at: Optional[float] = None
    persist_error: Optional[str] = None


class AlgorithmOverlayResponse(BaseModel):
    topology_id: str
    run_id: Optional[str] = None
    overlays: Dict[str, Any] = Field(default_factory=dict)  # topology_node_id -> overlay payload


class EmulationRuntimeAddDeviceRequest(BaseModel):
    topology_id: str
    name: str
    device_type: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    node_id: Optional[str] = None


class EmulationRuntimeAddLinkRequest(BaseModel):
    topology_id: str
    node1: str
    node2: str
    port1: str = ""
    port2: str = ""
    bandwidth: int = 0
    delay: int = 0
    loss: float = 0.0
    max_queue_size: int = 1000


class PcapStartRequest(BaseModel):
    topology_id: str
    emulation_id: Optional[str] = None
    device: str
    interface: Optional[str] = None
    bpf: Optional[str] = Field(default=None, description="tcpdump filter expression (quoted as a single arg)")
    duration_seconds: Optional[int] = None
    snaplen: int = 96


class PcapStopRequest(BaseModel):
    topology_id: str
    capture_id: str

