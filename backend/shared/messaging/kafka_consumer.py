"""
Kafka Consumer for receiving metrics and events
"""

import json
import logging
import os
from typing import Dict, Any, Optional, List, Callable
from kafka import KafkaConsumer
from kafka.errors import KafkaError
import threading

logger = logging.getLogger(__name__)


class CaduceusKafkaConsumer:
    """
    Kafka consumer for Caduceus-Flux system
    Handles consuming metrics and events from Kafka topics
    """

    def __init__(
        self,
        group_id: str,
        topics: Optional[List[str]] = None,
        bootstrap_servers: Optional[str] = None,
        auto_offset_reset: str = "latest",
        enable_auto_commit: bool = True
    ):
        """
        Initialize Kafka consumer

        Args:
            group_id: Consumer group ID
            topics: List of topics to subscribe to
            bootstrap_servers: Kafka broker addresses
            auto_offset_reset: Where to start reading (earliest, latest)
            enable_auto_commit: Auto-commit offsets
        """
        self.group_id = group_id
        self.topics = topics or []
        self.bootstrap_servers = bootstrap_servers or os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"
        )
        self.auto_offset_reset = auto_offset_reset
        self.enable_auto_commit = enable_auto_commit
        self.consumer = None
        self.callbacks: Dict[str, List[Callable]] = {}
        self.running = False
        self.consumer_thread = None
        self.messages_consumed = 0
        self.errors = 0

    def connect(self):
        """Establish connection to Kafka broker"""
        try:
            self.consumer = KafkaConsumer(
                *self.topics,
                bootstrap_servers=self.bootstrap_servers.split(','),
                group_id=self.group_id,
                auto_offset_reset=self.auto_offset_reset,
                enable_auto_commit=self.enable_auto_commit,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda k: k.decode('utf-8') if k else None,
                api_version_auto_timeout_ms=20000,
                consumer_timeout_ms=1000,  # Timeout for iteration
                max_poll_records=500,
                max_poll_interval_ms=300000,
                session_timeout_ms=10000,
                heartbeat_interval_ms=3000
            )
            logger.info(
                f"Connected to Kafka broker at {self.bootstrap_servers}, "
                f"subscribed to topics: {self.topics}"
            )
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {e}")
            raise

    def disconnect(self):
        """Close Kafka consumer connection"""
        self.running = False
        if self.consumer_thread:
            self.consumer_thread.join(timeout=5)

        if self.consumer:
            self.consumer.close()
            logger.info("Kafka consumer disconnected")

    def subscribe(self, topics: List[str]):
        """
        Subscribe to additional topics

        Args:
            topics: List of topic names
        """
        if not self.consumer:
            self.topics.extend(topics)
        else:
            all_topics = list(set(self.topics + topics))
            self.consumer.subscribe(all_topics)
            self.topics = all_topics
            logger.info(f"Subscribed to topics: {all_topics}")

    def register_callback(self, topic: str, callback: Callable):
        """
        Register a callback for a specific topic

        Args:
            topic: Topic name
            callback: Function to call when message received
                      Signature: callback(message: Dict[str, Any])
        """
        if topic not in self.callbacks:
            self.callbacks[topic] = []

        self.callbacks[topic].append(callback)
        logger.info(f"Registered callback for topic: {topic}")

    def start_consuming(self, blocking: bool = False):
        """
        Start consuming messages from Kafka

        Args:
            blocking: If True, blocks until stopped. If False, runs in background thread
        """
        if not self.consumer:
            self.connect()

        self.running = True

        if blocking:
            self._consume_loop()
        else:
            self.consumer_thread = threading.Thread(
                target=self._consume_loop,
                daemon=True
            )
            self.consumer_thread.start()
            logger.info("Started consuming messages in background thread")

    def _consume_loop(self):
        """Main consumption loop"""
        logger.info("Starting message consumption loop")

        while self.running:
            try:
                # Poll for messages
                for message in self.consumer:
                    if not self.running:
                        break

                    try:
                        # Process message
                        self._process_message(message)
                        self.messages_consumed += 1

                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        self.errors += 1

            except KafkaError as e:
                logger.error(f"Kafka error: {e}")
                self.errors += 1
            except Exception as e:
                logger.error(f"Unexpected error in consume loop: {e}")
                self.errors += 1

        logger.info("Consumption loop stopped")

    def _process_message(self, message):
        """
        Process a consumed message

        Args:
            message: Kafka message
        """
        topic = message.topic
        value = message.value
        key = message.key

        logger.debug(
            f"Consumed message from {topic}:{message.partition}:"
            f"{message.offset}, key: {key}"
        )

        # Call registered callbacks for this topic
        if topic in self.callbacks:
            for callback in self.callbacks[topic]:
                try:
                    callback(value)
                except Exception as e:
                    logger.error(f"Error in callback for {topic}: {e}")

    def consume_one(self, timeout_ms: int = 1000) -> Optional[Dict[str, Any]]:
        """
        Consume a single message (blocking)

        Args:
            timeout_ms: Timeout in milliseconds

        Returns:
            Message value or None
        """
        if not self.consumer:
            self.connect()

        try:
            message = next(self.consumer)
            self.messages_consumed += 1
            return message.value
        except StopIteration:
            return None
        except Exception as e:
            logger.error(f"Error consuming message: {e}")
            self.errors += 1
            return None

    def consume_batch(self, max_messages: int = 100, timeout_ms: int = 5000) -> List[Dict[str, Any]]:
        """
        Consume a batch of messages

        Args:
            max_messages: Maximum number of messages to consume
            timeout_ms: Timeout in milliseconds

        Returns:
            List of message values
        """
        if not self.consumer:
            self.connect()

        messages = []
        try:
            records = self.consumer.poll(timeout_ms=timeout_ms, max_records=max_messages)

            for topic_partition, records_list in records.items():
                for record in records_list:
                    messages.append(record.value)
                    self.messages_consumed += 1

        except Exception as e:
            logger.error(f"Error consuming batch: {e}")
            self.errors += 1

        return messages

    def commit(self):
        """Manually commit offsets"""
        if self.consumer:
            try:
                self.consumer.commit()
                logger.debug("Committed offsets")
            except Exception as e:
                logger.error(f"Error committing offsets: {e}")

    def seek_to_beginning(self):
        """Seek to beginning of all assigned partitions"""
        if self.consumer:
            self.consumer.seek_to_beginning()
            logger.info("Seeked to beginning of partitions")

    def seek_to_end(self):
        """Seek to end of all assigned partitions"""
        if self.consumer:
            self.consumer.seek_to_end()
            logger.info("Seeked to end of partitions")

    def get_stats(self) -> Dict[str, Any]:
        """Get consumer statistics"""
        return {
            "messages_consumed": self.messages_consumed,
            "errors": self.errors,
            "running": self.running,
            "connected": self.consumer is not None,
            "topics": self.topics,
            "group_id": self.group_id,
            "bootstrap_servers": self.bootstrap_servers
        }


# Convenience function for metrics consumption
def create_metrics_consumer(
    group_id: str = "caduceus-metrics-consumer",
    callback: Optional[Callable] = None,
    topics: Optional[List[str]] = None,
) -> CaduceusKafkaConsumer:
    """
    Create a consumer for metrics topic

    Args:
        group_id: Consumer group ID
        callback: Callback function for metrics

    Returns:
        Configured Kafka consumer
    """
    if topics:
        metrics_topics = topics
    else:
        raw = os.getenv("KAFKA_METRICS_TOPICS") or os.getenv("KAFKA_METRICS_TOPIC") or "metrics.raw"
        metrics_topics = [t.strip() for t in str(raw).split(",") if t.strip()]
        if not metrics_topics:
            metrics_topics = ["metrics.raw"]

    consumer = CaduceusKafkaConsumer(
        group_id=group_id,
        topics=metrics_topics,
        auto_offset_reset="earliest"
    )

    if callback:
        for t in metrics_topics:
            consumer.register_callback(t, callback)

    return consumer


# Convenience function for events consumption
def create_events_consumer(
    group_id: str = "caduceus-events-consumer",
    callback: Optional[Callable] = None
) -> CaduceusKafkaConsumer:
    """
    Create a consumer for events topic

    Args:
        group_id: Consumer group ID
        callback: Callback function for events

    Returns:
        Configured Kafka consumer
    """
    events_topic = os.getenv("KAFKA_EVENTS_TOPIC", "events")

    consumer = CaduceusKafkaConsumer(
        group_id=group_id,
        topics=[events_topic],
        auto_offset_reset="latest"
    )

    if callback:
        consumer.register_callback(events_topic, callback)

    return consumer
