"""
Kafka Consumer Handler for Monitoring Service
Consumes metrics from Kafka and writes to InfluxDB/Prometheus
"""

import logging
import os
import sys
from typing import Dict, Any, Optional
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from shared.messaging.kafka_consumer import create_metrics_consumer
from influxdb_client import Point

logger = logging.getLogger(__name__)


class MetricsKafkaConsumer:
    """
    Consumes metrics from Kafka and processes them
    """

    def __init__(self, influxdb_write_api, bucket_manager, prometheus_metrics):
        """
        Initialize Kafka metrics consumer

        Args:
            influxdb_write_api: InfluxDB write API instance
            bucket_manager: Provides topology-scoped bucket names (falls back to default bucket)
            prometheus_metrics: Dict of Prometheus metrics gauges
        """
        self.influxdb_write_api = influxdb_write_api
        self.bucket_manager = bucket_manager
        self.prometheus_metrics = prometheus_metrics
        self.consumer = None
        self.metrics_processed = 0
        self.errors = 0

    def start(self):
        """Start consuming metrics from Kafka"""
        try:
            if self.consumer and getattr(self.consumer, "running", False):
                logger.info("Kafka metrics consumer already running")
                return

            if self.consumer:
                try:
                    self.consumer.disconnect()
                except Exception:
                    pass
                self.consumer = None

            # Create Kafka consumer
            self.consumer = create_metrics_consumer(
                group_id="monitoring-service-consumer",
                callback=self.process_metrics
            )

            logger.info("Starting Kafka metrics consumer...")
            self.consumer.start_consuming(blocking=False)
            logger.info("Kafka metrics consumer started in background")

        except Exception as e:
            logger.error(f"Failed to start Kafka consumer: {e}")
            raise

    def stop(self):
        """Stop consuming metrics"""
        if self.consumer:
            self.consumer.disconnect()
            logger.info("Kafka metrics consumer stopped")

    def process_metrics(self, message: Dict[str, Any]):
        """
        Process a metrics message from Kafka

        Args:
            message: Metrics message from Kafka
        """
        try:
            topology_id = message.get("topology_id")
            emulation_id = message.get("emulation_id")

            metrics = message.get("metrics") if isinstance(message.get("metrics"), dict) else {}
            features = message.get("features") if isinstance(message.get("features"), dict) else {}
            device = message.get("device") or metrics.get("device")
            timestamp_str = message.get("timestamp") or metrics.get("timestamp")

            if not device or not metrics:
                logger.warning(f"Invalid metrics message: {message}")
                return

            # Parse timestamp
            try:
                if isinstance(timestamp_str, str):
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                elif isinstance(timestamp_str, (int, float)):
                    timestamp = datetime.fromtimestamp(timestamp_str / 1000.0)
                else:
                    timestamp = datetime.utcnow()
            except Exception:
                timestamp = datetime.utcnow()

            bucket = self._resolve_bucket(topology_id)

            # Write to InfluxDB
            source = message.get("source") or metrics.get("source") or "kafka"
            self._write_to_influxdb(bucket, device, topology_id, emulation_id, source, metrics, features, timestamp)

            # Update Prometheus metrics
            self._update_prometheus(device, metrics)

            self.metrics_processed += 1

            if self.metrics_processed % 100 == 0:
                logger.info(f"Processed {self.metrics_processed} metrics from Kafka")

        except Exception as e:
            logger.error(f"Error processing metrics message: {e}")
            self.errors += 1

    def _resolve_bucket(self, topology_id: Optional[str]) -> str:
        try:
            if self.bucket_manager:
                return str(self.bucket_manager.bucket_for_topology(topology_id))
        except Exception as e:
            logger.warning("Failed to resolve InfluxDB bucket for topology %s: %s", topology_id, e)
        return str(getattr(self.bucket_manager, "default_bucket", "metrics"))

    def _write_to_influxdb(
        self,
        bucket: str,
        device: str,
        topology_id: Optional[str],
        emulation_id: Optional[str],
        source: str,
        metrics: Dict[str, Any],
        features: Dict[str, Any],
        timestamp: datetime,
    ):
        """Write metrics to InfluxDB"""
        try:
            # Create InfluxDB point
            point = Point("network_metrics") \
                .tag("device", device) \
                .tag("source", str(source)) \
                .time(timestamp)

            if topology_id:
                point.tag("topology_id", str(topology_id))
            if emulation_id:
                point.tag("emulation_id", str(emulation_id))

            # Add fields
            if "bytes_sent" in metrics:
                point.field("bytes_sent", int(metrics["bytes_sent"]))
            if "bytes_received" in metrics:
                point.field("bytes_received", int(metrics["bytes_received"]))
            if "packets_sent" in metrics:
                point.field("packets_sent", int(metrics["packets_sent"]))
            if "packets_received" in metrics:
                point.field("packets_received", int(metrics["packets_received"]))
            if "errors_in" in metrics:
                point.field("errors_in", int(metrics["errors_in"]))
            if "errors_out" in metrics:
                point.field("errors_out", int(metrics["errors_out"]))
            if "drops_in" in metrics:
                point.field("drops_in", int(metrics["drops_in"]))
            if "drops_out" in metrics:
                point.field("drops_out", int(metrics["drops_out"]))
            if "cpu_percent" in metrics:
                point.field("cpu_percent", float(metrics["cpu_percent"]))
            if "memory_percent" in metrics:
                point.field("memory_percent", float(metrics["memory_percent"]))

            # Processed stream features (best-effort)
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
                        # ignore non-numeric values
                        continue
                except Exception:
                    continue

            # Write to InfluxDB
            self.influxdb_write_api.write(bucket=bucket, record=point)

        except Exception as e:
            logger.error(f"Error writing to InfluxDB: {e}")

    def _update_prometheus(self, device: str, metrics: Dict[str, Any]):
        """Update Prometheus metrics"""
        try:
            # Update Prometheus gauges
            if "bytes_sent" in metrics and "device_tx_bytes" in self.prometheus_metrics:
                self.prometheus_metrics["device_tx_bytes"].labels(
                    device=device, interface="aggregate"
                ).set(metrics["bytes_sent"])

            if "bytes_received" in metrics and "device_rx_bytes" in self.prometheus_metrics:
                self.prometheus_metrics["device_rx_bytes"].labels(
                    device=device, interface="aggregate"
                ).set(metrics["bytes_received"])

            if "packets_sent" in metrics and "device_tx_packets" in self.prometheus_metrics:
                self.prometheus_metrics["device_tx_packets"].labels(
                    device=device, interface="aggregate"
                ).set(metrics["packets_sent"])

            if "packets_received" in metrics and "device_rx_packets" in self.prometheus_metrics:
                self.prometheus_metrics["device_rx_packets"].labels(
                    device=device, interface="aggregate"
                ).set(metrics["packets_received"])

            if "cpu_percent" in metrics and "device_cpu_percent" in self.prometheus_metrics:
                self.prometheus_metrics["device_cpu_percent"].labels(
                    device=device
                ).set(metrics["cpu_percent"])

            if "memory_percent" in metrics and "device_memory_mb" in self.prometheus_metrics:
                # Convert percent to MB (assuming max 16GB)
                memory_mb = metrics["memory_percent"] * 16000 / 100
                self.prometheus_metrics["device_memory_mb"].labels(
                    device=device
                ).set(memory_mb)

        except Exception as e:
            logger.error(f"Error updating Prometheus metrics: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get consumer statistics"""
        stats = {
            "metrics_processed": self.metrics_processed,
            "errors": self.errors,
            "consumer_running": self.consumer is not None and self.consumer.running
        }

        if self.consumer:
            stats.update(self.consumer.get_stats())

        return stats
