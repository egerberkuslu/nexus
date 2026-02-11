"""
Monitoring Service (Port 8011)
Collects and exports metrics to Prometheus and InfluxDB
"""

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import logging
import threading
from datetime import datetime
from prometheus_client import Counter, Gauge, Histogram, generate_latest, REGISTRY
from influxdb_client import InfluxDBClient, Point
from influxdb_client.rest import ApiException as InfluxApiException
from influxdb_client.client.write_api import SYNCHRONOUS
import grpc

# Import shared components
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from shared.messaging.rabbitmq import RabbitMQPublisher, RabbitMQConsumer
from shared.utils.consul_client import ConsulClient

# gRPC stubs (generated in container build)
try:
    import emulation_pb2  # type: ignore
    import emulation_pb2_grpc  # type: ignore
except Exception:
    emulation_pb2 = None  # type: ignore
    emulation_pb2_grpc = None  # type: ignore

# Import Kafka consumer handler (if Kafka is enabled)
try:
    from kafka_consumer_handler import MetricsKafkaConsumer
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False
    # logger isn't configured yet at import time; keep stderr noise minimal.

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Caduceus-Flux Monitoring Service",
    description="Metrics collection and export to Prometheus/InfluxDB",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service clients
consul_client = ConsulClient()
rabbitmq_publisher = RabbitMQPublisher()
rabbitmq_consumer = None
influxdb_client = None
influxdb_write_api = None
kafka_bucket_manager = None
kafka_consumer_handler = None
_kafka_consumer_retry_thread: Optional[threading.Thread] = None
_kafka_consumer_retry_stop = threading.Event()

# Optional: per-topology isolated InfluxDB instances (one InfluxDB per topology).
_topology_influx_clients: Dict[str, InfluxDBClient] = {}
_topology_influx_write_apis: Dict[str, Any] = {}

SERVICE_PORT = 8011

# Configuration
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "caduceus-token")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "caduceus")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "network_metrics")
INFLUXDB_TOPOLOGY_BUCKETS_ENABLED = os.getenv("INFLUXDB_TOPOLOGY_BUCKETS_ENABLED", "true").lower() == "true"
INFLUXDB_TOPOLOGY_BUCKET_PREFIX = os.getenv("INFLUXDB_TOPOLOGY_BUCKET_PREFIX", "topology_")
INFLUXDB_TOPOLOGY_INSTANCES_ENABLED = os.getenv("INFLUXDB_TOPOLOGY_INSTANCES_ENABLED", "false").lower() == "true"
INFLUXDB_TOPOLOGY_URL_TEMPLATE = os.getenv(
    "INFLUXDB_TOPOLOGY_URL_TEMPLATE",
    "http://caduceus-topo-{short_id}-influxdb:8086",
)
GRPC_HOST = os.getenv("EMULATION_CONTAINER_HOST", "emulation-container")
GRPC_PORT = int(os.getenv("EMULATION_CONTAINER_PORT", "50051"))
KAFKA_ENABLED = os.getenv("KAFKA_ENABLED", "false").lower() == "true"

# Prometheus metrics
device_rx_bytes = Gauge('device_rx_bytes', 'Total RX bytes', ['device', 'interface'])
device_tx_bytes = Gauge('device_tx_bytes', 'Total TX bytes', ['device', 'interface'])
device_rx_packets = Gauge('device_rx_packets', 'Total RX packets', ['device', 'interface'])
device_tx_packets = Gauge('device_tx_packets', 'Total TX packets', ['device', 'interface'])
device_cpu_percent = Gauge('device_cpu_percent', 'CPU usage percentage', ['device'])
device_memory_mb = Gauge('device_memory_mb', 'Memory usage in MB', ['device'])
protocol_neighbor_count = Gauge('protocol_neighbor_count', 'Number of protocol neighbors', ['device', 'protocol'])
flow_table_entries = Gauge('flow_table_entries', 'Number of flow table entries', ['switch'])
link_bandwidth_usage = Gauge('link_bandwidth_usage', 'Link bandwidth usage', ['source', 'target'])

# Metrics collection counter
metrics_collected = Counter('metrics_collected_total', 'Total metrics collected', ['device'])

# Best-effort rate cache for UI (in-memory)
_topology_rate_cache: Dict[str, Dict[str, Any]] = {}
_topology_latency_cache: Dict[str, Dict[str, Any]] = {}

def _raise_emulation_unavailable(topology_id: str) -> None:
    raise HTTPException(
        status_code=409,
        detail=f"Emulation not running for topology {topology_id}; start it first",
    )


def _raise_grpc_as_http(topology_id: str, exc: Exception, fallback_detail: str) -> None:
    if isinstance(exc, grpc.RpcError):
        try:
            code = exc.code()
        except Exception:
            code = None
        if code in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED):
            _raise_emulation_unavailable(topology_id)
        try:
            detail = exc.details()
        except Exception:
            detail = str(exc)
        raise HTTPException(status_code=502, detail=f"{fallback_detail}: {detail}")
    raise HTTPException(status_code=502, detail=fallback_detail)


# Pydantic models
class MetricsQuery(BaseModel):
    device: Optional[str] = None
    metric_type: Optional[str] = None  # interface, cpu, memory, protocol, flow
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class DeviceMetrics(BaseModel):
    device: str
    timestamp: datetime
    interfaces: Dict[str, Dict[str, int]]
    cpu: Dict[str, float]
    memory: Dict[str, int]
    protocols: Dict[str, Any]


# Helper functions
def get_influxdb_client():
    """Get InfluxDB client"""
    global influxdb_client, influxdb_write_api
    if influxdb_client is None:
        influxdb_client = InfluxDBClient(
            url=INFLUXDB_URL,
            token=INFLUXDB_TOKEN,
            org=INFLUXDB_ORG
        )
        influxdb_write_api = influxdb_client.write_api(write_options=SYNCHRONOUS)
    return influxdb_client, influxdb_write_api


def _topology_influx_secrets(topology_id: str) -> Optional[Dict[str, str]]:
    """
    Read per-topology isolated InfluxDB credentials from Consul.
    These keys are created by the orchestrator when topology infrastructure runs in isolated mode.
    """
    tid = (topology_id or "").strip()
    if not tid:
        return None
    try:
        token = str(consul_client.get_config(f"caduceus/topologies/{tid}/isolated_influx_token") or "").strip()
        org = str(consul_client.get_config(f"caduceus/topologies/{tid}/isolated_influx_org") or "").strip()
        bucket = str(consul_client.get_config(f"caduceus/topologies/{tid}/isolated_influx_bucket") or "").strip()
        if not (token and org and bucket):
            return None
        return {"token": token, "org": org, "bucket": bucket}
    except Exception:
        return None


def _topology_influx_url(topology_id: str) -> str:
    tid = (topology_id or "").strip()
    short_id = tid[:8] if tid else ""
    return str(INFLUXDB_TOPOLOGY_URL_TEMPLATE).format(topology_id=tid, short_id=short_id)


def get_influxdb_target(topology_id: Optional[str] = None) -> tuple[InfluxDBClient, Any, str, str, str]:
    """
    Return (client, write_api, org, bucket, mode) where mode is 'isolated' or 'global'.

    If INFLUXDB_TOPOLOGY_INSTANCES_ENABLED is true and the topology has isolated InfluxDB secrets
    in Consul, reads/writes are routed to the topology's own InfluxDB container.
    """
    topo = str(topology_id or "").strip()
    if INFLUXDB_TOPOLOGY_INSTANCES_ENABLED and topo:
        secrets = _topology_influx_secrets(topo)
        if secrets:
            if topo not in _topology_influx_clients:
                url = _topology_influx_url(topo)
                c = InfluxDBClient(url=url, token=secrets["token"], org=secrets["org"])
                _topology_influx_clients[topo] = c
                _topology_influx_write_apis[topo] = c.write_api(write_options=SYNCHRONOUS)
            return (
                _topology_influx_clients[topo],
                _topology_influx_write_apis[topo],
                secrets["org"],
                secrets["bucket"],
                "isolated",
            )

    client, write_api = get_influxdb_client()
    bucket = kafka_bucket_manager.bucket_for_topology(topo) if kafka_bucket_manager else INFLUXDB_BUCKET
    return (client, write_api, INFLUXDB_ORG, bucket, "global")


class TopologyInfluxBucketManager:
    def __init__(
        self,
        client: InfluxDBClient,
        consul: ConsulClient,
        org: str,
        default_bucket: str,
        enabled: bool,
        prefix: str,
    ):
        self.client = client
        self.consul = consul
        self.org = org
        self.default_bucket = default_bucket
        self.enabled = enabled
        self.prefix = prefix
        self._cache: Dict[str, str] = {}
        self._org_id: Optional[str] = None

    def _safe_bucket_name(self, topology_id: str) -> str:
        name = f"{self.prefix}{topology_id}".strip()
        out = []
        for ch in name:
            out.append(ch if ch.isalnum() or ch in ("-", "_") else "_")
        safe = "".join(out)
        return safe[:120] if len(safe) > 120 else safe

    def _resolve_org_id(self) -> Optional[str]:
        if self._org_id:
            return self._org_id
        try:
            orgs = self.client.organizations_api().find_organizations(org=self.org) or []
            if orgs:
                self._org_id = getattr(orgs[0], "id", None)
        except Exception:
            self._org_id = None
        return self._org_id

    def bucket_for_topology(self, topology_id: Optional[str]) -> str:
        if not self.enabled or not topology_id:
            return self.default_bucket
        if topology_id in self._cache:
            return self._cache[topology_id]

        name = self._safe_bucket_name(str(topology_id))
        try:
            buckets_api = self.client.buckets_api()
            existing = buckets_api.find_bucket_by_name(name)
            if not existing:
                org_id = self._resolve_org_id()
                if not org_id:
                    raise RuntimeError(f"InfluxDB org id not found for org={self.org}")
                buckets_api.create_bucket(bucket_name=name, org_id=org_id)
                logger.info("Created InfluxDB bucket %s for topology %s", name, topology_id)

            self._cache[topology_id] = name
            try:
                self.consul.set_config(f"caduceus/topologies/{topology_id}/influxdb_bucket", name)
            except Exception:
                pass
            return name
        except Exception as exc:
            logger.warning("Failed to ensure InfluxDB bucket for topology %s: %s", topology_id, exc)
            return self.default_bucket


def _parse_metric_timestamp(ts: Any) -> datetime:
    if isinstance(ts, datetime):
        return ts
    if isinstance(ts, (int, float)):
        try:
            return datetime.fromtimestamp(float(ts) / 1000.0)
        except Exception:
            return datetime.utcnow()
    if isinstance(ts, str) and ts.strip():
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            return datetime.utcnow()
    return datetime.utcnow()


def _write_metric_envelope(bucket: str, envelope: Dict[str, Any]) -> None:
    """
    Writes a single metric envelope into InfluxDB.
    Envelope shape:
      { topology_id, emulation_id, device, source, timestamp, metrics: {..fields..} }
    """
    _client, write_api = get_influxdb_client()
    metrics = envelope.get("metrics") if isinstance(envelope.get("metrics"), dict) else {}
    features = envelope.get("features") if isinstance(envelope.get("features"), dict) else {}
    device = envelope.get("device") or metrics.get("device")
    if not device:
        return

    topology_id = envelope.get("topology_id") or metrics.get("topology_id")
    emulation_id = envelope.get("emulation_id") or metrics.get("emulation_id")
    source = envelope.get("source") or metrics.get("source") or "ingest"
    ts = _parse_metric_timestamp(envelope.get("timestamp") or metrics.get("timestamp"))

    point = Point("network_metrics").tag("device", str(device)).tag("source", str(source)).time(ts)
    if topology_id:
        point.tag("topology_id", str(topology_id))
    if emulation_id:
        point.tag("emulation_id", str(emulation_id))

    for field in (
        "bytes_sent",
        "bytes_received",
        "packets_sent",
        "packets_received",
        "errors_in",
        "errors_out",
        "drops_in",
        "drops_out",
    ):
        if field in metrics:
            try:
                point.field(field, int(metrics[field]))
            except Exception:
                pass

    for field in ("cpu_percent", "memory_percent"):
        if field in metrics:
            try:
                point.field(field, float(metrics[field]))
            except Exception:
                pass

    # Best-effort: store processed stream features (when present).
    for k, v in (features or {}).items():
        if not k:
            continue
        try:
            if isinstance(v, bool):
                point.field(str(k), int(v))
            elif isinstance(v, int):
                point.field(str(k), int(v))
            elif isinstance(v, float):
                point.field(str(k), float(v))
            else:
                continue
        except Exception:
            pass

    write_api.write(bucket=bucket, record=point)


class MetricsIngestRequest(BaseModel):
    topology_id: Optional[str] = None
    emulation_id: Optional[str] = None
    device: Optional[str] = None
    source: Optional[str] = None
    timestamp: Optional[Any] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    features: Dict[str, Any] = Field(default_factory=dict)


@app.post("/api/monitoring/ingest/metrics")
async def ingest_metrics(payload: List[MetricsIngestRequest]):
    """
    Ingest topology-scoped metrics envelopes (e.g. from metrics-collector).
    This is used to persist per-topology metrics even when Kafka is disabled.
    """
    if not payload:
        return {"success": True, "ingested": 0}

    ok = 0
    failed = 0
    for item in payload:
        try:
            topo = item.topology_id or (item.metrics.get("topology_id") if isinstance(item.metrics, dict) else None)
            bucket = kafka_bucket_manager.bucket_for_topology(topo) if kafka_bucket_manager else INFLUXDB_BUCKET
            _write_metric_envelope(
                bucket,
                {
                    "topology_id": item.topology_id,
                    "emulation_id": item.emulation_id,
                    "device": item.device,
                    "source": item.source,
                    "timestamp": item.timestamp,
                    "metrics": item.metrics,
                    "features": item.features,
                },
            )
            ok += 1
        except Exception:
            failed += 1
    return {"success": failed == 0, "ingested": ok, "failed": failed}


class AlgorithmResultIngestRequest(BaseModel):
    topology_id: str
    run_id: str
    algorithm: str = "algorithm"
    version: Optional[str] = None
    emulation_id: Optional[str] = None
    timestamp: Optional[Any] = None  # ms epoch, RFC3339, or datetime
    node: Dict[str, Any] = Field(default_factory=dict)  # {algo_id, uuid, name, type, ...}
    result: Dict[str, Any] = Field(default_factory=dict)  # {color, sent_msgs, recv_msgs, ...}


@app.post("/api/monitoring/algorithms/ingest")
async def ingest_algorithm_results(payload: List[AlgorithmResultIngestRequest]):
    """
    Persist algorithm run results into InfluxDB so the UI can filter/history them.

    Measurement: `algorithm_node_result`
    Tags: topology_id, run_id, algorithm, version, emulation_id, algo_id, node_uuid, node_name, node_type
    Fields: color, sent_msgs, sent_bytes, broadcast_msgs, broadcast_bytes, recv_msgs, recv_bytes
    """
    if not payload:
        return {"success": True, "ingested": 0}

    ok = 0
    failed = 0
    for item in payload:
        try:
            topo = str(item.topology_id or "").strip()
            if not topo:
                failed += 1
                continue
            _client, write_api, org, bucket, _mode = get_influxdb_target(topo)
            ts = _parse_metric_timestamp(item.timestamp)

            node = item.node if isinstance(item.node, dict) else {}
            res = item.result if isinstance(item.result, dict) else {}

            algo_id = node.get("algo_id", res.get("algo_id"))
            node_uuid = node.get("uuid") or node.get("id") or node.get("node_id") or ""
            node_name = node.get("name") or ""
            node_type = node.get("type") or ""

            point = (
                Point("algorithm_node_result")
                .tag("topology_id", topo)
                .tag("run_id", str(item.run_id))
                .tag("algorithm", str(item.algorithm or "algorithm"))
                .time(ts)
            )
            if item.version:
                point.tag("version", str(item.version))
            if item.emulation_id:
                point.tag("emulation_id", str(item.emulation_id))
            if algo_id is not None:
                point.tag("algo_id", str(algo_id))
            if node_uuid:
                point.tag("node_uuid", str(node_uuid))
            if node_name:
                point.tag("node_name", str(node_name))
            if node_type:
                point.tag("node_type", str(node_type))

            if "color" in res:
                try:
                    point.field("color", str(res.get("color") or ""))
                except Exception:
                    pass

            for f in ("sent_msgs", "sent_bytes", "broadcast_msgs", "broadcast_bytes", "recv_msgs", "recv_bytes"):
                if f in res:
                    try:
                        point.field(f, int(res.get(f) or 0))
                    except Exception:
                        pass

            write_api.write(bucket=bucket, record=point)
            ok += 1
        except Exception:
            failed += 1

    return {"success": failed == 0, "ingested": ok, "failed": failed}


class AlgorithmRunSummaryIngestRequest(BaseModel):
    topology_id: str
    run_id: str
    algorithm: str = "algorithm"
    version: Optional[str] = None
    emulation_id: Optional[str] = None
    timestamp: Optional[Any] = None  # ms epoch, RFC3339, or datetime
    created_at: Optional[float] = None
    stopped_at: Optional[float] = None
    duration_s: Optional[float] = None
    mininet_baseline: Optional[Dict[str, Any]] = None
    mininet_final: Optional[Dict[str, Any]] = None
    mininet_delta: Optional[Dict[str, Any]] = None
    algo_totals: Optional[Dict[str, Any]] = None
    validation_ok: Optional[bool] = None
    validation: Optional[Dict[str, Any]] = None
    # Optional WSN (Wireless Sensor Network) summary fields for protocol comparison.
    wsn_total_nodes: Optional[int] = None
    wsn_total_rounds: Optional[int] = None
    wsn_fnd_round: Optional[int] = None
    wsn_hnd_round: Optional[int] = None
    wsn_lnd_round: Optional[int] = None
    wsn_packets_to_bs: Optional[int] = None
    wsn_packets_to_bs_per_round: Optional[float] = None
    wsn_initial_total_energy_j: Optional[float] = None
    wsn_final_total_energy_j: Optional[float] = None
    wsn_energy_spent_j: Optional[float] = None
    wsn_energy_spent_per_round_j: Optional[float] = None
    wsn_cluster_count_avg: Optional[float] = None
    wsn_cluster_count_min: Optional[int] = None
    wsn_cluster_count_max: Optional[int] = None
    wsn_cluster_count_last: Optional[int] = None
    wsn_cluster_size_avg: Optional[float] = None
    wsn_cluster_size_min: Optional[int] = None
    wsn_cluster_size_max: Optional[int] = None
    wsn_summary: Optional[Dict[str, Any]] = None


@app.post("/api/monitoring/algorithms/ingest-summary")
async def ingest_algorithm_run_summary(payload: AlgorithmRunSummaryIngestRequest):
    """
    Persist algorithm run summary into InfluxDB.

    Measurement: `algorithm_run_summary`
    Tags: topology_id, run_id, algorithm, version, emulation_id
    Fields:
      - created_at, stopped_at, duration_s
      - mininet_* totals and deltas (best effort)
      - algo_* totals (msgs/bytes)
      - validation_ok, validation_json
    """
    topo = str(payload.topology_id or "").strip()
    if not topo:
        raise HTTPException(status_code=400, detail="topology_id is required")
    rid = str(payload.run_id or "").strip()
    if not rid:
        raise HTTPException(status_code=400, detail="run_id is required")

    _client, write_api, influx_org, bucket, _mode = get_influxdb_target(topo)
    ts = _parse_metric_timestamp(payload.timestamp)

    point = (
        Point("algorithm_run_summary")
        .tag("topology_id", topo)
        .tag("run_id", rid)
        .tag("algorithm", str(payload.algorithm or "algorithm"))
        .time(ts)
    )
    if payload.version:
        point.tag("version", str(payload.version))
    if payload.emulation_id:
        point.tag("emulation_id", str(payload.emulation_id))

    try:
        if payload.created_at is not None:
            point.field("created_at", float(payload.created_at))
        if payload.stopped_at is not None:
            point.field("stopped_at", float(payload.stopped_at))
        if payload.duration_s is not None:
            point.field("duration_s", float(payload.duration_s))
    except Exception:
        pass

    def _field_int(name: str, value: Any) -> None:
        try:
            point.field(name, int(value or 0))
        except Exception:
            pass

    mb = payload.mininet_baseline if isinstance(payload.mininet_baseline, dict) else {}
    mf = payload.mininet_final if isinstance(payload.mininet_final, dict) else {}
    md = payload.mininet_delta if isinstance(payload.mininet_delta, dict) else {}

    for src, prefix in ((mb, "mininet_baseline"), (mf, "mininet_final")):
        _field_int(f"{prefix}_rx_packets", src.get("total_rx_packets"))
        _field_int(f"{prefix}_tx_packets", src.get("total_tx_packets"))
        _field_int(f"{prefix}_rx_bytes", src.get("total_rx_bytes"))
        _field_int(f"{prefix}_tx_bytes", src.get("total_tx_bytes"))

    _field_int("mininet_delta_rx_packets", md.get("rx_packets"))
    _field_int("mininet_delta_tx_packets", md.get("tx_packets"))
    _field_int("mininet_delta_rx_bytes", md.get("rx_bytes"))
    _field_int("mininet_delta_tx_bytes", md.get("tx_bytes"))
    _field_int("mininet_delta_total_packets", md.get("total_packets"))
    _field_int("mininet_delta_total_bytes", md.get("total_bytes"))

    at = payload.algo_totals if isinstance(payload.algo_totals, dict) else {}
    _field_int("algo_sent_msgs", at.get("sent_msgs"))
    _field_int("algo_sent_bytes", at.get("sent_bytes"))
    _field_int("algo_broadcast_msgs", at.get("broadcast_msgs"))
    _field_int("algo_broadcast_bytes", at.get("broadcast_bytes"))
    _field_int("algo_recv_msgs", at.get("recv_msgs"))
    _field_int("algo_recv_bytes", at.get("recv_bytes"))

    if payload.validation_ok is not None:
        try:
            point.field("validation_ok", 1 if bool(payload.validation_ok) else 0)
        except Exception:
            pass
    if payload.validation is not None:
        try:
            point.field("validation_json", json.dumps(payload.validation, ensure_ascii=False, separators=(",", ":")))
        except Exception:
            pass

    # --- WSN summary fields (optional) ---
    try:
        if payload.wsn_total_nodes is not None:
            point.field("wsn_total_nodes", int(payload.wsn_total_nodes))
        if payload.wsn_total_rounds is not None:
            point.field("wsn_total_rounds", int(payload.wsn_total_rounds))
        if payload.wsn_fnd_round is not None:
            point.field("wsn_fnd_round", int(payload.wsn_fnd_round))
        if payload.wsn_hnd_round is not None:
            point.field("wsn_hnd_round", int(payload.wsn_hnd_round))
        if payload.wsn_lnd_round is not None:
            point.field("wsn_lnd_round", int(payload.wsn_lnd_round))
        if payload.wsn_packets_to_bs is not None:
            point.field("wsn_packets_to_bs", int(payload.wsn_packets_to_bs))
        if payload.wsn_packets_to_bs_per_round is not None:
            point.field("wsn_packets_to_bs_per_round", float(payload.wsn_packets_to_bs_per_round))
        if payload.wsn_initial_total_energy_j is not None:
            point.field("wsn_initial_total_energy_j", float(payload.wsn_initial_total_energy_j))
        if payload.wsn_final_total_energy_j is not None:
            point.field("wsn_final_total_energy_j", float(payload.wsn_final_total_energy_j))
        if payload.wsn_energy_spent_j is not None:
            point.field("wsn_energy_spent_j", float(payload.wsn_energy_spent_j))
        if payload.wsn_energy_spent_per_round_j is not None:
            point.field("wsn_energy_spent_per_round_j", float(payload.wsn_energy_spent_per_round_j))
        if payload.wsn_cluster_count_avg is not None:
            point.field("wsn_cluster_count_avg", float(payload.wsn_cluster_count_avg))
        if payload.wsn_cluster_count_min is not None:
            point.field("wsn_cluster_count_min", int(payload.wsn_cluster_count_min))
        if payload.wsn_cluster_count_max is not None:
            point.field("wsn_cluster_count_max", int(payload.wsn_cluster_count_max))
        if payload.wsn_cluster_count_last is not None:
            point.field("wsn_cluster_count_last", int(payload.wsn_cluster_count_last))
        if payload.wsn_cluster_size_avg is not None:
            point.field("wsn_cluster_size_avg", float(payload.wsn_cluster_size_avg))
        if payload.wsn_cluster_size_min is not None:
            point.field("wsn_cluster_size_min", int(payload.wsn_cluster_size_min))
        if payload.wsn_cluster_size_max is not None:
            point.field("wsn_cluster_size_max", int(payload.wsn_cluster_size_max))
        if payload.wsn_summary is not None:
            point.field("wsn_summary_json", json.dumps(payload.wsn_summary, ensure_ascii=False, separators=(",", ":")))
    except Exception:
        pass

    write_api.write(bucket=bucket, record=point)
    return {"success": True, "bucket": bucket, "mode": _mode}


@app.get("/api/monitoring/algorithms/topology/{topology_id}/runs")
async def list_algorithm_runs(topology_id: str, window_minutes: int = 24 * 60, algorithm: Optional[str] = None):
    """
    List algorithm runs persisted to InfluxDB for a topology (from `algorithm_node_result`).
    """
    topology_id = (topology_id or "").strip()
    if not topology_id:
        raise HTTPException(status_code=400, detail="topology_id is required")

    window_minutes = int(max(5, min(14 * 24 * 60, window_minutes)))
    start_range = f"-{window_minutes}m"

    client, _write_api, influx_org, bucket, _mode = get_influxdb_target(topology_id)
    alg_filter = (algorithm or "").strip()
    alg_filter_clause = f' and r.algorithm == "{alg_filter}"' if alg_filter else ""

    flux = (
        f'from(bucket: "{bucket}")'
        f" |> range(start: {start_range})"
        f' |> filter(fn: (r) => r._measurement == "algorithm_node_result" and r.topology_id == "{topology_id}"{alg_filter_clause})'
        f' |> filter(fn: (r) => r._field == "color")'
        f' |> group(columns: ["run_id","algorithm","version","emulation_id"])'
        f" |> last()"
        f' |> keep(columns: ["_time","run_id","algorithm","version","emulation_id"])'
        f' |> sort(columns: ["_time"], desc: true)'
        f" |> limit(n: 200)"
    )

    query_api = client.query_api()
    try:
        tables = query_api.query(flux, org=influx_org)
    except InfluxApiException as exc:
        status_code = int(getattr(exc, "status", 0) or 0)
        msg = str(getattr(exc, "reason", "") or "") or "InfluxDB query failed"
        if status_code == 401:
            raise HTTPException(
                status_code=502,
                detail=f"InfluxDB unauthorized for topology '{topology_id}' (mode={_mode}, bucket={bucket}). "
                f"Check isolated Influx token in Consul. ({msg})",
            ) from exc
        raise HTTPException(
            status_code=502,
            detail=f"InfluxDB query failed for topology '{topology_id}' (mode={_mode}, bucket={bucket}). ({msg})",
        ) from exc

    runs: List[Dict[str, Any]] = []
    for table in tables or []:
        for record in table.records:
            values = record.values or {}
            runs.append(
                {
                    "run_id": values.get("run_id") or "",
                    "algorithm": values.get("algorithm") or "",
                    "version": values.get("version") or "",
                    "emulation_id": values.get("emulation_id") or "",
                    "time": (values.get("_time").isoformat() if values.get("_time") else ""),
                }
            )

    # Deduplicate by run_id (safety).
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for r in runs:
        rid = str(r.get("run_id") or "")
        if not rid or rid in seen:
            continue
        seen.add(rid)
        out.append(r)
    try:
        def _ts(item: Dict[str, Any]) -> float:
            t = str(item.get("time") or "").strip()
            if not t:
                return 0.0
            try:
                return datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp()
            except Exception:
                return 0.0

        out.sort(key=_ts, reverse=True)
    except Exception:
        pass
    return {"topology_id": topology_id, "bucket": bucket, "mode": _mode, "runs": out}


@app.get("/api/monitoring/algorithms/topology/{topology_id}/runs/{run_id}/nodes")
async def get_algorithm_run_nodes(topology_id: str, run_id: str, window_minutes: int = 14 * 24 * 60):
    """
    Return per-node persisted results for a run (latest values per node/field).
    """
    topology_id = (topology_id or "").strip()
    run_id = (run_id or "").strip()
    if not topology_id:
        raise HTTPException(status_code=400, detail="topology_id is required")
    if not run_id:
        raise HTTPException(status_code=400, detail="run_id is required")

    window_minutes = int(max(5, min(30 * 24 * 60, window_minutes)))
    start_range = f"-{window_minutes}m"
    client, _write_api, influx_org, bucket, _mode = get_influxdb_target(topology_id)

    flux = (
        f'from(bucket: "{bucket}")'
        f" |> range(start: {start_range})"
        f' |> filter(fn: (r) => r._measurement == "algorithm_node_result" and r.topology_id == "{topology_id}" and r.run_id == "{run_id}")'
        f" |> last()"
    )

    query_api = client.query_api()
    try:
        tables = query_api.query(flux, org=influx_org)
    except InfluxApiException as exc:
        status_code = int(getattr(exc, "status", 0) or 0)
        msg = str(getattr(exc, "reason", "") or "") or "InfluxDB query failed"
        if status_code == 401:
            raise HTTPException(
                status_code=502,
                detail=f"InfluxDB unauthorized for topology '{topology_id}' run '{run_id}' (mode={_mode}, bucket={bucket}). "
                f"Check isolated Influx token in Consul. ({msg})",
            ) from exc
        raise HTTPException(
            status_code=502,
            detail=f"InfluxDB query failed for topology '{topology_id}' run '{run_id}' (mode={_mode}, bucket={bucket}). ({msg})",
        ) from exc

    by_node: Dict[str, Dict[str, Any]] = {}
    for table in tables or []:
        for record in table.records:
            v = record.values or {}
            algo_id = str(v.get("algo_id") or "")
            node_uuid = str(v.get("node_uuid") or "")
            key = f"{algo_id}:{node_uuid}"
            row = by_node.setdefault(
                key,
                {
                    "algo_id": algo_id,
                    "node_uuid": node_uuid,
                    "node_name": v.get("node_name") or "",
                    "node_type": v.get("node_type") or "",
                    "algorithm": v.get("algorithm") or "",
                    "version": v.get("version") or "",
                    "emulation_id": v.get("emulation_id") or "",
                    "time": (v.get("_time").isoformat() if v.get("_time") else ""),
                    "fields": {},
                },
            )
            field = v.get("_field")
            if field:
                row["fields"][str(field)] = v.get("_value")

    nodes = list(by_node.values())
    nodes.sort(key=lambda r: int(r.get("algo_id") or 0))
    return {"topology_id": topology_id, "run_id": run_id, "bucket": bucket, "mode": _mode, "nodes": nodes}


@app.get("/api/monitoring/algorithms/topology/{topology_id}/runs/{run_id}/summary")
async def get_algorithm_run_summary(topology_id: str, run_id: str, window_minutes: int = 30 * 24 * 60):
    """
    Return latest persisted summary for a run (from `algorithm_run_summary`).
    """
    topology_id = (topology_id or "").strip()
    run_id = (run_id or "").strip()
    if not topology_id:
        raise HTTPException(status_code=400, detail="topology_id is required")
    if not run_id:
        raise HTTPException(status_code=400, detail="run_id is required")

    window_minutes = int(max(5, min(90 * 24 * 60, window_minutes)))
    start_range = f"-{window_minutes}m"
    client, _write_api, influx_org, bucket, _mode = get_influxdb_target(topology_id)

    flux = (
        f'from(bucket: "{bucket}")'
        f" |> range(start: {start_range})"
        f' |> filter(fn: (r) => r._measurement == "algorithm_run_summary" and r.topology_id == "{topology_id}" and r.run_id == "{run_id}")'
        f" |> last()"
    )

    query_api = client.query_api()
    try:
        tables = query_api.query(flux, org=influx_org)
    except InfluxApiException as exc:
        status_code = int(getattr(exc, "status", 0) or 0)
        msg = str(getattr(exc, "reason", "") or "") or "InfluxDB query failed"
        if status_code == 401:
            raise HTTPException(
                status_code=502,
                detail=f"InfluxDB unauthorized for topology '{topology_id}' run '{run_id}' (mode={_mode}, bucket={bucket}). "
                f"Check isolated Influx token in Consul. ({msg})",
            ) from exc
        raise HTTPException(
            status_code=502,
            detail=f"InfluxDB query failed for topology '{topology_id}' run '{run_id}' (mode={_mode}, bucket={bucket}). ({msg})",
        ) from exc

    tags: Dict[str, Any] = {}
    fields: Dict[str, Any] = {}
    last_time = ""

    for table in tables or []:
        for record in table.records:
            v = record.values or {}
            tags = {
                "topology_id": v.get("topology_id") or topology_id,
                "run_id": v.get("run_id") or run_id,
                "algorithm": v.get("algorithm") or "",
                "version": v.get("version") or "",
                "emulation_id": v.get("emulation_id") or "",
            }
            if v.get("_time"):
                last_time = v.get("_time").isoformat()
            field = v.get("_field")
            if field:
                fields[str(field)] = v.get("_value")

    return {"topology_id": topology_id, "run_id": run_id, "bucket": bucket, "mode": _mode, "time": last_time, "tags": tags, "fields": fields}


@app.post("/api/monitoring/topologies/{topology_id}/influxdb/ensure")
async def ensure_topology_influx_bucket(topology_id: str):
    """Ensure a topology-scoped InfluxDB bucket exists and return its name."""
    if not kafka_bucket_manager:
        return {"success": False, "bucket": INFLUXDB_BUCKET}
    bucket = kafka_bucket_manager.bucket_for_topology(topology_id)
    return {"success": True, "bucket": bucket}


def publish_event(event_type: str, data: Dict):
    """Publish monitoring event"""
    try:
        rabbitmq_publisher.publish(
            exchange="caduceus",
            routing_key=f"monitoring.{event_type}",
            message=data
        )
    except Exception as e:
        logger.error(f"Failed to publish event: {e}")


def write_to_influxdb(device: str, metrics: Dict):
    """Write metrics to InfluxDB"""
    try:
        client, write_api = get_influxdb_client()
        
        # Write interface metrics
        for iface_name, iface_stats in metrics.get("interfaces", {}).items():
            point = Point("interface_metrics") \
                .tag("device", device) \
                .tag("interface", iface_name) \
                .field("rx_bytes", iface_stats.get("rx_bytes", 0)) \
                .field("tx_bytes", iface_stats.get("tx_bytes", 0)) \
                .field("rx_packets", iface_stats.get("rx_packets", 0)) \
                .field("tx_packets", iface_stats.get("tx_packets", 0)) \
                .field("rx_errors", iface_stats.get("rx_errors", 0)) \
                .field("tx_errors", iface_stats.get("tx_errors", 0))
            
            write_api.write(bucket=INFLUXDB_BUCKET, record=point)
        
        # Write system metrics
        cpu = metrics.get("cpu", {})
        if cpu:
            point = Point("system_metrics") \
                .tag("device", device) \
                .field("cpu_percent", cpu.get("total_cpu_percent", 0)) \
                .field("process_count", cpu.get("process_count", 0))
            write_api.write(bucket=INFLUXDB_BUCKET, record=point)
        
        memory = metrics.get("memory", {})
        if memory:
            point = Point("system_metrics") \
                .tag("device", device) \
                .field("memory_total_mb", memory.get("total_mb", 0)) \
                .field("memory_used_mb", memory.get("used_mb", 0)) \
                .field("memory_free_mb", memory.get("free_mb", 0))
            write_api.write(bucket=INFLUXDB_BUCKET, record=point)
        
        # Write protocol metrics
        for protocol, proto_metrics in metrics.get("protocols", {}).items():
            if isinstance(proto_metrics, dict):
                point = Point("protocol_metrics") \
                    .tag("device", device) \
                    .tag("protocol", protocol) \
                    .field("neighbor_count", proto_metrics.get("neighbor_count", 0))
                write_api.write(bucket=INFLUXDB_BUCKET, record=point)
        
        logger.debug(f"Wrote metrics to InfluxDB for device: {device}")
    
    except Exception as e:
        logger.error(f"Failed to write to InfluxDB: {e}")


def update_prometheus_metrics(device: str, metrics: Dict):
    """Update Prometheus metrics"""
    try:
        # Update interface metrics
        for iface_name, iface_stats in metrics.get("interfaces", {}).items():
            device_rx_bytes.labels(device=device, interface=iface_name).set(iface_stats.get("rx_bytes", 0))
            device_tx_bytes.labels(device=device, interface=iface_name).set(iface_stats.get("tx_bytes", 0))
            device_rx_packets.labels(device=device, interface=iface_name).set(iface_stats.get("rx_packets", 0))
            device_tx_packets.labels(device=device, interface=iface_name).set(iface_stats.get("tx_packets", 0))
        
        # Update CPU metrics
        cpu = metrics.get("cpu", {})
        if cpu:
            device_cpu_percent.labels(device=device).set(cpu.get("total_cpu_percent", 0))
        
        # Update memory metrics
        memory = metrics.get("memory", {})
        if memory:
            device_memory_mb.labels(device=device).set(memory.get("used_mb", 0))
        
        # Update protocol metrics
        for protocol, proto_metrics in metrics.get("protocols", {}).items():
            if isinstance(proto_metrics, dict):
                protocol_neighbor_count.labels(device=device, protocol=protocol).set(
                    proto_metrics.get("neighbor_count", 0)
                )
        
        # Increment collection counter
        metrics_collected.labels(device=device).inc()
        
        logger.debug(f"Updated Prometheus metrics for device: {device}")
    
    except Exception as e:
        logger.error(f"Failed to update Prometheus metrics: {e}")


def collect_device_metrics(device: str) -> Dict:
    """Collect metrics from device via monitoring handler"""
    try:
        import subprocess
        
        metrics = {
            "device": device,
            "timestamp": datetime.utcnow().isoformat(),
            "interfaces": {},
            "cpu": {},
            "memory": {},
            "protocols": {}
        }
        
        # Collect interface metrics
        result = subprocess.run(
            ["ip", "netns", "exec", device, "ip", "-s", "link", "show"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            current_iface = None
            for line in result.stdout.splitlines():
                if line and line[0].isdigit():
                    parts = line.split(':')
                    if len(parts) >= 2:
                        current_iface = parts[1].strip()
                        metrics["interfaces"][current_iface] = {
                            "rx_bytes": 0, "tx_bytes": 0,
                            "rx_packets": 0, "tx_packets": 0,
                            "rx_errors": 0, "tx_errors": 0
                        }
                elif current_iface and "RX:" in line:
                    continue
                elif current_iface and line.strip() and line.strip()[0].isdigit():
                    parts = line.strip().split()
                    if "RX" in result.stdout.splitlines()[result.stdout.splitlines().index(line) - 1]:
                        if len(parts) >= 4:
                            metrics["interfaces"][current_iface]["rx_bytes"] = int(parts[0])
                            metrics["interfaces"][current_iface]["rx_packets"] = int(parts[1])
                            metrics["interfaces"][current_iface]["rx_errors"] = int(parts[2])
        
        # Collect CPU metrics
        result = subprocess.run(
            ["ip", "netns", "exec", device, "ps", "aux"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            total_cpu = 0.0
            process_count = 0
            for line in result.stdout.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        cpu_percent = float(parts[2])
                        total_cpu += cpu_percent
                        process_count += 1
                    except ValueError:
                        continue
            
            metrics["cpu"] = {
                "total_cpu_percent": total_cpu,
                "process_count": process_count,
                "avg_cpu_percent": total_cpu / process_count if process_count > 0 else 0
            }
        
        # Collect memory metrics
        result = subprocess.run(
            ["ip", "netns", "exec", device, "free", "-m"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            lines = result.stdout.splitlines()
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 3:
                    metrics["memory"] = {
                        "total_mb": int(parts[1]) if parts[1].isdigit() else 0,
                        "used_mb": int(parts[2]) if parts[2].isdigit() else 0,
                        "free_mb": int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
                    }
        
        return metrics
    
    except Exception as e:
        logger.error(f"Failed to collect metrics for {device}: {e}")
        return {}


def _summarize_stats_from_interfaces(interfaces: Dict[str, Dict[str, int]]) -> Dict[str, int]:
    total_rx_bytes = 0
    total_tx_bytes = 0
    total_rx_packets = 0
    total_tx_packets = 0
    total_rx_errors = 0
    total_tx_errors = 0
    for iface_stats in (interfaces or {}).values():
        if not isinstance(iface_stats, dict):
            continue
        total_rx_bytes += int(iface_stats.get("rx_bytes", 0) or 0)
        total_tx_bytes += int(iface_stats.get("tx_bytes", 0) or 0)
        total_rx_packets += int(iface_stats.get("rx_packets", 0) or 0)
        total_tx_packets += int(iface_stats.get("tx_packets", 0) or 0)
        total_rx_errors += int(iface_stats.get("rx_errors", 0) or 0)
        total_tx_errors += int(iface_stats.get("tx_errors", 0) or 0)
    return {
        "rx_bytes": total_rx_bytes,
        "tx_bytes": total_tx_bytes,
        "rx_packets": total_rx_packets,
        "tx_packets": total_tx_packets,
        "rx_errors": total_rx_errors,
        "tx_errors": total_tx_errors,
    }


def handle_device_event(ch, method, properties, body):
    """Handle device-related events from RabbitMQ"""
    try:
        import json
        event = json.loads(body)
        event_type = method.routing_key.split('.')[-1]
        
        logger.info(f"Received device event: {event_type}")
        
        # Start monitoring new devices
        if event_type == "added":
            device = event.get("name")
            if device:
                logger.info(f"Starting monitoring for new device: {device}")
                # In real implementation, start monitoring thread
    
    except Exception as e:
        logger.error(f"Error handling device event: {e}")


# API endpoints

@app.on_event("startup")
async def startup_event():
    """Service startup"""
    logger.info("Starting Monitoring Service...")
    try:
        global rabbitmq_consumer, kafka_consumer_handler, kafka_bucket_manager, _kafka_consumer_retry_thread
        _kafka_consumer_retry_stop.clear()

        # Initialize InfluxDB client
        client, write_api = get_influxdb_client()
        logger.info("InfluxDB connection established")
        kafka_bucket_manager = TopologyInfluxBucketManager(
            client=client,
            consul=consul_client,
            org=INFLUXDB_ORG,
            default_bucket=INFLUXDB_BUCKET,
            enabled=INFLUXDB_TOPOLOGY_BUCKETS_ENABLED,
            prefix=INFLUXDB_TOPOLOGY_BUCKET_PREFIX,
        )

        def _is_kafka_consumer_running() -> bool:
            try:
                return bool(
                    kafka_consumer_handler
                    and getattr(kafka_consumer_handler, "consumer", None) is not None
                    and getattr(kafka_consumer_handler.consumer, "running", False)
                )
            except Exception:
                return False

        def _kafka_consumer_retry_loop():
            backoff = 1.0
            while not _kafka_consumer_retry_stop.is_set():
                if _is_kafka_consumer_running():
                    backoff = 1.0
                    _kafka_consumer_retry_stop.wait(10.0)
                    continue
                try:
                    if kafka_consumer_handler:
                        kafka_consumer_handler.start()
                    backoff = 1.0
                    _kafka_consumer_retry_stop.wait(5.0)
                except Exception as exc:
                    logger.warning("Kafka consumer not ready (%s); retrying in %.1fs", exc, backoff)
                    _kafka_consumer_retry_stop.wait(backoff)
                    backoff = min(backoff * 2.0, 30.0)

        # Start Kafka consumer if enabled
        if KAFKA_ENABLED and KAFKA_AVAILABLE:
            try:
                # Create Prometheus metrics dict for Kafka consumer
                prometheus_gauges = {
                    "device_rx_bytes": device_rx_bytes,
                    "device_tx_bytes": device_tx_bytes,
                    "device_rx_packets": device_rx_packets,
                    "device_tx_packets": device_tx_packets,
                    "device_cpu_percent": device_cpu_percent,
                    "device_memory_mb": device_memory_mb
                }

                kafka_consumer_handler = MetricsKafkaConsumer(
                    influxdb_write_api=write_api,
                    bucket_manager=kafka_bucket_manager,
                    prometheus_metrics=prometheus_gauges
                )
                kafka_consumer_handler.start()
                logger.info("✅ Kafka metrics consumer started")

                # Keep a lightweight watchdog thread running so if Kafka is temporarily unavailable
                # at startup or later, the consumer will reconnect and resume.
                if not _kafka_consumer_retry_thread or not _kafka_consumer_retry_thread.is_alive():
                    _kafka_consumer_retry_thread = threading.Thread(target=_kafka_consumer_retry_loop, daemon=True)
                    _kafka_consumer_retry_thread.start()
            except Exception as e:
                logger.error(f"Failed to start Kafka consumer: {e}")
                logger.info("Will retry Kafka consumer startup in background")
                if not _kafka_consumer_retry_thread or not _kafka_consumer_retry_thread.is_alive():
                    _kafka_consumer_retry_thread = threading.Thread(target=_kafka_consumer_retry_loop, daemon=True)
                    _kafka_consumer_retry_thread.start()
        elif KAFKA_ENABLED:
            logger.warning("Kafka is enabled but kafka-python is not installed")
        else:
            logger.info("Kafka consumer disabled")

        # Register with Consul
        consul_client.register_service("monitoring", SERVICE_PORT)
        rabbitmq_publisher.connect()

        # Subscribe to device events (best-effort; does not block startup).
        try:
            def _handle_device_event_message(event_type: str, event: Dict[str, Any]):
                logger.info(f"Received device event: {event_type}")
                if event_type == "added":
                    device = event.get("name")
                    if device:
                        logger.info(f"Starting monitoring for new device: {device}")

            rabbitmq_consumer = RabbitMQConsumer("monitoring_device_events_queue")
            rabbitmq_consumer.connect()

            for rk, et in (("device.added", "added"), ("device.updated", "updated"), ("device.deleted", "deleted")):
                rabbitmq_consumer.bind_routing_key(rk, exchange="caduceus")
                rabbitmq_consumer.register_callback(rk, lambda msg, _et=et: _handle_device_event_message(_et, msg))

            threading.Thread(target=rabbitmq_consumer.start_consuming, daemon=True).start()
        except Exception as e:
            logger.warning(f"Failed to start RabbitMQ device event consumer: {e}")
            rabbitmq_consumer = None

        logger.info("Monitoring Service started successfully")
    except Exception as e:
        logger.error(f"Startup error: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Service shutdown"""
    logger.info("Shutting down Monitoring Service...")

    # Stop Kafka consumer
    if kafka_consumer_handler:
        kafka_consumer_handler.stop()
    try:
        _kafka_consumer_retry_stop.set()
    except Exception:
        pass

    if rabbitmq_consumer:
        rabbitmq_consumer.disconnect()

    # Close topology-scoped InfluxDB clients
    try:
        for _tid, c in list(_topology_influx_clients.items()):
            try:
                c.close()
            except Exception:
                pass
        _topology_influx_clients.clear()
        _topology_influx_write_apis.clear()
    except Exception:
        pass

    if influxdb_client:
        influxdb_client.close()

    consul_client.deregister_service("monitoring")
    rabbitmq_publisher.disconnect()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    health_status = {
        "status": "healthy",
        "service": "monitoring",
        "influxdb_connected": influxdb_client is not None,
        "kafka_enabled": KAFKA_ENABLED,
        "kafka_consumer_active": kafka_consumer_handler is not None,
        "timestamp": datetime.utcnow().isoformat()
    }

    # Add Kafka consumer stats if available
    if kafka_consumer_handler:
        health_status["kafka_stats"] = kafka_consumer_handler.get_stats()

    return health_status


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(REGISTRY), media_type="text/plain")


@app.post("/api/collect/{device}")
async def collect_metrics(device: str):
    """Manually trigger metrics collection for a device"""
    try:
        logger.info(f"Collecting metrics for device: {device}")
        
        # Collect metrics
        metrics = collect_device_metrics(device)
        
        if not metrics:
            raise HTTPException(status_code=500, detail="Failed to collect metrics")
        
        # Write to InfluxDB
        write_to_influxdb(device, metrics)
        
        # Update Prometheus metrics
        update_prometheus_metrics(device, metrics)
        
        return {
            "success": True,
            "device": device,
            "metrics": metrics,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error collecting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/collect-all")
async def collect_all_metrics(devices: List[str]):
    """Collect metrics for multiple devices"""
    results = []
    
    for device in devices:
        try:
            metrics = collect_device_metrics(device)
            write_to_influxdb(device, metrics)
            update_prometheus_metrics(device, metrics)
            
            results.append({
                "device": device,
                "success": True,
                "metrics": metrics
            })
        except Exception as e:
            logger.error(f"Error collecting metrics for {device}: {e}")
            results.append({
                "device": device,
                "success": False,
                "error": str(e)
            })
    
    return {
        "collected": len([r for r in results if r["success"]]),
        "failed": len([r for r in results if not r["success"]]),
        "results": results
    }


@app.get("/api/query")
async def query_metrics(
    device: Optional[str] = None,
    metric_type: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = 100
):
    """Query metrics from InfluxDB"""
    try:
        client, _ = get_influxdb_client()
        query_api = client.query_api()
        
        # Build Flux query
        flux_query = f'from(bucket: "{INFLUXDB_BUCKET}")'
        
        if start:
            flux_query += f' |> range(start: {start})'
        else:
            flux_query += ' |> range(start: -1h)'
        
        if end:
            flux_query += f' |> range(stop: {end})'
        
        if device:
            flux_query += f' |> filter(fn: (r) => r.device == "{device}")'
        
        if metric_type:
            flux_query += f' |> filter(fn: (r) => r._measurement == "{metric_type}_metrics")'
        
        flux_query += f' |> limit(n: {limit})'
        
        # Execute query
        result = query_api.query(flux_query, org=INFLUXDB_ORG)
        
        # Format results
        data = []
        for table in result:
            for record in table.records:
                data.append({
                    "time": record.get_time().isoformat(),
                    "device": record.values.get("device"),
                    "measurement": record.get_measurement(),
                    "field": record.get_field(),
                    "value": record.get_value()
                })
        
        return {
            "query": flux_query,
            "data": data,
            "count": len(data)
        }
    
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/devices/{device}/metrics/latest")
async def get_latest_metrics(device: str):
    """Get latest metrics for a device"""
    try:
        # Collect fresh metrics
        metrics = collect_device_metrics(device)
        
        return {
            "device": device,
            "metrics": metrics,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error getting latest metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/monitoring/devices/{device}")
async def get_device_metrics_for_ui(device: str, topology_id: Optional[str] = None):
    """
    UI-friendly device metrics endpoint (alias).
    Matches the frontend `DeviceMetrics` shape.
    """
    now = datetime.utcnow()

    def _host_mem_total_mb() -> float:
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        parts = line.split()
                        if len(parts) >= 2:
                            kb = float(parts[1])
                            return kb / 1024.0
        except Exception:
            pass
        return 0.0

    # Prefer gRPC metrics from the emulation container (requires topology_id).
    if topology_id and emulation_pb2 and emulation_pb2_grpc:
        host = f"caduceus-emu-{topology_id[:8]}"
        try:
            channel = grpc.insecure_channel(
                f"{host}:50051",
                options=[
                    ("grpc.max_send_message_length", 50 * 1024 * 1024),
                    ("grpc.max_receive_message_length", 50 * 1024 * 1024),
                ],
            )
            stub = emulation_pb2_grpc.EmulationServiceStub(channel)
            resp = stub.GetMetrics(emulation_pb2.GetMetricsRequest(devices=[device], metrics=[]), timeout=10)
            dm = resp.device_metrics.get(device)
            if not dm:
                raise HTTPException(status_code=404, detail="No metrics available")
            interfaces = {
                "total": {
                    "rx_bytes": int(dm.bytes_received),
                    "tx_bytes": int(dm.bytes_sent),
                    "rx_packets": int(dm.packets_received),
                    "tx_packets": int(dm.packets_sent),
                    "rx_errors": int(dm.errors_in),
                    "tx_errors": int(dm.errors_out),
                }
            }
            stats = _summarize_stats_from_interfaces(interfaces)
            mem_pct = float(dm.memory_percent or 0.0)
            total_mb = _host_mem_total_mb()
            used_mb = (total_mb * mem_pct / 100.0) if total_mb > 0 else 0.0
            free_mb = max(0.0, total_mb - used_mb) if total_mb > 0 else 0.0
            memory = {
                "total_mb": total_mb,
                "used_mb": used_mb,
                "free_mb": free_mb,
                "memory_percent": mem_pct,
            }
            return {
                "device": device,
                "timestamp": now.isoformat(),
                "interfaces": interfaces,
                "stats": {k: stats[k] for k in ("rx_bytes", "tx_bytes", "rx_packets", "tx_packets")},
                "cpu": {"total_cpu_percent": float(dm.cpu_percent or 0.0), "process_count": 0},
                "memory": memory,
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch gRPC metrics for {device} on {host}: {e}")
            _raise_grpc_as_http(str(topology_id), e, "Failed to fetch metrics from emulation container")

    # Fallback: local netns exec (works only if running inside emulation container).
    metrics = collect_device_metrics(device)
    if not metrics:
        raise HTTPException(status_code=404, detail="No metrics available")
    interfaces = metrics.get("interfaces") if isinstance(metrics.get("interfaces"), dict) else {}
    stats = _summarize_stats_from_interfaces(interfaces)
    return {
        "device": device,
        "timestamp": now.isoformat(),
        "interfaces": interfaces,
        "stats": {k: stats[k] for k in ("rx_bytes", "tx_bytes", "rx_packets", "tx_packets")},
        "cpu": metrics.get("cpu") or {"total_cpu_percent": 0, "process_count": 0},
        "memory": metrics.get("memory") or {"total_mb": 0, "used_mb": 0, "free_mb": 0},
    }


@app.get("/api/monitoring/devices/{device}/interfaces")
async def get_device_interface_stats_for_ui(device: str, topology_id: str, interface: Optional[str] = None):
    """
    UI-friendly interface stats endpoint (per-interface counters).
    Requires topology_id to reach the correct emulation container.
    """
    if not (emulation_pb2 and emulation_pb2_grpc):
        raise HTTPException(status_code=503, detail="gRPC stubs not available in monitoring service")

    host = f"caduceus-emu-{topology_id[:8]}"
    try:
        channel = grpc.insecure_channel(
            f"{host}:50051",
            options=[
                ("grpc.max_send_message_length", 50 * 1024 * 1024),
                ("grpc.max_receive_message_length", 50 * 1024 * 1024),
            ],
        )
        stub = emulation_pb2_grpc.EmulationServiceStub(channel)
        resp = stub.GetInterfaceStats(
            emulation_pb2.GetInterfaceStatsRequest(device=device, interface=interface or ""),
            timeout=10,
        )
        interfaces = {}
        for st in resp.stats:
            interfaces[st.interface] = {
                "rx_bytes": int(st.rx_bytes),
                "tx_bytes": int(st.tx_bytes),
                "rx_packets": int(st.rx_packets),
                "tx_packets": int(st.tx_packets),
                "rx_errors": int(st.rx_errors),
                "tx_errors": int(st.tx_errors),
                "rx_dropped": int(st.rx_dropped),
                "tx_dropped": int(st.tx_dropped),
            }
        return {
            "device": device,
            "timestamp": datetime.utcnow().isoformat(),
            "interfaces": interfaces,
        }
    except Exception as e:
        logger.error(f"Failed to fetch interface stats for {device} on {host}: {e}")
        _raise_grpc_as_http(topology_id, e, "Failed to fetch interface stats from emulation container")


@app.get("/api/monitoring/devices/{device}/routes")
async def get_device_routing_table_for_ui(device: str, topology_id: str):
    """UI-friendly routing table endpoint."""
    if not (emulation_pb2 and emulation_pb2_grpc):
        raise HTTPException(status_code=503, detail="gRPC stubs not available in monitoring service")

    host = f"caduceus-emu-{topology_id[:8]}"
    try:
        channel = grpc.insecure_channel(
            f"{host}:50051",
            options=[
                ("grpc.max_send_message_length", 50 * 1024 * 1024),
                ("grpc.max_receive_message_length", 50 * 1024 * 1024),
            ],
        )
        stub = emulation_pb2_grpc.EmulationServiceStub(channel)
        resp = stub.GetRoutingTable(emulation_pb2.GetRoutingTableRequest(device=device))
        routes = []
        for r in resp.routes:
            routes.append(
                {
                    "destination": r.destination,
                    "gateway": r.gateway,
                    "interface": r.interface,
                    "metric": int(r.metric),
                    "protocol": r.protocol,
                }
            )
        return {"device": device, "timestamp": datetime.utcnow().isoformat(), "routes": routes}
    except Exception as e:
        logger.error(f"Failed to fetch routing table for {device} on {host}: {e}")
        _raise_grpc_as_http(topology_id, e, "Failed to fetch routing table from emulation container")


@app.get("/api/monitoring/devices/{device}/arp")
async def get_device_arp_table_for_ui(device: str, topology_id: str):
    """UI-friendly ARP table endpoint."""
    if not (emulation_pb2 and emulation_pb2_grpc):
        raise HTTPException(status_code=503, detail="gRPC stubs not available in monitoring service")

    host = f"caduceus-emu-{topology_id[:8]}"
    try:
        channel = grpc.insecure_channel(
            f"{host}:50051",
            options=[
                ("grpc.max_send_message_length", 50 * 1024 * 1024),
                ("grpc.max_receive_message_length", 50 * 1024 * 1024),
            ],
        )
        stub = emulation_pb2_grpc.EmulationServiceStub(channel)
        resp = stub.GetARPTable(emulation_pb2.GetARPTableRequest(device=device))
        entries = []
        for ent in resp.entries:
            entries.append(
                {
                    "ip": ent.ip,
                    "mac": ent.mac,
                    "interface": ent.interface,
                    "state": ent.state,
                }
            )
        return {"device": device, "timestamp": datetime.utcnow().isoformat(), "entries": entries}
    except Exception as e:
        logger.error(f"Failed to fetch ARP table for {device} on {host}: {e}")
        _raise_grpc_as_http(topology_id, e, "Failed to fetch ARP table from emulation container")


@app.get("/api/monitoring/switches/{switch}/flows")
async def get_switch_flow_table_for_ui(switch: str, topology_id: str):
    """UI-friendly switch flow table endpoint."""
    if not (emulation_pb2 and emulation_pb2_grpc):
        raise HTTPException(status_code=503, detail="gRPC stubs not available in monitoring service")

    host = f"caduceus-emu-{topology_id[:8]}"
    try:
        channel = grpc.insecure_channel(
            f"{host}:50051",
            options=[
                ("grpc.max_send_message_length", 50 * 1024 * 1024),
                ("grpc.max_receive_message_length", 50 * 1024 * 1024),
            ],
        )
        stub = emulation_pb2_grpc.EmulationServiceStub(channel)
        resp = stub.GetFlowTable(emulation_pb2.GetFlowTableRequest(switch=switch))
        flows = []
        for f in resp.flows:
            flows.append(
                {
                    "priority": int(f.priority),
                    "match": f.match,
                    "actions": f.actions,
                    "packet_count": int(f.packet_count),
                    "byte_count": int(f.byte_count),
                    "duration": int(f.duration),
                }
            )
        return {"switch": switch, "timestamp": datetime.utcnow().isoformat(), "flows": flows}
    except Exception as e:
        logger.error(f"Failed to fetch flow table for {switch} on {host}: {e}")
        _raise_grpc_as_http(topology_id, e, "Failed to fetch flow table from emulation container")


@app.get("/api/monitoring/topology/{topology_id}/metrics")
async def get_topology_metrics_for_ui(topology_id: str):
    """
    UI-friendly topology metrics endpoint (alias).
    Provides totals and best-effort rates for bandwidth/packets.
    """
    now = datetime.utcnow()
    topo: Dict[str, Any] = {}

    # Try gRPC direct metrics (preferred)
    total_rx_bytes = 0
    total_tx_bytes = 0
    total_rx_packets = 0
    total_tx_packets = 0
    device_count = 0

    if emulation_pb2 and emulation_pb2_grpc:
        host = f"caduceus-emu-{topology_id[:8]}"
        try:
            import httpx

            async with httpx.AsyncClient(timeout=8.0) as client:
                topo_res = await client.get(f"http://topology-service:8001/api/topologies/{topology_id}")
                topo = topo_res.json() if topo_res.status_code == 200 else {}
            device_names = [n.get("name") for n in (topo.get("nodes") or []) if isinstance(n, dict) and n.get("name")]
            device_count = len(device_names)

            if device_names:
                channel = grpc.insecure_channel(
                    f"{host}:50051",
                    options=[
                        ("grpc.max_send_message_length", 50 * 1024 * 1024),
                        ("grpc.max_receive_message_length", 50 * 1024 * 1024),
                    ],
                )
                stub = emulation_pb2_grpc.EmulationServiceStub(channel)
                resp = stub.GetMetrics(emulation_pb2.GetMetricsRequest(devices=device_names, metrics=[]))
                for dm in resp.device_metrics.values():
                    total_rx_bytes += int(dm.bytes_received)
                    total_tx_bytes += int(dm.bytes_sent)
                    total_rx_packets += int(dm.packets_received)
                    total_tx_packets += int(dm.packets_sent)
        except Exception as e:
            logger.error(f"Failed to fetch topology gRPC metrics on {host}: {e}")

    # Fallback: local aggregation (likely empty outside emulation container)
    if device_count == 0 and (total_rx_bytes + total_tx_bytes + total_rx_packets + total_tx_packets) == 0:
        aggregated = await get_topology_metrics(topology_id)
        total_rx_bytes = int(aggregated.get("total_rx_bytes", 0) or 0)
        total_tx_bytes = int(aggregated.get("total_tx_bytes", 0) or 0)
        total_rx_packets = int(aggregated.get("total_rx_packets", 0) or 0)
        total_tx_packets = int(aggregated.get("total_tx_packets", 0) or 0)
        device_count = int(aggregated.get("device_count", 0) or 0)

    total_bytes = total_rx_bytes + total_tx_bytes
    total_packets = total_rx_packets + total_tx_packets
    cache = _topology_rate_cache.get(topology_id)
    bandwidth = "—"
    packets_rate = "—"
    bandwidth_trend = None
    if cache and cache.get("ts"):
        dt = (now - cache["ts"]).total_seconds()
        # Avoid huge spikes from very small dt / counter resets; UI polls can be bursty.
        if dt >= 1.0:
            prev_bytes = float(cache.get("bytes", 0) or 0.0)
            prev_packets = float(cache.get("packets", 0) or 0.0)
            delta_bytes = float(total_bytes) - prev_bytes
            delta_packets = float(total_packets) - prev_packets
            if delta_bytes < 0 or delta_packets < 0:
                delta_bytes = 0.0
                delta_packets = 0.0
            bps = max(0.0, delta_bytes / dt)
            pps = max(0.0, delta_packets / dt)
            mbps = (bps * 8.0) / 1_000_000.0
            if mbps >= 1.0:
                bandwidth = f"{mbps:.2f} Mbps"
            else:
                kbps = (bps * 8.0) / 1_000.0
                if kbps >= 1.0:
                    bandwidth = f"{kbps:.1f} Kbps"
                else:
                    bandwidth = f"{(bps * 8.0):.0f} bps"

            packets_rate = f"{pps:.1f}/s" if pps >= 0.1 else f"{pps:.3f}/s"
            prev_mbps = float(cache.get("mbps", 0.0))
            if mbps > prev_mbps * 1.05:
                bandwidth_trend = "up"
            elif mbps < prev_mbps * 0.95:
                bandwidth_trend = "down"
            else:
                bandwidth_trend = "flat"

    _topology_rate_cache[topology_id] = {
        "ts": now,
        "bytes": float(total_bytes),
        "packets": float(total_packets),
        "mbps": float(bandwidth.split()[0]) if bandwidth != "—" else 0.0,
    }

    # Best-effort latency (cache to avoid spamming ping).
    latency = "—"
    latency_trend = None
    lat_cache = _topology_latency_cache.get(topology_id)
    if lat_cache and lat_cache.get("ts"):
        try:
            if (now - lat_cache["ts"]).total_seconds() < 10.0:
                ms = float(lat_cache.get("ms", 0.0) or 0.0)
                if ms > 0:
                    latency = f"{ms:.2f} ms"
                    latency_trend = lat_cache.get("trend")
        except Exception:
            pass

    if latency == "—" and emulation_pb2 and emulation_pb2_grpc:
        host = f"caduceus-emu-{topology_id[:8]}"
        try:
            import re

            # Prefer host->host; fall back to host->router.
            nodes = topo.get("nodes") if isinstance(topo, dict) else None
            nodes = nodes if isinstance(nodes, list) else []
            candidates = []
            for n in nodes:
                if not isinstance(n, dict):
                    continue
                name = n.get("name")
                dtype = (n.get("device_type") or "").lower()
                if not name:
                    continue
                if dtype in ("host", "router", "station", "docker", "docker_container", "container"):
                    candidates.append((str(name), dtype))

            src = next((nm for nm, dtp in candidates if dtp == "host"), None) or (candidates[0][0] if candidates else None)
            dst = next((nm for nm, dtp in candidates if nm != src and dtp == "host"), None)
            if not dst:
                dst = next((nm for nm, dtp in candidates if nm != src and dtp == "router"), None)

            if src and dst:
                channel = grpc.insecure_channel(
                    f"{host}:50051",
                    options=[
                        ("grpc.max_send_message_length", 50 * 1024 * 1024),
                        ("grpc.max_receive_message_length", 50 * 1024 * 1024),
                    ],
                )
                stub = emulation_pb2_grpc.EmulationServiceStub(channel)

                ip_resp = stub.ExecuteCommand(
                    emulation_pb2.ExecuteCommandRequest(
                        device=dst,
                        command="ip -4 -o addr show scope global | awk '{print $4}' | cut -d/ -f1 | head -n 1",
                    ),
                    timeout=5,
                )
                dst_ip = (ip_resp.stdout or "").strip()

                if dst_ip:
                    ping_resp = stub.ExecuteCommand(
                        emulation_pb2.ExecuteCommandRequest(
                            device=src,
                            command=f"ping -c 1 -W 1 {dst_ip}",
                        ),
                        timeout=8,
                    )
                    out = ping_resp.stdout or ""
                    m = re.search(r"time=([0-9]+(?:\.[0-9]+)?)\s*ms", out)
                    if m:
                        ms = float(m.group(1))
                        latency = f"{ms:.2f} ms"
                        prev_ms = float(lat_cache.get("ms", 0.0) or 0.0) if lat_cache else 0.0
                        if prev_ms > 0.0:
                            if ms > prev_ms * 1.05:
                                latency_trend = "up"
                            elif ms < prev_ms * 0.95:
                                latency_trend = "down"
                            else:
                                latency_trend = "flat"
                        _topology_latency_cache[topology_id] = {"ts": now, "ms": ms, "trend": latency_trend}
        except Exception:
            pass

    return {
        "topology_id": topology_id,
        "timestamp": now.isoformat(),
        "bandwidth": bandwidth,
        "bandwidthTrend": bandwidth_trend,
        "latency": latency,
        "latencyTrend": latency_trend,
        "packets": packets_rate if packets_rate != "—" else str(total_packets),
        "total_rx_bytes": total_rx_bytes,
        "total_tx_bytes": total_tx_bytes,
        "total_rx_packets": total_rx_packets,
        "total_tx_packets": total_tx_packets,
        "device_count": device_count,
    }


@app.get("/api/topology/{topology_id}/metrics")
async def get_topology_metrics(topology_id: str):
    """Get aggregated metrics for entire topology"""
    try:
        # Get topology devices from Topology Service
        import httpx
        
        aggregated = {
            "topology_id": topology_id,
            "timestamp": datetime.utcnow().isoformat(),
            "total_rx_bytes": 0,
            "total_tx_bytes": 0,
            "total_rx_packets": 0,
            "total_tx_packets": 0,
            "device_count": 0,
            "devices": []
        }
        
        # Fetch topology to get devices
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"http://topology-service:8001/api/topologies/{topology_id}")
                if response.status_code == 200:
                    topology = response.json()
                    devices = [node["name"] for node in topology.get("nodes", [])]
                    
                    for device in devices:
                        metrics = collect_device_metrics(device)
                        if metrics:
                            aggregated["devices"].append(metrics)
                            for iface_stats in metrics.get("interfaces", {}).values():
                                aggregated["total_rx_bytes"] += iface_stats.get("rx_bytes", 0)
                                aggregated["total_tx_bytes"] += iface_stats.get("tx_bytes", 0)
                                aggregated["total_rx_packets"] += iface_stats.get("rx_packets", 0)
                                aggregated["total_tx_packets"] += iface_stats.get("tx_packets", 0)
                    
                    aggregated["device_count"] = len(devices)
            except httpx.HTTPError as e:
                logger.error(f"Failed to fetch topology: {e}")
        
        return aggregated
    
    except Exception as e:
        logger.error(f"Error getting topology metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/metrics/{device}")
async def delete_device_metrics(device: str):
    """Delete all metrics for a device"""
    try:
        client, _ = get_influxdb_client()
        delete_api = client.delete_api()
        
        # Delete from InfluxDB
        start = "1970-01-01T00:00:00Z"
        stop = datetime.utcnow().isoformat() + "Z"
        
        delete_api.delete(
            start,
            stop,
            f'device="{device}"',
            bucket=INFLUXDB_BUCKET,
            org=INFLUXDB_ORG
        )
        
        logger.info(f"Deleted metrics for device: {device}")
        
        return {
            "success": True,
            "device": device,
            "message": "Metrics deleted"
        }
    
    except Exception as e:
        logger.error(f"Error deleting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)
