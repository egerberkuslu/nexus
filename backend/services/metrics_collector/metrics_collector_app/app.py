"""
Metrics Collector Service (Port 8013)
Bridges gRPC metrics streaming from emulation container to Kafka
"""

import logging
import asyncio
import sys
import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import grpc
import httpx

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

import emulation_pb2
import emulation_pb2_grpc

from shared.messaging.kafka_producer import CaduceusKafkaProducer, get_kafka_producer
from shared.messaging.rabbitmq import RabbitMQPublisher
from shared.utils.consul_client import ConsulClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Caduceus-Flux Metrics Collector Service",
    description="Collects metrics from emulation container and streams to Kafka",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service configuration
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8013"))
KAFKA_ENABLED = os.getenv("KAFKA_ENABLED", "true").lower() == "true"
METRICS_COLLECTION_INTERVAL = int(os.getenv("METRICS_COLLECTION_INTERVAL", "5"))
METRICS_BATCH_SIZE = int(os.getenv("METRICS_BATCH_SIZE", "100"))
METRICS_BUFFER_SIZE = int(os.getenv("METRICS_BUFFER_SIZE", "1000"))
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator-service:8002")
MONITORING_URL = os.getenv("MONITORING_URL", "http://monitoring-service:8011")
MONITORING_INGEST_ENABLED = os.getenv("MONITORING_INGEST_ENABLED", "true").lower() == "true"
ACTIVE_POLL_INTERVAL = int(os.getenv("ACTIVE_EMULATION_POLL_INTERVAL", "10"))
AUTO_START_COLLECTION = os.getenv("AUTO_START_COLLECTION", "true").lower() == "true"

# Service clients
consul_client = ConsulClient()
rabbitmq_publisher = RabbitMQPublisher()
kafka_producer: Optional[CaduceusKafkaProducer] = None

# Metrics collection state
collection_active = False
collection_task = None
discovery_task: Optional[asyncio.Task] = None
metrics_buffer: List[Dict[str, Any]] = []
topology_stream_tasks: Dict[str, asyncio.Task] = {}
topology_last_seen: Dict[str, float] = {}
stats = {
    "metrics_collected": 0,
    "metrics_sent_to_kafka": 0,
    "errors": 0,
    "buffer_overflows": 0
}

def _escape_tag(value: Any) -> str:
    s = str(value)
    return s.replace("\\", "\\\\").replace(" ", "\\ ").replace(",", "\\,").replace("=", "\\=")


def _iso_to_epoch_ms(ts: Any) -> int:
    if isinstance(ts, (int, float)):
        return int(ts)
    if isinstance(ts, str) and ts.strip():
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000)
        except Exception:
            return int(datetime.utcnow().timestamp() * 1000)
    return int(datetime.utcnow().timestamp() * 1000)


def _metric_to_line(metric: Dict[str, Any]) -> Optional[str]:
    metrics = metric.get("metrics") if isinstance(metric.get("metrics"), dict) else {}
    topology_id = metric.get("topology_id") or metrics.get("topology_id")
    emulation_id = metric.get("emulation_id") or metrics.get("emulation_id")
    device = metric.get("device") or metrics.get("device")
    source = metric.get("source") or metrics.get("source") or "grpc"
    if not topology_id or not device:
        return None

    tags = {
        "device": device,
        "topology_id": topology_id,
        "source": source,
    }
    if emulation_id:
        tags["emulation_id"] = emulation_id

    int_fields = [
        "bytes_sent",
        "bytes_received",
        "packets_sent",
        "packets_received",
        "errors_in",
        "errors_out",
        "drops_in",
        "drops_out",
    ]
    float_fields = ["cpu_percent", "memory_percent"]

    fields: list[str] = []
    for k in int_fields:
        if k in metrics:
            try:
                fields.append(f"{k}={int(metrics[k])}i")
            except Exception:
                pass
    for k in float_fields:
        if k in metrics:
            try:
                fields.append(f"{k}={float(metrics[k])}")
            except Exception:
                pass
    if not fields:
        return None

    tag_str = ",".join([f"{k}={_escape_tag(v)}" for k, v in tags.items()])
    field_str = ",".join(fields)
    ts_ms = _iso_to_epoch_ms(metric.get("timestamp") or metrics.get("timestamp"))
    return f"network_metrics,{tag_str} {field_str} {ts_ms}"


async def _write_to_topology_influx(topology_id: str, metrics: List[Dict[str, Any]]) -> bool:
    """
    Best-effort write to a topology's isolated InfluxDB, if configured in Consul.
    """
    try:
        infra_raw = consul_client.get_config(f"caduceus/topologies/{topology_id}/isolated_infra")
        token = consul_client.get_config(f"caduceus/topologies/{topology_id}/isolated_influx_token")
        org = consul_client.get_config(f"caduceus/topologies/{topology_id}/isolated_influx_org")
        bucket = consul_client.get_config(f"caduceus/topologies/{topology_id}/isolated_influx_bucket")
        if not infra_raw or not token or not org or not bucket:
            return False
        infra = json.loads(infra_raw) if isinstance(infra_raw, str) else {}
        influx_url = (((infra or {}).get("internal") or {}).get("influxdb_url")) or None
        if not influx_url:
            return False

        lines = []
        for m in metrics:
            line = _metric_to_line(m)
            if line:
                lines.append(line)
        if not lines:
            return True

        write_url = f"{influx_url}/api/v2/write"
        params = {"org": org, "bucket": bucket, "precision": "ms"}
        headers = {"Authorization": f"Token {token}", "Content-Type": "text/plain; charset=utf-8"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(write_url, params=params, content="\n".join(lines) + "\n", headers=headers)
        if res.status_code >= 400:
            logger.warning("Influx write failed for topology %s (HTTP %s): %s", topology_id, res.status_code, res.text[:300])
            return False
        return True
    except Exception as e:
        logger.warning("Influx write failed for topology %s: %s", topology_id, e)
        return False

def _topology_host(topology_id: str) -> str:
    return f"caduceus-emu-{topology_id[:8]}"


async def _list_active_emulations() -> List[Dict[str, Any]]:
    async with httpx.AsyncClient(timeout=5.0) as client:
        res = await client.get(f"{ORCHESTRATOR_URL}/api/emulation/active")
    res.raise_for_status()
    data = res.json() or {}
    emulations = data.get("emulations") or []
    if not isinstance(emulations, list):
        return []
    return [e for e in emulations if isinstance(e, dict)]


async def _stream_topology_metrics(topology_id: str, emulation_id: Optional[str]) -> None:
    """
    Stream metrics from a running emulation container and publish to Kafka.
    Adds `topology_id` and `emulation_id` so downstream consumers can persist per-topology.
    """
    host = _topology_host(topology_id)
    interval = METRICS_COLLECTION_INTERVAL

    channel = grpc.aio.insecure_channel(
        f"{host}:50051",
        options=[
            ("grpc.max_send_message_length", 100 * 1024 * 1024),
            ("grpc.max_receive_message_length", 100 * 1024 * 1024),
        ],
    )
    stub = emulation_pb2_grpc.EmulationServiceStub(channel)

    try:
        resp = await stub.ListDevices(emulation_pb2.ListDevicesRequest(device_type=""))
        devices = [d.name for d in (resp.devices or []) if getattr(d, "name", None)]
        if not devices:
            logger.info("No devices found for topology %s; skipping metrics stream", topology_id)
            return

        req = emulation_pb2.StreamMetricsRequest(devices=devices, interval_seconds=interval)
        logger.info("Starting metrics stream for topology %s (%s devices) via %s", topology_id, len(devices), host)

        async for update in stub.StreamMetrics(req):
            if not collection_active:
                break
            ts = datetime.utcfromtimestamp(float(update.timestamp) / 1000.0).isoformat()
            for dev, dm in (update.device_metrics or {}).items():
                metric_fields = {
                    "topology_id": topology_id,
                    "emulation_id": emulation_id,
                    "device": dev,
                    "source": "grpc",
                    "timestamp": ts,
                    "bytes_sent": dm.bytes_sent,
                    "bytes_received": dm.bytes_received,
                    "packets_sent": dm.packets_sent,
                    "packets_received": dm.packets_received,
                    "errors_in": dm.errors_in,
                    "errors_out": dm.errors_out,
                    "drops_in": dm.drops_in,
                    "drops_out": dm.drops_out,
                    "cpu_percent": dm.cpu_percent,
                    "memory_percent": dm.memory_percent,
                }
                await buffer_metrics(
                    {
                        "topology_id": topology_id,
                        "emulation_id": emulation_id,
                        "device": dev,
                        "source": "grpc",
                        "timestamp": ts,
                        "metrics": metric_fields,
                    }
                )
    except Exception as e:
        logger.warning("Topology metrics stream ended for %s (%s): %s", topology_id, host, e)
        stats["errors"] += 1
    finally:
        try:
            await channel.close()
        except Exception:
            pass


async def _poll_and_stream_loop() -> None:
    global topology_stream_tasks
    while collection_active:
        try:
            emulations = await _list_active_emulations()
            now = asyncio.get_running_loop().time()
            running: Dict[str, Dict[str, Any]] = {}
            for e in emulations:
                if e.get("status") != "running":
                    continue
                tid = e.get("topology_id")
                if not tid:
                    continue
                running[str(tid)] = e
                topology_last_seen[str(tid)] = now

            # Start new streams
            for tid, e in running.items():
                if tid in topology_stream_tasks and not topology_stream_tasks[tid].done():
                    continue
                topology_stream_tasks[tid] = asyncio.create_task(
                    _stream_topology_metrics(tid, e.get("emulation_id"))
                )

            # Stop streams for topologies that disappeared
            for tid in list(topology_stream_tasks.keys()):
                if tid in running:
                    continue
                task = topology_stream_tasks.pop(tid, None)
                if task and not task.done():
                    task.cancel()

        except Exception as e:
            logger.warning("Active emulation poll failed: %s", e)
            stats["errors"] += 1

        await asyncio.sleep(ACTIVE_POLL_INTERVAL)


async def buffer_metrics(metrics: Dict[str, Any]):
    """
    Buffer metrics and send to Kafka when batch size reached

    Args:
        metrics: Metrics dictionary
    """
    global metrics_buffer

    metrics_buffer.append(metrics)
    stats["metrics_collected"] += 1

    # Check buffer size
    if len(metrics_buffer) >= METRICS_BATCH_SIZE:
        await flush_buffer()
    elif len(metrics_buffer) >= METRICS_BUFFER_SIZE:
        # Buffer overflow - flush and warn
        logger.warning(f"Metrics buffer overflow! Flushing {len(metrics_buffer)} metrics")
        stats["buffer_overflows"] += 1
        await flush_buffer()


async def flush_buffer():
    """Flush metrics buffer to Kafka"""
    global metrics_buffer

    if not metrics_buffer:
        return

    # Prefer isolated per-topology InfluxDB when available (doesn't require Kafka).
    try:
        by_topology: Dict[str, List[Dict[str, Any]]] = {}
        for m in metrics_buffer:
            tid = m.get("topology_id") if isinstance(m, dict) else None
            if not tid:
                continue
            by_topology.setdefault(str(tid), []).append(m)
        for tid, rows in by_topology.items():
            await _write_to_topology_influx(tid, rows)
    except Exception as e:
        logger.warning("Topology Influx write step failed: %s", e)

    if MONITORING_INGEST_ENABLED:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(f"{MONITORING_URL}/api/monitoring/ingest/metrics", json=metrics_buffer)
            if res.status_code >= 400:
                logger.warning("Monitoring ingest failed (HTTP %s): %s", res.status_code, res.text[:500])
        except Exception as e:
            logger.warning("Monitoring ingest failed: %s", e)

    if not KAFKA_ENABLED:
        logger.debug(f"Kafka disabled - discarding {len(metrics_buffer)} metrics")
        metrics_buffer.clear()
        return

    try:
        # Send batch to Kafka
        count = kafka_producer.send_batch(
            topic=os.getenv("KAFKA_METRICS_TOPIC", "metrics.raw"),
            messages=metrics_buffer,
            key_extractor=lambda m: m.get("device")
        )

        stats["metrics_sent_to_kafka"] += count
        logger.debug(f"Flushed {count} metrics to Kafka")

        # Clear buffer
        metrics_buffer.clear()

    except Exception as e:
        logger.error(f"Error flushing buffer to Kafka: {e}")
        stats["errors"] += 1
        # Don't clear buffer - try again later
        if len(metrics_buffer) > METRICS_BUFFER_SIZE:
            # Emergency clear to prevent memory issues
            metrics_buffer = metrics_buffer[-METRICS_BATCH_SIZE:]


async def periodic_flush_task():
    """Periodically flush metrics buffer"""
    while collection_active:
        await asyncio.sleep(10)  # Flush every 10 seconds
        if metrics_buffer:
            await flush_buffer()

async def _start_collection() -> None:
    global collection_active, collection_task, discovery_task
    if collection_active:
        return
    collection_active = True
    collection_task = asyncio.create_task(periodic_flush_task())
    discovery_task = asyncio.create_task(_poll_and_stream_loop())
    logger.info("Started metrics collection (auto topology discovery)")


@app.on_event("startup")
async def startup_event():
    """Service startup"""
    global kafka_producer, collection_task

    logger.info("Starting Metrics Collector Service...")

    try:
        # Initialize Kafka producer
        if KAFKA_ENABLED:
            kafka_producer = get_kafka_producer()
            logger.info("Kafka producer initialized")
        else:
            logger.warning("Kafka is disabled - metrics will not be persisted")

        # Register with Consul
        consul_client.register_service("metrics-collector", SERVICE_PORT)

        # Connect to RabbitMQ for control events
        rabbitmq_publisher.connect()

        logger.info("Metrics Collector Service started successfully")

        if AUTO_START_COLLECTION:
            await _start_collection()

    except Exception as e:
        logger.error(f"Startup error: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Service shutdown"""
    global collection_active, collection_task, discovery_task

    logger.info("Shutting down Metrics Collector Service...")

    # Stop collection
    collection_active = False
    if collection_task:
        collection_task.cancel()
    if discovery_task:
        discovery_task.cancel()

    # Flush remaining metrics
    await flush_buffer()

    # Disconnect from services
    if kafka_producer:
        kafka_producer.disconnect()

    consul_client.deregister_service("metrics-collector")
    rabbitmq_publisher.disconnect()


# ==================== API Endpoints ====================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "metrics-collector",
        "kafka_enabled": KAFKA_ENABLED,
        "kafka_connected": kafka_producer is not None if KAFKA_ENABLED else None,
        "collection_active": collection_active,
        "auto_start_collection": AUTO_START_COLLECTION,
        "discovery_running": bool(discovery_task and not discovery_task.done()),
        "active_streams": len([t for t in topology_stream_tasks.values() if t and not t.done()]),
        "buffer_size": len(metrics_buffer),
        "stats": stats
    }


@app.post("/api/start-collection")
async def start_collection(devices: Optional[List[str]] = None):
    """
    Start metrics collection (auto-discovers running emulations).
    """
    global collection_active

    try:
        if collection_active:
            return {
                "success": False,
                "message": "Collection already active"
            }

        await _start_collection()

        return {
            "success": True,
            "message": "Collection started (auto topology discovery)",
            "interval": METRICS_COLLECTION_INTERVAL
        }

    except Exception as e:
        logger.error(f"Error starting collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/stop-collection")
async def stop_collection():
    """Stop metrics collection"""
    global collection_active, collection_task, discovery_task

    try:
        if not collection_active:
            return {
                "success": False,
                "message": "Collection not active"
            }

        collection_active = False

        if collection_task:
            collection_task.cancel()
            collection_task = None
        if discovery_task:
            discovery_task.cancel()
            discovery_task = None

        # Cancel topology streams
        for tid, task in list(topology_stream_tasks.items()):
            if task and not task.done():
                task.cancel()
            topology_stream_tasks.pop(tid, None)

        # Flush remaining metrics
        await flush_buffer()

        logger.info("Stopped metrics collection")

        return {
            "success": True,
            "message": "Collection stopped",
            "stats": stats
        }

    except Exception as e:
        logger.error(f"Error stopping collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
async def get_stats():
    """Get collection statistics"""
    return {
        "stats": stats,
        "buffer_size": len(metrics_buffer),
        "collection_active": collection_active,
        "kafka_producer_stats": kafka_producer.get_stats() if kafka_producer else None
    }


@app.post("/api/flush")
async def manual_flush():
    """Manually flush metrics buffer"""
    try:
        buffer_size = len(metrics_buffer)
        await flush_buffer()

        return {
            "success": True,
            "message": f"Flushed {buffer_size} metrics",
            "buffer_size_before": buffer_size,
            "buffer_size_after": len(metrics_buffer)
        }

    except Exception as e:
        logger.error(f"Error flushing buffer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/collect/{device}")
async def collect_device_metrics(device: str):
    """Manually trigger metrics collection for a single device"""
    try:
        raise HTTPException(
            status_code=400,
            detail="Manual collection is disabled in topology-auto mode; use /api/start-collection"
        )

        # Send to Kafka if enabled
        if KAFKA_ENABLED and kafka_producer:
            for metric in metrics:
                kafka_producer.send_metrics(device, metric)

        return {
            "success": True,
            "device": device,
            "metrics": metrics[0] if metrics else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error collecting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)
