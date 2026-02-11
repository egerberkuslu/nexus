"""
Consul client for service discovery and configuration
"""

import consul
import logging
import os
import socket

logger = logging.getLogger(__name__)


class ConsulClient:
    """Client for interacting with Consul"""

    def __init__(self):
        self.host = os.getenv("CONSUL_HOST", "localhost")
        self.port = int(os.getenv("CONSUL_PORT", "8500"))
        self.scheme = os.getenv("CONSUL_SCHEME", "http")
        self.client = consul.Consul(
            host=self.host,
            port=self.port,
            scheme=self.scheme,
        )

    def register_service(self, service_name: str, service_port: int, tags: list = None):
        """Register a service with Consul"""
        try:
            # Get hostname/IP
            hostname = socket.gethostname()
            service_id = f"{service_name}-{hostname}"

            # Register service
            self.client.agent.service.register(
                name=service_name,
                service_id=service_id,
                address=hostname,
                port=service_port,
                tags=tags or [],
                check=consul.Check.http(
                    f"{self.scheme}://{hostname}:{service_port}/health",
                    interval="10s",
                    timeout="5s"
                )
            )
            logger.info(f"Registered service {service_name} with Consul at {hostname}:{service_port}")
        except Exception as e:
            logger.error(f"Failed to register service with Consul: {e}")
            raise

    def deregister_service(self, service_name: str):
        """Deregister a service from Consul"""
        try:
            hostname = socket.gethostname()
            service_id = f"{service_name}-{hostname}"
            self.client.agent.service.deregister(service_id)
            logger.info(f"Deregistered service {service_name} from Consul")
        except Exception as e:
            logger.error(f"Failed to deregister service from Consul: {e}")

    def discover_service(self, service_name: str):
        """Discover a service from Consul"""
        try:
            index, services = self.client.health.service(service_name, passing=True)
            if services:
                # Return first healthy service
                service = services[0]
                return {
                    'address': service['Service']['Address'],
                    'port': service['Service']['Port']
                }
            return None
        except Exception as e:
            logger.error(f"Failed to discover service from Consul: {e}")
            return None

    def get_config(self, key: str):
        """Get configuration value from Consul KV store"""
        try:
            index, data = self.client.kv.get(key)
            if data:
                return data['Value'].decode('utf-8')
            return None
        except Exception as e:
            logger.error(f"Failed to get config from Consul: {e}")
            return None

    def set_config(self, key: str, value: str):
        """Set configuration value in Consul KV store"""
        try:
            self.client.kv.put(key, value)
            logger.info(f"Set config in Consul: {key}")
        except Exception as e:
            logger.error(f"Failed to set config in Consul: {e}")
            raise
