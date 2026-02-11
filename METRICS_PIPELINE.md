# Metrics Data Pipeline Documentation

## Overview

The Caduceus-Flux metrics pipeline is a comprehensive data streaming architecture that collects network metrics from Mininet simulations, processes them in real-time, stores them for analysis, and provides visualization capabilities.

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Layer I: Data Ingestion                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    Mininet Network Emulation
                    (Hosts, Switches, Routers)
                                    │
                                    ↓
                         gRPC Server (Port 50051)
                    EmulationService.StreamMetrics
                                    │
                                    ↓
                   Metrics Collector Service (Port 8013)
                    - gRPC Stream Consumer
                    - Batching & Buffering
                    - Kafka Producer
                                    │
                                    ↓
                        Kafka Topic: metrics.raw
                     (Partitioned by device name)
                                    │
┌─────────────────────────────────┴─────────────────────────────────────┐
│                                                                         │
│            Layer II: Persistence & Analysis                             │
│                                                                         │
├──────────────────────────────┬──────────────────────────────────────────┤
│                              │                                          │
│   Kafka Connect JDBC Sink    │     Kafka Connect InfluxDB Sink          │
│                              │                                          │
↓                              ↓                                          ↓
PostgreSQL                  Monitoring Service (8011)               InfluxDB
- network_metrics           - Kafka Consumer                        - Real-time metrics
- interface_metrics         - Prometheus Exporter                   - Time-series DB
- protocol_metrics          - Direct InfluxDB writes                - High-performance queries
- flow_metrics                                                      │
- ml_training_features                                              ↓
│                                                                   Grafana
↓                                                                   - Dashboards
ML Training & Analytics                                             - Alerts
- Feature Engineering                                               - Visualization
- Model Training
- Predictions
```

## Data Flow

### 1. **Metric Generation (Mininet)**

**Source:** Network devices in Mininet emulation

**Metrics Collected:**
- Interface statistics (RX/TX bytes, packets, errors, drops)
- CPU usage per device
- Memory usage per device
- Protocol metrics (OSPF, BGP neighbors, routes)
- Flow table statistics (OpenFlow switches)

**Collection Method:** Polling via subprocess commands in network namespaces

### 2. **gRPC Streaming (Port 50051)**

**Service:** `EmulationService.StreamMetrics`

**Protocol:** gRPC with Protobuf serialization

**Message Format:**
```protobuf
message MetricsUpdate {
    int64 timestamp = 1;
    map<string, DeviceMetrics> device_metrics = 2;
}

message DeviceMetrics {
    int64 bytes_sent = 1;
    int64 bytes_received = 2;
    int64 packets_sent = 3;
    int64 packets_received = 4;
    int64 errors_in = 5;
    int64 errors_out = 6;
    int64 drops_in = 7;
    int64 drops_out = 8;
    double cpu_percent = 9;
    double memory_percent = 10;
}
```

**Stream Characteristics:**
- Real-time streaming
- Configurable interval (default: 5 seconds)
- Bidirectional (can be paused/resumed)
- Automatic reconnection

### 3. **Metrics Collector Service (Port 8013)**

**Role:** Bridge between gRPC and Kafka

**Responsibilities:**
1. **Consume** gRPC metrics stream
2. **Buffer** metrics in memory
3. **Batch** messages for efficiency
4. **Produce** to Kafka topic `metrics.raw`

**Configuration:**
```env
METRICS_COLLECTION_INTERVAL=5     # Streaming interval (seconds)
METRICS_BATCH_SIZE=100            # Messages per Kafka batch
METRICS_BUFFER_SIZE=1000          # Max buffer before flush
```

**API Endpoints:**
```bash
POST /api/start-collection  # Start collecting from devices
POST /api/stop-collection   # Stop collection
POST /api/flush             # Manually flush buffer
GET  /api/stats             # View collection statistics
GET  /health                # Service health check
```

**Message Format (Kafka):**
```json
{
  "device": "h1",
  "timestamp": "2025-10-08T10:30:45.123Z",
  "metrics": {
    "bytes_sent": 1048576,
    "bytes_received": 2097152,
    "packets_sent": 1024,
    "packets_received": 2048,
    "errors_in": 0,
    "errors_out": 0,
    "drops_in": 0,
    "drops_out": 5,
    "cpu_percent": 45.2,
    "memory_percent": 62.8
  },
  "source": "caduceus-metrics-collector"
}
```

### 4. **Kafka Broker (Ports 9092, 29092)**

**Topic:** `metrics.raw`

**Partitioning:** By device name (ensures ordering per device)

**Retention:** 7 days (168 hours)

**Compression:** gzip

**Replication:** 1 (single broker setup)

**Performance:**
- Throughput: ~10,000 messages/sec
- Latency: <10ms (p99)
- Disk usage: ~1GB/day (typical)

### 5. **Kafka Connect Sinks**

#### A. JDBC Sink → PostgreSQL

**Purpose:** Long-term storage for analytics and ML training

**Connector:** `io.confluent.connect.jdbc.JdbcSinkConnector`

**Target Tables:**
- `network_metrics` - Main aggregated metrics
- `interface_metrics` - Per-interface statistics
- `protocol_metrics` - Routing protocol data
- `flow_metrics` - OpenFlow statistics
- `ml_training_features` - Engineered features

**Write Mode:** Insert-only

**Batch Size:** 1000 messages

**Features:**
- Automatic schema evolution (disabled for safety)
- Dead letter queue for failed writes
- Exactly-once semantics (with idempotence)

#### B. InfluxDB Sink → InfluxDB

**Purpose:** Real-time time-series storage for Grafana

**Connector:** `com.github.jcustenborder.kafka.connect.influxdb.InfluxDBSinkConnector`

**Measurement:** `network_metrics`

**Tags:**
- `device` - Device name
- `source` - Data source identifier

**Fields:** All numeric metrics (bytes, packets, CPU, memory, etc.)

**Batch Size:** 500 messages

**Flush Interval:** 1 second

### 6. **Monitoring Service (Port 8011)**

**Dual Role:**
1. **Kafka Consumer** - Consumes from `metrics.raw`
2. **Direct Collector** - Manual metrics collection via API

**Kafka Consumer:**
- Group ID: `monitoring-service-consumer`
- Auto-commit: Enabled
- Offset reset: Latest (for new consumers)

**Outputs:**
1. **InfluxDB** - Direct writes (parallel to Kafka Connect)
2. **Prometheus** - Exposes `/metrics` endpoint

**Prometheus Metrics:**
```
device_rx_bytes{device="h1",interface="eth0"} 1048576
device_tx_bytes{device="h1",interface="eth0"} 2097152
device_cpu_percent{device="h1"} 45.2
device_memory_mb{device="h1"} 10048
```

### 7. **PostgreSQL Storage**

**Database:** `caduceus_flux`

**Schema Features:**
- **TimescaleDB** extension for time-series optimization
- **Hypertables** for automatic partitioning
- **Continuous Aggregates** for pre-computed roll-ups
- **Retention Policies** for automatic data cleanup

**Tables:**

| Table | Purpose | Retention |
|-------|---------|-----------|
| `network_metrics` | Raw device metrics | 7 days |
| `interface_metrics` | Interface-level stats | 7 days |
| `protocol_metrics` | Protocol statistics | 7 days |
| `flow_metrics` | OpenFlow flows | 7 days |
| `metrics_1min` | 1-minute aggregates | 30 days |
| `metrics_5min` | 5-minute aggregates | 90 days |
| `ml_training_features` | ML features | Permanent |

**Query Examples:**
```sql
-- Latest metrics for a device
SELECT * FROM get_latest_metrics('h1');

-- Average throughput over last hour
SELECT
  device,
  avg_bytes_sent,
  avg_bytes_received
FROM metrics_1min
WHERE time_bucket >= NOW() - INTERVAL '1 hour'
  AND device = 'h1';

-- High CPU devices
SELECT device, avg_cpu_percent
FROM metrics_1min
WHERE time_bucket >= NOW() - INTERVAL '5 minutes'
  AND avg_cpu_percent > 80
ORDER BY avg_cpu_percent DESC;
```

### 8. **InfluxDB Storage**

**Organization:** `caduceus-flux`

**Bucket:** `metrics`

**Retention:** 30 days

**Measurement:** `network_metrics`

**Query Examples (Flux):**
```flux
// Last hour of metrics for device h1
from(bucket: "metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r.device == "h1")
  |> filter(fn: (r) => r._measurement == "network_metrics")

// Average CPU by device
from(bucket: "metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r._field == "cpu_percent")
  |> group(columns: ["device"])
  |> mean()
```

### 9. **Grafana Visualization**

**Data Sources:**
- InfluxDB (primary)
- Prometheus (secondary)
- PostgreSQL (for analytics)

**Dashboards:**
- Network Topology Overview
- Device Performance Metrics
- Protocol Convergence Analysis
- Traffic Flow Visualization
- ML Model Performance

## Metrics Types

### Network Traffic Metrics

| Metric | Type | Unit | Description |
|--------|------|------|-------------|
| `bytes_sent` | Counter | bytes | Total bytes transmitted |
| `bytes_received` | Counter | bytes | Total bytes received |
| `packets_sent` | Counter | count | Total packets transmitted |
| `packets_received` | Counter | count | Total packets received |
| `errors_in` | Counter | count | Inbound errors |
| `errors_out` | Counter | count | Outbound errors |
| `drops_in` | Counter | count | Inbound packet drops |
| `drops_out` | Counter | count | Outbound packet drops |

### System Metrics

| Metric | Type | Unit | Description |
|--------|------|------|-------------|
| `cpu_percent` | Gauge | % | CPU utilization |
| `memory_percent` | Gauge | % | Memory utilization |
| `process_count` | Gauge | count | Running processes |

### Protocol Metrics

| Metric | Type | Unit | Description |
|--------|------|------|-------------|
| `neighbor_count` | Gauge | count | Protocol neighbors (OSPF, BGP) |
| `route_count` | Gauge | count | Number of routes |
| `convergence_time` | Histogram | seconds | Protocol convergence time |

## Data Pipeline Modes

### 1. **Real-time Mode** (Default)

- Metrics streamed every 5 seconds
- Immediate Kafka publication
- Sub-second latency to Grafana
- Suitable for: Live monitoring, alerting

### 2. **Batch Mode**

- Metrics collected in batches
- Periodic flush (every 10 seconds)
- Higher throughput, lower overhead
- Suitable for: High-volume emulations

### 3. **On-demand Mode**

- Manual metric collection via API
- No continuous streaming
- Suitable for: Testing, debugging

## Performance Characteristics

### Throughput

- **Metrics Collector:** 10,000 metrics/second
- **Kafka Broker:** 50,000 messages/second
- **PostgreSQL Writes:** 5,000 inserts/second
- **InfluxDB Writes:** 20,000 points/second

### Latency

- **gRPC Stream:** <5ms
- **Kafka Producer:** <10ms
- **End-to-End (Mininet → Grafana):** <500ms

### Storage

- **Kafka:** ~100MB/day (10 devices, 5s interval)
- **PostgreSQL:** ~500MB/day (with retention)
- **InfluxDB:** ~300MB/day (compressed)

## Error Handling

### Dead Letter Queue (DLQ)

**Topic:** `metrics.dlq`

**Purpose:** Store failed messages for investigation

**Triggers:**
- Invalid message format
- Database connection failures
- Schema mismatches

**Recovery:**
```bash
# Inspect DLQ messages
docker exec caduceus-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic metrics.dlq \
  --from-beginning

# Reprocess from DLQ (manual)
# Fix issue, then replay messages to original topic
```

### Circuit Breakers

- **Kafka Producer:** Retry with exponential backoff
- **JDBC Sink:** Pause on repeated failures
- **InfluxDB Sink:** Buffer and retry

## Monitoring the Pipeline

### Key Metrics to Watch

```bash
# Kafka lag
docker exec caduceus-kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group monitoring-service-consumer \
  --describe

# Connector status
curl http://localhost:8083/connectors/jdbc-sink-metrics/status

# Metrics collector stats
curl http://localhost:8013/api/stats

# Database row counts
docker exec caduceus-postgres psql -U caduceus -d caduceus_flux \
  -c "SELECT COUNT(*) FROM network_metrics;"
```

### Alerts

Recommended alerts:
- Kafka consumer lag > 1000
- Metrics collector buffer overflow
- Database write failures
- Connector task failures

## Best Practices

1. **Partitioning:** Use device name for consistent ordering
2. **Batching:** Balance latency vs throughput
3. **Retention:** Match to use case (7d raw, 30d aggregates)
4. **Monitoring:** Track pipeline health metrics
5. **Backpressure:** Implement circuit breakers
6. **Scaling:** Add Kafka partitions for more devices

## Troubleshooting Guide

See [KAFKA_SETUP.md](KAFKA_SETUP.md#troubleshooting) for detailed troubleshooting steps.

## Next Steps

- Configure [Grafana Dashboards](infrastructure/grafana/README.md)
- Set up [ML Training Pipeline](docs/ML_TRAINING.md)
- Enable [Kafka Security](docs/KAFKA_SECURITY.md)
