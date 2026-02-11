"""
Protocol Manager Service - Port 8003
Manages protocol configurations, switching, and plugin system
"""

import logging
import importlib
import os
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.plugins.protocol_plugin import (
    ProtocolPlugin, ProtocolType, ProtocolStatus,
    plugin_registry
)
from shared.messaging.rabbitmq import RabbitMQPublisher
from shared.utils.consul_client import ConsulClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Caduceus-Flux Protocol Manager Service",
    description="Manages protocols with hot-swapping capability",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

consul_client = ConsulClient()
rabbitmq_publisher = RabbitMQPublisher()


# Pydantic models
class ProtocolConfigureRequest(BaseModel):
    device: str
    protocol: str
    config: Dict[str, Any]


class ProtocolEnableRequest(BaseModel):
    device: str
    protocol: str


class ProtocolSwitchRequest(BaseModel):
    device: str
    from_protocol: str
    to_protocol: str
    preserve_config: bool = True


class ProtocolListResponse(BaseModel):
    protocols: List[Dict[str, Any]]


class ProtocolInfoResponse(BaseModel):
    name: str
    version: str
    protocol_type: str
    description: str
    supported_devices: List[str]
    config_schema: Dict[str, Any]


def load_plugins():
    """Load all protocol plugins from plugins directory"""
    plugins_dir = Path(__file__).resolve().parent.parent / "plugins"

    if not plugins_dir.exists():
        logger.warning(f"Plugins directory not found: {plugins_dir}")
        return

    for plugin_file in plugins_dir.glob("*_plugin.py"):
        try:
            module_name = plugin_file.stem
            spec = importlib.util.spec_from_file_location(module_name, plugin_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find plugin classes
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                        issubclass(attr, ProtocolPlugin) and
                        attr is not ProtocolPlugin and
                        hasattr(attr, 'name') and attr.name):

                    # Instantiate and register plugin
                    plugin_instance = attr()
                    plugin_registry.register(plugin_instance)
                    logger.info(f"Loaded plugin: {plugin_instance.name} v{plugin_instance.version}")

        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_file}: {e}")


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    logger.info("Starting Protocol Manager Service...")

    # Load protocol plugins
    load_plugins()

    # Register with Consul
    consul_client.register_service("protocol-manager-service", 8003)

    # Connect to RabbitMQ
    rabbitmq_publisher.connect()

    logger.info(f"Protocol Manager Service started with {len(plugin_registry.list_plugins())} plugins")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Protocol Manager Service...")
    consul_client.deregister_service("protocol-manager-service")
    rabbitmq_publisher.disconnect()


# ==================== Plugin Management Endpoints ====================

@app.get("/api/protocols", response_model=ProtocolListResponse)
async def list_protocols(protocol_type: Optional[str] = None):
    """List all available protocol plugins"""
    try:
        if protocol_type:
            protocol_names = plugin_registry.list_plugins(ProtocolType(protocol_type))
        else:
            protocol_names = plugin_registry.list_plugins()

        protocols = []
        for name in protocol_names:
            plugin = plugin_registry.get(name)
            if plugin:
                protocols.append({
                    'name': plugin.name,
                    'version': plugin.version,
                    'protocol_type': plugin.protocol_type.value,
                    'description': plugin.description,
                    'supported_devices': plugin.supported_devices
                })

        return ProtocolListResponse(protocols=protocols)

    except Exception as e:
        logger.error(f"Failed to list protocols: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/protocols/{protocol_name}", response_model=ProtocolInfoResponse)
async def get_protocol_info(protocol_name: str):
    """Get detailed information about a protocol"""
    try:
        plugin = plugin_registry.get(protocol_name)

        if not plugin:
            raise HTTPException(status_code=404, detail=f"Protocol {protocol_name} not found")

        return ProtocolInfoResponse(
            name=plugin.name,
            version=plugin.version,
            protocol_type=plugin.protocol_type.value,
            description=plugin.description,
            supported_devices=plugin.supported_devices,
            config_schema=plugin.get_config_schema()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get protocol info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/protocols/{protocol_name}/default-config")
async def get_default_config(protocol_name: str):
    """Get default configuration for a protocol"""
    try:
        plugin = plugin_registry.get(protocol_name)

        if not plugin:
            raise HTTPException(status_code=404, detail=f"Protocol {protocol_name} not found")

        return {
            'protocol': protocol_name,
            'default_config': plugin.get_default_config()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get default config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/devices/{device_type}/protocols")
async def get_protocols_for_device(device_type: str):
    """Get protocols that support a specific device type"""
    try:
        protocol_names = plugin_registry.get_plugins_for_device(device_type)

        protocols = []
        for name in protocol_names:
            plugin = plugin_registry.get(name)
            if plugin:
                protocols.append({
                    'name': plugin.name,
                    'version': plugin.version,
                    'protocol_type': plugin.protocol_type.value,
                    'description': plugin.description
                })

        return {
            'device_type': device_type,
            'supported_protocols': protocols
        }

    except Exception as e:
        logger.error(f"Failed to get protocols for device: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Protocol Configuration Endpoints ====================

@app.post("/api/protocols/configure")
async def configure_protocol(request: ProtocolConfigureRequest):
    """Configure a protocol on a device"""
    try:
        plugin = plugin_registry.get(request.protocol)

        if not plugin:
            raise HTTPException(status_code=404, detail=f"Protocol {request.protocol} not found")

        logger.info(f"Configuring {request.protocol} on {request.device}")

        result = plugin.configure(request.device, request.config)

        if result['success']:
            # Publish event
            rabbitmq_publisher.publish("protocol.configured", {
                'device': request.device,
                'protocol': request.protocol,
                'config': request.config
            })

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to configure protocol: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/protocols/enable")
async def enable_protocol(request: ProtocolEnableRequest):
    """Enable a protocol on a device"""
    try:
        plugin = plugin_registry.get(request.protocol)

        if not plugin:
            raise HTTPException(status_code=404, detail=f"Protocol {request.protocol} not found")

        logger.info(f"Enabling {request.protocol} on {request.device}")

        result = plugin.enable(request.device)

        if result['success']:
            # Publish event
            rabbitmq_publisher.publish("protocol.enabled", {
                'device': request.device,
                'protocol': request.protocol
            })

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to enable protocol: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/protocols/disable")
async def disable_protocol(request: ProtocolEnableRequest):
    """Disable a protocol on a device"""
    try:
        plugin = plugin_registry.get(request.protocol)

        if not plugin:
            raise HTTPException(status_code=404, detail=f"Protocol {request.protocol} not found")

        logger.info(f"Disabling {request.protocol} on {request.device}")

        result = plugin.disable(request.device)

        if result['success']:
            # Publish event
            rabbitmq_publisher.publish("protocol.disabled", {
                'device': request.device,
                'protocol': request.protocol
            })

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disable protocol: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/protocols/status/{device}/{protocol}")
async def get_protocol_status(device: str, protocol: str):
    """Get protocol status on a device"""
    try:
        plugin = plugin_registry.get(protocol)

        if not plugin:
            raise HTTPException(status_code=404, detail=f"Protocol {protocol} not found")

        status = plugin.get_status(device)

        return {
            'device': device,
            'protocol': protocol,
            **status
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get protocol status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Protocol Switching (Hot-Swap) ====================

@app.post("/api/protocols/switch")
async def switch_protocol(request: ProtocolSwitchRequest):
    """
    Switch from one protocol to another without restart

    This is the KEY FEATURE - hot protocol switching
    """
    try:
        # Get both plugins
        from_plugin = plugin_registry.get(request.from_protocol)
        to_plugin = plugin_registry.get(request.to_protocol)

        if not from_plugin:
            raise HTTPException(
                status_code=404,
                detail=f"Source protocol {request.from_protocol} not found"
            )

        if not to_plugin:
            raise HTTPException(
                status_code=404,
                detail=f"Target protocol {request.to_protocol} not found"
            )

        logger.info(
            f"Switching protocol on {request.device}: "
            f"{request.from_protocol} -> {request.to_protocol}"
        )

        # Publish switching started event
        rabbitmq_publisher.publish("protocol.switching.started", {
            'device': request.device,
            'from_protocol': request.from_protocol,
            'to_protocol': request.to_protocol
        })

        # Step 1: Switch from source protocol
        switch_from_result = from_plugin.switch_from(
            request.device,
            request.to_protocol,
            request.preserve_config
        )

        if not switch_from_result['success']:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to switch from {request.from_protocol}: {switch_from_result['message']}"
            )

        preserved_state = switch_from_result.get('preserved_state', {})

        # Step 2: Switch to target protocol
        switch_to_result = to_plugin.switch_to(
            request.device,
            request.from_protocol,
            preserved_state if request.preserve_config else None
        )

        if not switch_to_result['success']:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to switch to {request.to_protocol}: {switch_to_result['message']}"
            )

        # Publish switching completed event
        rabbitmq_publisher.publish("protocol.switching.completed", {
            'device': request.device,
            'from_protocol': request.from_protocol,
            'to_protocol': request.to_protocol,
            'preserved_config': request.preserve_config
        })

        logger.info(
            f"Successfully switched protocol on {request.device}: "
            f"{request.from_protocol} -> {request.to_protocol}"
        )

        return {
            'success': True,
            'message': f"Successfully switched from {request.from_protocol} to {request.to_protocol}",
            'device': request.device,
            'from_protocol': request.from_protocol,
            'to_protocol': request.to_protocol,
            'preserved_state': preserved_state if request.preserve_config else None,
            'status': switch_to_result.get('status', ProtocolStatus.ENABLED)
        }

    except HTTPException:
        # Publish switching failed event
        rabbitmq_publisher.publish("protocol.switching.failed", {
            'device': request.device,
            'from_protocol': request.from_protocol,
            'to_protocol': request.to_protocol
        })
        raise
    except Exception as e:
        logger.error(f"Failed to switch protocol: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Configuration Validation ====================

@app.post("/api/protocols/validate")
async def validate_config(protocol: str, config: Dict[str, Any]):
    """Validate protocol configuration without applying it"""
    try:
        plugin = plugin_registry.get(protocol)

        if not plugin:
            raise HTTPException(status_code=404, detail=f"Protocol {protocol} not found")

        validation_result = plugin.validate_config(config)

        return {
            'protocol': protocol,
            'config': config,
            **validation_result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to validate config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Health Check ====================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "protocol-manager-service",
        "loaded_plugins": len(plugin_registry.list_plugins()),
        "plugins": plugin_registry.list_plugins()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
