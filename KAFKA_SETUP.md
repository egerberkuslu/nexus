# Kafka Streaming Infrastructure Setup Guide

## Overview

Caduceus-Flux uses Apache Kafka as the central data streaming platform for collecting, processing, and distributing network metrics from Mininet emulations. This guide covers the complete setup and operation of the Kafka-based metrics pipeline.

## Architecture

```
Mininet → gRPC (50051) → Metrics Collector Service (8013) → Kafka (metrics.raw topic)
                                                                    ↓
                                    ┌───────────────────────────────┴────────────────────────────┐
                                    ↓                                                            ↓
                          Kafka Connect JDBC Sink                               Kafka Connect InfluxDB Sink
                                    ↓                                                            ↓
                              PostgreSQL                                                    InfluxDB
                          (Historical Data)                                            (Time-Series Metrics)
                                    ↓                                                            ↓
                          ML Training & Analytics                                          Grafana Dashboards
```

## Components

### 1. **Zookeeper** (Port 2181)
- Coordinates Kafka brokers
- Manages cluster metadata
- Ensures distributed consensus

### 2. **Kafka Broker** (Ports 9092, 29092)
- Main message broker
- Stores metrics streams in topics
- Provides fault-tolerant messaging

### 3. **Schema Registry** (Port 8081)
- Manages Avro/Protobuf schemas
- Ensures data compatibility
- Version control for message formats

### 4. **Kafka Connect** (Port 8083)
- Connects Kafka to external systems
- JDBC Sink: Kafka → PostgreSQL
- InfluxDB Sink: Kafka → InfluxDB

### 5. **Metrics Collector Service** (Port 8013)
- Bridges gRPC → Kafka
- Batches and buffers metrics
- Produces to `metrics.raw` topic

### 6. **Monitoring Service** (Port 8011)
- Consumes metrics from Kafka
- Updates Prometheus metrics
- Writes to InfluxDB (direct path)

## Quick Start

### 1. Enable Kafka in Environment

```bash
# Edit .env file
KAFKA_ENABLED=true
```

### 2. Start All Services

```bash
./start-services.sh
```

This will start:
- Zookeeper
- Kafka broker
- Schema Registry
- Kafka Connect
- Metrics Collector Service
- All other Caduceus services

### 3. Verify Kafka is Running

```bash
# Check Kafka broker
docker logs caduceus-kafka

# Check Kafka Connect
curl http://localhost:8083/connectors

# List Kafka topics
docker exec caduceus-kafka kafka-topics --bootstrap-server localhost:9092 --list
```

### 4. Initialize Database Schema

```bash
# Run PostgreSQL migrations
docker exec -i caduceus-postgres psql -U caduceus -d caduceus_flux < backend/database/migrations/001_create_metrics_tables.sql
```

### 5. Deploy Kafka Connect Connectors

```bash
# Deploy JDBC and InfluxDB sinks
./infrastructure/kafka-connect/deploy-connectors.sh
```

### 6. Start Metrics Collection

```bash
# Via API (after starting emulation)
curl -X POST http://localhost:8013/api/start-collection \
  -H "Content-Type: application/json" \
  -d '{"devices": ["h1", "h2", "s1"]}'
```

## Topics

### Core Topics

| Topic | Purpose | Retention | Partitions |
|-------|---------|-----------|------------|
| `metrics.raw` | Raw metrics from emulation | 7 days | 3 |
| `metrics.processed` | Processed/aggregated metrics | 30 days | 3 |
| `alerts.anomaly` | Anomaly alerts from decision engine | 30 days | 3 |
| `alerts.security` | Security/attack alerts from decision engine | 30 days | 3 |
| `actions.routing` | Routing/TE actions from decision engine | 30 days | 3 |
| `actions.mano` | MANO actions from decision engine | 30 days | 3 |
| `events` | System events (topology changes, etc.) | 30 days | 1 |
| `metrics.dlq` | Dead letter queue for failed messages | 7 days | 1 |

### Topic Configuration

```bash
# Create topics manually (auto-create is enabled by default)
docker exec caduceus-kafka kafka-topics \
  --create \
  --bootstrap-server localhost:9092 \
  --topic metrics.raw \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000
```

## Kafka Connect Connectors

### JDBC Sink Connector (Kafka → PostgreSQL)

**Purpose:** Stream metrics to PostgreSQL for historical analysis and ML training

**Configuration:** `infrastructure/kafka-connect/connectors/jdbc-sink-metrics.json`

**Tables:**
- `network_metrics` - Main metrics table
- `interface_metrics` - Interface-level metrics
- `protocol_metrics` - Routing protocol metrics
- `flow_metrics` - OpenFlow flow statistics
- `ml_training_features` - Engineered features for ML

**Check Status:**
```bash
curl http://localhost:8083/connectors/jdbc-sink-metrics/status | jq
```

### InfluxDB Sink Connector (Kafka → InfluxDB)

**Purpose:** Stream metrics to InfluxDB for real-time visualization in Grafana

**Configuration:** `infrastructure/kafka-connect/connectors/influxdb-sink-metrics.json`

**Measurements:**
- `network_metrics` - All device metrics with tags (device, source)

**Check Status:**
```bash
curl http://localhost:8083/connectors/influxdb-sink-metrics/status | jq
```

## Monitoring Kafka

### Metrics Collector Service

```bash
# Check health
curl http://localhost:8013/health | jq

# View stats
curl http://localhost:8013/api/stats | jq

# Manual flush
curl -X POST http://localhost:8013/api/flush

# Stop collection
curl -X POST http://localhost:8013/api/stop-collection
```

### Kafka Broker Metrics

```bash
# Consumer groups
docker exec caduceus-kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --list

# Consumer group lag
docker exec caduceus-kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group monitoring-service-consumer \
  --describe
```

### Kafka Connect Logs

```bash
# View connector logs
docker logs caduceus-kafka-connect

# Restart connector
curl -X POST http://localhost:8083/connectors/jdbc-sink-metrics/restart
```

## Troubleshooting

### Issue: Kafka broker not starting

**Check:**
```bash
docker logs caduceus-kafka
```

**Common causes:**
- Zookeeper not ready
- Port conflicts (9092, 29092)
- Insufficient memory

**Solution:**
```bash
# Restart services in order
docker-compose restart zookeeper
docker-compose restart kafka
```

### Issue: Metrics not appearing in PostgreSQL

**Check:**
1. Kafka topic has messages:
```bash
docker exec caduceus-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic metrics.raw \
  --from-beginning \
  --max-messages 10
```

2. JDBC connector is running:
```bash
curl http://localhost:8083/connectors/jdbc-sink-metrics/status
```

3. PostgreSQL connection:
```bash
docker exec caduceus-postgres psql -U caduceus -d caduceus_flux \
  -c "SELECT COUNT(*) FROM network_metrics;"
```

**Solution:**
- Check connector logs in Kafka Connect
- Verify database credentials in connector config
- Ensure table schema exists

### Issue: InfluxDB not receiving metrics

**Check:**
```bash
# Query InfluxDB
docker exec caduceus-influxdb influx query \
  'from(bucket: "metrics") |> range(start: -1h) |> limit(n: 10)'
```

**Solution:**
- Verify InfluxDB token in connector config
- Check InfluxDB connector status
- Ensure bucket "metrics" exists

### Issue: High consumer lag

**Check lag:**
```bash
docker exec caduceus-kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group monitoring-service-consumer \
  --describe
```

**Solutions:**
- Increase consumer parallelism
- Optimize consumer processing
- Scale Kafka partitions

## Performance Tuning

### Kafka Broker

```yaml
# docker-compose.yml environment
KAFKA_LOG_SEGMENT_BYTES: 1073741824  # 1GB
KAFKA_LOG_RETENTION_HOURS: 168       # 7 days
KAFKA_COMPRESSION_TYPE: gzip
```

### Kafka Connect

```json
{
  "batch.size": "1000",
  "linger.ms": "1000",
  "buffer.memory": "33554432"
}
```

### Metrics Collector

```bash
# .env configuration
METRICS_COLLECTION_INTERVAL=5  # seconds
METRICS_BATCH_SIZE=100
METRICS_BUFFER_SIZE=1000
```

## Security

### Enable SASL/SSL (Production)

1. Generate certificates
2. Configure SASL authentication
3. Update broker and client configs

See: `docs/KAFKA_SECURITY.md` (to be created)

## Backup & Recovery

### Backup Kafka Topics

```bash
# Export topic to file
docker exec caduceus-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic metrics.raw \
  --from-beginning \
  --max-messages 100000 > metrics_backup.json
```

### Restore Kafka Topics

```bash
# Import from file
cat metrics_backup.json | docker exec -i caduceus-kafka \
  kafka-console-producer \
  --bootstrap-server localhost:9092 \
  --topic metrics.raw
```

## Useful Commands

```bash
# List all topics
docker exec caduceus-kafka kafka-topics --bootstrap-server localhost:9092 --list

# Describe topic
docker exec caduceus-kafka kafka-topics --bootstrap-server localhost:9092 --describe --topic metrics.raw

# Delete topic
docker exec caduceus-kafka kafka-topics --bootstrap-server localhost:9092 --delete --topic metrics.raw

# Consume messages
docker exec caduceus-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic metrics.raw \
  --from-beginning

# Produce test message
echo '{"device":"test","metrics":{"cpu":50}}' | \
  docker exec -i caduceus-kafka kafka-console-producer \
  --bootstrap-server localhost:9092 \
  --topic metrics.raw

# Check connector plugins
curl http://localhost:8083/connector-plugins | jq

# Get connector config
curl http://localhost:8083/connectors/jdbc-sink-metrics/config | jq

# Pause connector
curl -X PUT http://localhost:8083/connectors/jdbc-sink-metrics/pause

# Resume connector
curl -X PUT http://localhost:8083/connectors/jdbc-sink-metrics/resume
```

## Next Steps

- [Metrics Pipeline Guide](METRICS_PIPELINE.md) - Understand the full data flow
- [Grafana Dashboards](infrastructure/grafana/README.md) - Visualize metrics
- [ML Training](docs/ML_TRAINING.md) - Use historical data for machine learning

## Support

For issues, questions, or contributions:
- GitHub Issues: https://github.com/your-org/caduceus-flux/issues
- Documentation: https://docs.caduceus-flux.io
