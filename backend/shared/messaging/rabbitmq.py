"""
RabbitMQ message broker integration for inter-service communication
"""

import pika
import json
import logging
import os
import time
from typing import Callable, Dict, Any

logger = logging.getLogger(__name__)


class RabbitMQPublisher:
    """Publisher for sending messages to RabbitMQ"""

    def __init__(self):
        self.host = os.getenv("RABBITMQ_HOST", "localhost")
        self.port = int(os.getenv("RABBITMQ_PORT", "5672"))
        self.user = os.getenv("RABBITMQ_USER", "caduceus")
        self.password = os.getenv("RABBITMQ_PASSWORD", "changeme")
        self.vhost = os.getenv("RABBITMQ_VHOST", "/caduceus-flux")
        self.connection = None
        self.channel = None

    def connect(self):
        """Establish connection to RabbitMQ"""
        retries = int(os.getenv("RABBITMQ_CONNECT_RETRIES", "30") or "30")
        delay_seconds = float(os.getenv("RABBITMQ_CONNECT_DELAY_SECONDS", "1") or "1")

        for attempt in range(1, max(retries, 1) + 1):
            try:
                credentials = pika.PlainCredentials(self.user, self.password)
                parameters = pika.ConnectionParameters(
                    host=self.host,
                    port=self.port,
                    virtual_host=self.vhost,
                    credentials=credentials,
                    heartbeat=600,
                    blocked_connection_timeout=300,
                )
                self.connection = pika.BlockingConnection(parameters)
                self.channel = self.connection.channel()
                logger.info("Connected to RabbitMQ")
                return True
            except Exception as e:
                self.connection = None
                self.channel = None
                if attempt >= retries:
                    logger.warning("RabbitMQ unavailable (giving up after %s attempts): %s", attempt, e)
                    return False
                logger.warning("RabbitMQ connect failed (attempt %s/%s): %s", attempt, retries, e)
                time.sleep(max(delay_seconds, 0.1))

    def disconnect(self):
        """Close connection to RabbitMQ"""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logger.info("Disconnected from RabbitMQ")

    def publish(self, routing_key: str, message: Dict[str, Any], exchange: str = "caduceus-flux"):
        """Publish a message to RabbitMQ"""
        if not self.channel:
            if not self.connect():
                logger.warning("Skipping publish to %s (RabbitMQ unavailable)", routing_key)
                return False

        try:
            # Declare exchange
            self.channel.exchange_declare(
                exchange=exchange,
                exchange_type='topic',
                durable=True
            )

            # Publish message
            self.channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                    content_type='application/json'
                )
            )
            logger.debug(f"Published message to {routing_key}: {message}")
            return True
        except Exception as e:
            logger.error("Failed to publish message to %s: %s", routing_key, e)
            # Try to reconnect once; if it still fails, drop the message (don't crash the API).
            self.connect()
            try:
                if not self.channel:
                    return False
                self.channel.basic_publish(
                    exchange=exchange,
                    routing_key=routing_key,
                    body=json.dumps(message),
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                        content_type='application/json',
                    ),
                )
                return True
            except Exception as e2:
                logger.error("Failed to publish message after reconnect to %s: %s", routing_key, e2)
                return False


class RabbitMQConsumer:
    """Consumer for receiving messages from RabbitMQ"""

    def __init__(self, queue_name: str):
        self.host = os.getenv("RABBITMQ_HOST", "localhost")
        self.port = int(os.getenv("RABBITMQ_PORT", "5672"))
        self.user = os.getenv("RABBITMQ_USER", "caduceus")
        self.password = os.getenv("RABBITMQ_PASSWORD", "changeme")
        self.vhost = os.getenv("RABBITMQ_VHOST", "/caduceus-flux")
        self.queue_name = queue_name
        self.connection = None
        self.channel = None
        self.callbacks = {}

    def connect(self):
        """Establish connection to RabbitMQ"""
        retries = int(os.getenv("RABBITMQ_CONNECT_RETRIES", "30") or "30")
        delay_seconds = float(os.getenv("RABBITMQ_CONNECT_DELAY_SECONDS", "1") or "1")

        for attempt in range(1, max(retries, 1) + 1):
            try:
                credentials = pika.PlainCredentials(self.user, self.password)
                parameters = pika.ConnectionParameters(
                    host=self.host,
                    port=self.port,
                    virtual_host=self.vhost,
                    credentials=credentials,
                    heartbeat=600,
                    blocked_connection_timeout=300,
                )
                self.connection = pika.BlockingConnection(parameters)
                self.channel = self.connection.channel()
                self.channel.queue_declare(queue=self.queue_name, durable=True)
                logger.info("Connected to RabbitMQ, listening on queue: %s", self.queue_name)
                return True
            except Exception as e:
                self.connection = None
                self.channel = None
                if attempt >= retries:
                    logger.warning(
                        "RabbitMQ unavailable for consumer %s (giving up after %s attempts): %s",
                        self.queue_name,
                        attempt,
                        e,
                    )
                    return False
                logger.warning(
                    "RabbitMQ connect failed for consumer %s (attempt %s/%s): %s",
                    self.queue_name,
                    attempt,
                    retries,
                    e,
                )
                time.sleep(max(delay_seconds, 0.1))

    def disconnect(self):
        """Close connection to RabbitMQ"""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logger.info("Disconnected from RabbitMQ")

    def bind_routing_key(self, routing_key: str, exchange: str = "caduceus-flux"):
        """Bind queue to routing key"""
        if not self.channel:
            if not self.connect():
                logger.warning("Skipping bind for %s (RabbitMQ unavailable)", routing_key)
                return False

        try:
            # Declare exchange
            self.channel.exchange_declare(
                exchange=exchange,
                exchange_type='topic',
                durable=True
            )

            # Bind queue to routing key
            self.channel.queue_bind(
                exchange=exchange,
                queue=self.queue_name,
                routing_key=routing_key
            )
            logger.info(f"Bound queue {self.queue_name} to routing key: {routing_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to bind routing key: {e}")
            return False

    def register_callback(self, routing_key: str, callback: Callable):
        """Register a callback for a specific routing key"""
        self.callbacks[routing_key] = callback
        logger.info(f"Registered callback for routing key: {routing_key}")

    def start_consuming(self):
        """Start consuming messages"""
        if not self.channel:
            if not self.connect():
                logger.warning("RabbitMQ unavailable; consumer %s will not start", self.queue_name)
                return

        def callback(ch, method, properties, body):
            try:
                message = json.loads(body)
                routing_key = method.routing_key

                logger.debug(f"Received message from {routing_key}: {message}")

                # Call registered callback if exists
                if routing_key in self.callbacks:
                    self.callbacks[routing_key](message)
                else:
                    logger.warning(f"No callback registered for routing key: {routing_key}")

                # Acknowledge message
                ch.basic_ack(delivery_tag=method.delivery_tag)

            except Exception as e:
                logger.error(f"Error processing message: {e}")
                # Reject message and don't requeue
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue=self.queue_name, on_message_callback=callback)

        logger.info(f"Starting to consume messages from queue: {self.queue_name}")
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.channel.stop_consuming()
            self.disconnect()
