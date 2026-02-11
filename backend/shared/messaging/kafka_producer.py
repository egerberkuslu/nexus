"""
Kafka Producer for streaming metrics and events
"""

import json
import logging
import os
from typing import Dict, Any, Optional, List
from kafka import KafkaProducer
from kafka.errors import KafkaError, KafkaTimeoutError
import time

logger = logging.getLogger(__name__)


class CaduceusKafkaProducer:
    """
    Kafka producer for Caduceus-Flux system
    Handles metrics and event streaming to Kafka topics
    """

    def __init__(
        self,
        bootstrap_servers: Optional[str] = None,
        client_id: str = "caduceus-producer",
        compression_type: str = "gzip",
        max_retries: int = 3
    ):
        """
        Initialize Kafka producer

        Args:
            bootstrap_servers: Kafka broker addresses
            client_id: Producer client ID
            compression_type: Compression algorithm (gzip, snappy, lz4, zstd)
            max_retries: Maximum number of retries for failed sends
        """
        self.bootstrap_servers = bootstrap_servers or os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"
        )
        self.client_id = client_id
        self.compression_type = compression_type
        self.max_retries = max_retries
        self.producer = None
        self.metrics_sent = 0
        self.errors = 0

    def connect(self):
        """Establish connection to Kafka broker"""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers.split(','),
                client_id=self.client_id,
                compression_type=self.compression_type,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks='all',  # Wait for all replicas
                retries=self.max_retries,
                max_in_flight_requests_per_connection=5,
                buffer_memory=33554432,  # 32MB
                batch_size=16384,  # 16KB
                linger_ms=10,  # Small delay for batching
                request_timeout_ms=30000,
                api_version_auto_timeout_ms=20000
            )
            logger.info(f"Connected to Kafka broker at {self.bootstrap_servers}")
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {e}")
            raise

    def disconnect(self):
        """Close Kafka producer connection"""
        if self.producer:
            self.producer.flush()
            self.producer.close()
            logger.info("Kafka producer disconnected")

    def send_message(
        self,
        topic: str,
        message: Dict[str, Any],
        key: Optional[str] = None,
        partition: Optional[int] = None,
        headers: Optional[List[tuple]] = None
    ) -> bool:
        """
        Send a single message to Kafka topic

        Args:
            topic: Kafka topic name
            message: Message payload (dict)
            key: Message key for partitioning
            partition: Specific partition (optional)
            headers: Message headers

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.producer:
            self.connect()

        try:
            # Add timestamp if not present
            if 'timestamp' not in message:
                message['timestamp'] = int(time.time() * 1000)

            # Send message
            future = self.producer.send(
                topic=topic,
                value=message,
                key=key,
                partition=partition,
                headers=headers
            )

            # Wait for acknowledgment (with timeout)
            record_metadata = future.get(timeout=10)

            self.metrics_sent += 1
            logger.debug(
                f"Message sent to {record_metadata.topic}:"
                f"{record_metadata.partition}:{record_metadata.offset}"
            )

            return True

        except KafkaTimeoutError:
            logger.error(f"Timeout sending message to {topic}")
            self.errors += 1
            return False
        except KafkaError as e:
            logger.error(f"Kafka error sending message to {topic}: {e}")
            self.errors += 1
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending message to {topic}: {e}")
            self.errors += 1
            return False

    def send_batch(
        self,
        topic: str,
        messages: List[Dict[str, Any]],
        key_extractor: Optional[callable] = None
    ) -> int:
        """
        Send batch of messages to Kafka topic

        Args:
            topic: Kafka topic name
            messages: List of message payloads
            key_extractor: Function to extract key from message

        Returns:
            Number of messages successfully sent
        """
        if not self.producer:
            self.connect()

        sent_count = 0
        failed_count = 0

        for message in messages:
            try:
                key = key_extractor(message) if key_extractor else None

                # Add timestamp if not present
                if 'timestamp' not in message:
                    message['timestamp'] = int(time.time() * 1000)

                # Send message (async)
                self.producer.send(
                    topic=topic,
                    value=message,
                    key=key
                )
                sent_count += 1

            except Exception as e:
                logger.error(f"Error adding message to batch: {e}")
                failed_count += 1

        # Flush to ensure all messages are sent
        try:
            self.producer.flush(timeout=30)
            self.metrics_sent += sent_count
            logger.info(
                f"Batch sent: {sent_count} messages to {topic}, "
                f"{failed_count} failed"
            )
        except Exception as e:
            logger.error(f"Error flushing batch: {e}")
            self.errors += failed_count

        return sent_count

    def send_metrics(
        self,
        device: str,
        metrics: Dict[str, Any],
        topic: Optional[str] = None
    ) -> bool:
        """
        Send device metrics to Kafka

        Args:
            device: Device name
            metrics: Metrics dictionary
            topic: Kafka topic (defaults to metrics.raw)

        Returns:
            True if sent successfully
        """
        topic = topic or os.getenv("KAFKA_METRICS_TOPIC", "metrics.raw")

        # Prepare metrics message
        message = {
            "device": device,
            "metrics": metrics,
            "timestamp": metrics.get("timestamp", int(time.time() * 1000)),
            "source": "caduceus-metrics-collector"
        }

        return self.send_message(
            topic=topic,
            message=message,
            key=device  # Partition by device for ordering
        )

    def send_event(
        self,
        event_type: str,
        event_data: Dict[str, Any],
        topic: Optional[str] = None
    ) -> bool:
        """
        Send system event to Kafka

        Args:
            event_type: Event type (e.g., 'topology.created')
            event_data: Event data
            topic: Kafka topic (defaults to events)

        Returns:
            True if sent successfully
        """
        topic = topic or os.getenv("KAFKA_EVENTS_TOPIC", "events")

        message = {
            "event_type": event_type,
            "data": event_data,
            "timestamp": int(time.time() * 1000),
            "source": "caduceus-system"
        }

        return self.send_message(
            topic=topic,
            message=message,
            key=event_type
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get producer statistics"""
        return {
            "messages_sent": self.metrics_sent,
            "errors": self.errors,
            "connected": self.producer is not None,
            "bootstrap_servers": self.bootstrap_servers
        }


# Global producer instance
_kafka_producer = None


def get_kafka_producer() -> CaduceusKafkaProducer:
    """Get global Kafka producer instance"""
    global _kafka_producer
    if _kafka_producer is None:
        _kafka_producer = CaduceusKafkaProducer()
        _kafka_producer.connect()
    return _kafka_producer
