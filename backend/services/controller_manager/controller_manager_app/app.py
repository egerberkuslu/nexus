"""
Controller Manager Service (Port 8005)
Manages SDN controller lifecycle (OS-Ken, Ryu, OpenDaylight, ONOS)
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import logging
import subprocess
import docker
from datetime import datetime
import time
from docker.errors import APIError as DockerAPIError, ImageNotFound

# Import shared components
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from shared.messaging.rabbitmq import RabbitMQPublisher
from shared.utils.consul_client import ConsulClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Caduceus-Flux Controller Manager Service",
    description="SDN Controller lifecycle management",
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
docker_client = None

SERVICE_PORT = 8005

# Active controllers registry
active_controllers: Dict[str, Dict] = {}


# Pydantic models
class ControllerCreate(BaseModel):
    name: str = Field(..., description="Controller name/identifier")
    controller_type: str = Field(..., description="Controller type: osken, ryu, opendaylight, onos, custom")
    ip: str = Field(default="127.0.0.1", description="Controller IP address")
    port: int = Field(default=6653, description="OpenFlow port")
    rest_port: Optional[int] = Field(default=8080, description="REST API port")
    config: Dict[str, Any] = Field(default_factory=dict, description="Controller-specific configuration")


class ControllerResponse(BaseModel):
    id: str
    name: str
    controller_type: str
    ip: str
    port: int
    rest_port: Optional[int]
    status: str
    created_at: datetime
    container_id: Optional[str] = None


class ControllerUpdate(BaseModel):
    status: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


# Helper functions
def get_docker_client():
    """Get Docker client"""
    global docker_client
    if docker_client is None:
        docker_client = docker.from_env()
    return docker_client


def publish_event(event_type: str, data: Dict):
    """Publish controller event"""
    try:
        rabbitmq_publisher.publish(
            exchange="caduceus",
            routing_key=f"controller.{event_type}",
            message=data
        )
    except Exception as e:
        logger.error(f"Failed to publish event: {e}")


def start_osken_controller(controller_id: str, name: str, config: Dict) -> str:
    """Start OS-Ken controller in Docker container"""
    try:
        client = get_docker_client()

        # OS-Ken simple switch application
        app = str(config.get("application", "simple_switch_13.py"))
        app_module = app.replace(".py", "").strip()
        ofp_port = config.get("port", 6653)
        rest_port = config.get("rest_port", 8080)

        image_candidates = [
            os.getenv("OSKEN_IMAGE", "caduceus-flux-osken-controller:latest"),
            "caduceus-flux-osken-controller:latest",
            "osken/osken:latest",
        ]
        command = f"sh -lc 'ryu-manager --ofp-tcp-listen-port {ofp_port} ryu.app.{app_module}'"

        container = _run_controller_container(
            client=client,
            controller_id=controller_id,
            image_candidates=image_candidates,
            command=command,
            env={"CONTROLLER_NAME": name},
        )

        logger.info(f"OS-Ken controller started: {container.id[:12]}")
        return container.id

    except Exception as e:
        logger.error(f"Failed to start OS-Ken controller: {e}")
        raise


def start_ryu_controller(controller_id: str, name: str, config: Dict) -> str:
    """Start Ryu controller in Docker container"""
    try:
        client = get_docker_client()

        app = str(config.get("application", "simple_switch_13.py"))
        app_module = app.replace(".py", "").strip()
        ofp_port = config.get("port", 6653)

        image_candidates = [
            os.getenv("RYU_IMAGE", "osrg/ryu:latest"),
            # Local fallback improves reliability when public pulls are throttled/blocked.
            os.getenv("OSKEN_IMAGE", "caduceus-flux-osken-controller:latest"),
            "caduceus-flux-osken-controller:latest",
            "osrg/ryu:latest",
        ]
        command = f"sh -lc 'ryu-manager --ofp-tcp-listen-port {ofp_port} ryu.app.{app_module}'"

        container = _run_controller_container(
            client=client,
            controller_id=controller_id,
            image_candidates=image_candidates,
            command=command,
            env={"CONTROLLER_NAME": name},
        )

        logger.info(f"Ryu controller started: {container.id[:12]}")
        return container.id

    except Exception as e:
        logger.error(f"Failed to start Ryu controller: {e}")
        raise


def start_custom_controller(controller_id: str, name: str, config: Dict) -> str:
    """Start custom controller"""
    try:
        # For custom controllers, just register the connection details
        # The controller is assumed to be running externally
        logger.info(f"Registered custom controller: {name}")
        return f"custom_{controller_id}"

    except Exception as e:
        logger.error(f"Failed to register custom controller: {e}")
        raise


def _run_controller_container(
    *,
    client,
    controller_id: str,
    image_candidates: List[str],
    command: str,
    env: Dict[str, Any],
):
    """
    Start controller container with resilient local-first image fallback.
    """
    unique_images: List[str] = []
    for image in image_candidates:
        image_name = str(image or "").strip()
        if image_name and image_name not in unique_images:
            unique_images.append(image_name)

    last_error: Optional[str] = None
    for image_name in unique_images:
        try:
            container = client.containers.run(
                image_name,
                command=command,
                name=f"controller_{controller_id}",
                detach=True,
                network_mode="host",
                environment=env,
            )
            return container
        except ImageNotFound as exc:
            last_error = f"image not found: {image_name} ({exc})"
            logger.warning("Controller image not found, trying next fallback: %s", image_name)
            continue
        except DockerAPIError as exc:
            msg = str(exc)
            lower = msg.lower()
            # Retry next candidate for pull/image access issues.
            if "pull access denied" in lower or "repository does not exist" in lower or "not found" in lower:
                last_error = f"cannot pull image: {image_name} ({msg})"
                logger.warning("Controller image pull failed, trying next fallback: %s", image_name)
                continue
            raise

    raise RuntimeError(last_error or "No controller image candidate could be started")


# API endpoints

@app.on_event("startup")
async def startup_event():
    """Service startup"""
    logger.info("Starting Controller Manager Service...")
    try:
        # Initialize Docker client
        get_docker_client()

        # Register with Consul
        consul_client.register_service("controller-manager", SERVICE_PORT)
        rabbitmq_publisher.connect()

        logger.info("Controller Manager Service started successfully")
    except Exception as e:
        logger.error(f"Startup error: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Service shutdown"""
    logger.info("Shutting down Controller Manager Service...")

    # Stop all active controllers
    for controller_id, controller_info in list(active_controllers.items()):
        try:
            if controller_info.get("container_id") and not controller_info["container_id"].startswith("custom_"):
                container = get_docker_client().containers.get(controller_info["container_id"])
                container.stop(timeout=10)
                container.remove()
                logger.info(f"Stopped controller: {controller_id}")
        except Exception as e:
            logger.error(f"Error stopping controller {controller_id}: {e}")

    consul_client.deregister_service("controller-manager")
    rabbitmq_publisher.disconnect()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "controller-manager",
        "active_controllers": len(active_controllers),
        "docker_connected": docker_client is not None,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/api/controllers", response_model=ControllerResponse, status_code=201)
async def create_controller(controller: ControllerCreate):
    """
    Create and start a new SDN controller
    Supports: osken, ryu, opendaylight, onos, custom
    """
    try:
        logger.info(f"Creating controller: {controller.name} (type: {controller.controller_type})")

        controller_id = f"{controller.name}_{int(datetime.utcnow().timestamp())}"

        # Start controller based on type
        container_id = None
        config = {
            "port": controller.port,
            "rest_port": controller.rest_port,
            **controller.config
        }

        if controller.controller_type.lower() == "osken":
            container_id = start_osken_controller(controller_id, controller.name, config)
        elif controller.controller_type.lower() == "ryu":
            container_id = start_ryu_controller(controller_id, controller.name, config)
        elif controller.controller_type.lower() in ["opendaylight", "odl"]:
            # OpenDaylight would be started here (typically pre-deployed)
            container_id = start_custom_controller(controller_id, controller.name, config)
        elif controller.controller_type.lower() == "onos":
            # ONOS would be started here (typically pre-deployed)
            container_id = start_custom_controller(controller_id, controller.name, config)
        elif controller.controller_type.lower() == "custom":
            container_id = start_custom_controller(controller_id, controller.name, config)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported controller type: {controller.controller_type}"
            )

        # Store controller info
        controller_data = {
            "id": controller_id,
            "name": controller.name,
            "controller_type": controller.controller_type,
            "ip": controller.ip,
            "port": controller.port,
            "rest_port": controller.rest_port,
            "status": "running",
            "created_at": datetime.utcnow(),
            "container_id": container_id,
            "config": config
        }

        active_controllers[controller_id] = controller_data

        # Publish event
        publish_event("created", controller_data)

        return ControllerResponse(**controller_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating controller: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/controllers", response_model=List[ControllerResponse])
async def list_controllers(controller_type: Optional[str] = None):
    """List all controllers"""
    controllers = list(active_controllers.values())

    # Filter by type if specified
    if controller_type:
        controllers = [c for c in controllers if c["controller_type"] == controller_type]

    return [ControllerResponse(**c) for c in controllers]


@app.get("/api/controllers/{controller_id}", response_model=ControllerResponse)
async def get_controller(controller_id: str):
    """Get controller details"""
    if controller_id not in active_controllers:
        raise HTTPException(status_code=404, detail=f"Controller {controller_id} not found")

    return ControllerResponse(**active_controllers[controller_id])


@app.put("/api/controllers/{controller_id}", response_model=ControllerResponse)
async def update_controller(controller_id: str, update: ControllerUpdate):
    """Update controller configuration"""
    if controller_id not in active_controllers:
        raise HTTPException(status_code=404, detail=f"Controller {controller_id} not found")

    controller = active_controllers[controller_id]

    # Update status
    if update.status:
        controller["status"] = update.status

    # Update config
    if update.config:
        controller["config"].update(update.config)

    # Publish event
    publish_event("updated", controller)

    return ControllerResponse(**controller)


@app.delete("/api/controllers/{controller_id}", status_code=204)
async def delete_controller(controller_id: str):
    """Stop and remove a controller"""
    if controller_id not in active_controllers:
        raise HTTPException(status_code=404, detail=f"Controller {controller_id} not found")

    controller = active_controllers[controller_id]

    try:
        # Stop Docker container if exists
        if controller.get("container_id") and not controller["container_id"].startswith("custom_"):
            container = get_docker_client().containers.get(controller["container_id"])
            container.stop(timeout=10)
            container.remove()
            logger.info(f"Stopped and removed controller container: {controller['container_id'][:12]}")

        # Remove from registry
        del active_controllers[controller_id]

        # Publish event
        publish_event("deleted", {"controller_id": controller_id, "name": controller["name"]})

        return None

    except Exception as e:
        logger.error(f"Error deleting controller: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/controllers/{controller_id}/start")
async def start_controller(controller_id: str):
    """Start a stopped controller"""
    if controller_id not in active_controllers:
        raise HTTPException(status_code=404, detail=f"Controller {controller_id} not found")

    controller = active_controllers[controller_id]

    try:
        if controller.get("container_id") and not controller["container_id"].startswith("custom_"):
            container = get_docker_client().containers.get(controller["container_id"])
            container.start()
            controller["status"] = "running"
            logger.info(f"Started controller: {controller_id}")

            # Publish event
            publish_event("started", {"controller_id": controller_id})

        return {"message": f"Controller {controller_id} started", "status": "running"}

    except Exception as e:
        logger.error(f"Error starting controller: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/controllers/{controller_id}/stop")
async def stop_controller(controller_id: str):
    """Stop a running controller"""
    if controller_id not in active_controllers:
        raise HTTPException(status_code=404, detail=f"Controller {controller_id} not found")

    controller = active_controllers[controller_id]

    try:
        if controller.get("container_id") and not controller["container_id"].startswith("custom_"):
            container = get_docker_client().containers.get(controller["container_id"])
            container.stop(timeout=10)
            controller["status"] = "stopped"
            logger.info(f"Stopped controller: {controller_id}")

            # Publish event
            publish_event("stopped", {"controller_id": controller_id})

        return {"message": f"Controller {controller_id} stopped", "status": "stopped"}

    except Exception as e:
        logger.error(f"Error stopping controller: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/controllers/{controller_id}/status")
async def get_controller_status(controller_id: str):
    """Get detailed controller status"""
    if controller_id not in active_controllers:
        raise HTTPException(status_code=404, detail=f"Controller {controller_id} not found")

    controller = active_controllers[controller_id]

    status = {
        "controller_id": controller_id,
        "name": controller["name"],
        "type": controller["controller_type"],
        "status": controller["status"],
        "uptime": None,
        "container_status": None
    }

    try:
        # Get container status if applicable
        if controller.get("container_id") and not controller["container_id"].startswith("custom_"):
            container = get_docker_client().containers.get(controller["container_id"])
            status["container_status"] = container.status
            status["uptime"] = container.attrs.get("State", {}).get("StartedAt")

    except Exception as e:
        logger.error(f"Error getting controller status: {e}")
        status["error"] = str(e)

    return status


@app.get("/api/controllers/{controller_id}/logs")
async def get_controller_logs(controller_id: str, tail: int = 100):
    """Get controller logs"""
    if controller_id not in active_controllers:
        raise HTTPException(status_code=404, detail=f"Controller {controller_id} not found")

    controller = active_controllers[controller_id]

    try:
        if controller.get("container_id") and not controller["container_id"].startswith("custom_"):
            container = get_docker_client().containers.get(controller["container_id"])
            logs = container.logs(tail=tail).decode('utf-8')

            return {
                "controller_id": controller_id,
                "logs": logs.splitlines()
            }
        else:
            return {
                "controller_id": controller_id,
                "logs": ["Logs not available for custom controllers"]
            }

    except Exception as e:
        logger.error(f"Error getting controller logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)
