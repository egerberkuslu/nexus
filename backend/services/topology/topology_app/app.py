"""
Topology Service - Port 8001
Handles CRUD operations for topologies, JSON import/export, and versioning
"""

import logging
from fastapi import FastAPI, HTTPException, Depends, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
import httpx
import os
import docker
from pydantic import BaseModel, Field
from typing import Any, Dict
import asyncio
import json
from datetime import datetime
import copy

from sqlalchemy.exc import IntegrityError

from shared.database.postgres import get_db, init_db
from shared.models.topology import Topology, Node, Link, Controller, Project, EmulationStatus
from shared.models.network_config import NetworkConfiguration
from shared.schemas.topology_schema import (
    TopologyCreate,
    TopologyUpdate,
    TopologyResponse,
    NodeCreate,
    NodeUpdate,
    NodeResponse,
    LinkCreate,
    LinkUpdate,
    LinkResponse,
    ControllerCreate,
    ControllerResponse,
    ProjectCreate,
   ProjectUpdate,
   ProjectResponse,
   TopologyDefinition,
   TopologyApplyRequest,
    TopologyChangeSet,
    NodeIdentifier,
    LinkIdentifier
)
from shared.schemas.network_config_schema import (
    NetworkConfigCreateRequest,
    NetworkConfigListItem,
    NetworkConfigResponse,
    NetworkConfigurationDocument,
)
from shared.messaging.rabbitmq import RabbitMQPublisher
from shared.utils.consul_client import ConsulClient

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Caduceus-Flux Topology Service",
    description="Manages network topology CRUD operations",
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

# Service registration
consul_client = ConsulClient()
rabbitmq_publisher = RabbitMQPublisher()

# Docker client for container management
docker_client = None
try:
    docker_client = docker.from_env()
    # Test connection
    docker_client.ping()
    logger.info("✅ Docker client initialized successfully")
except Exception as e:
    logger.warning(f"Docker client initialization failed: {e}")
    docker_client = None


class P4ProgramDraftUpsert(BaseModel):
    draft_id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=128)
    source_code: str = Field(..., min_length=1)
    target: str = Field(default="bmv2")
    architecture: str = Field(default="v1model")
    compiled_program_id: Optional[str] = None


class P4ProgramDraftResponse(BaseModel):
    draft_id: str
    name: str
    source_code: str
    target: str
    architecture: str
    compiled_program_id: Optional[str] = None
    created_at: str
    updated_at: str


def _ensure_topology_metadata(topology: Topology) -> Dict[str, Any]:
    meta = topology.topology_metadata
    if not isinstance(meta, dict):
        meta = {}
    # Deep-copy to avoid mutating the existing JSON structure in-place (which SQLAlchemy won't detect).
    meta = copy.deepcopy(meta)
    topology.topology_metadata = meta
    return meta


def _ensure_p4_drafts(meta: Dict[str, Any]) -> Dict[str, Any]:
    drafts = meta.get("p4_programs")
    if drafts is None:
        drafts = {}
        meta["p4_programs"] = drafts
    if isinstance(drafts, list):
        migrated = {}
        for item in drafts:
            if isinstance(item, dict) and item.get("draft_id"):
                migrated[str(item["draft_id"])] = item
        drafts = migrated
        meta["p4_programs"] = drafts
    if not isinstance(drafts, dict):
        drafts = {}
        meta["p4_programs"] = drafts
    return drafts


class _TopologyWebSocketManager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._connections: Dict[str, set[WebSocket]] = {}

    async def connect(self, topology_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.setdefault(topology_id, set()).add(websocket)

    async def disconnect(self, topology_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            conns = self._connections.get(topology_id)
            if not conns:
                return
            conns.discard(websocket)
            if not conns:
                self._connections.pop(topology_id, None)

    async def broadcast(self, topology_id: str, message: Dict[str, Any]) -> None:
        async with self._lock:
            conns = list(self._connections.get(topology_id, set()))
        if not conns:
            return

        payload = json.dumps(message, default=str)
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                current = self._connections.get(topology_id, set())
                for ws in dead:
                    current.discard(ws)
                if not current:
                    self._connections.pop(topology_id, None)


topology_ws = _TopologyWebSocketManager()


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    logger.info("Starting Topology Service...")
    init_db()
    consul_client.register_service("topology-service", 8001)
    rabbitmq_publisher.connect()
    logger.info("Topology Service started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Topology Service...")
    consul_client.deregister_service("topology-service")
    rabbitmq_publisher.disconnect()


@app.websocket("/ws/topology/{topology_id}")
async def topology_updates_ws(websocket: WebSocket, topology_id: str):
    """
    WebSocket channel for topology editor live updates.
    Sends events:
      - topology.updated
      - topology.node.updated
      - topology.link.updated
    """
    await topology_ws.connect(topology_id, websocket)
    await websocket.send_text(json.dumps({"type": "connected", "payload": {"topology_id": topology_id}}))
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                msg = {"type": raw}
            if (msg.get("type") or "").lower() == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        await topology_ws.disconnect(topology_id, websocket)
    except Exception:
        await topology_ws.disconnect(topology_id, websocket)


# Helper function to get container info from orchestrator
async def _fetch_active_emulations(orchestrator_url: str, timeout_seconds: float = 2.0) -> list[dict[str, Any]]:
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.get(f"{orchestrator_url}/api/emulation/active")
        if response.status_code != 200:
            return []
        data = response.json() or {}
        emulations = data.get("emulations", [])
        return emulations if isinstance(emulations, list) else []
    except Exception:
        return []


async def get_container_info(topology_id: str, active_emulations: Optional[list[dict[str, Any]]] = None):
    """Fetch container/emulation info for a topology from the orchestrator service."""
    try:
        orchestrator_url = os.getenv("ORCHESTRATOR_SERVICE_URL", "http://orchestrator-service:8002")
        emulations = active_emulations
        if emulations is None:
            emulations = await _fetch_active_emulations(orchestrator_url, timeout_seconds=2.0)
        for emulation in emulations:
            if emulation.get("topology_id") == topology_id:
                return {
                    "container_id": emulation.get("container_id"),
                    "container_name": emulation.get("container_name"),
                    "emulation_id": emulation.get("emulation_id"),
                    "status": emulation.get("status"),
                }
    except Exception as e:
        logger.error(f"Could not fetch container info for topology {topology_id}: {e}")
    return {"container_id": None, "container_name": None, "emulation_id": None, "status": None}


async def cleanup_emulation_container(topology_id: str):
    """Stop and remove the emulation container for a topology."""
    try:
        # First, get container info from orchestrator
        container_info = await get_container_info(topology_id)
        container_id = container_info.get("container_id")
        container_name = container_info.get("container_name")

        if not container_id or not container_name:
            logger.info(f"No active container found for topology {topology_id}")
            return True

        if not docker_client:
            logger.error("Docker client not available for container cleanup")
            return False

        # Stop and remove container by ID
        try:
            container = docker_client.containers.get(container_id)
            logger.info(f"Stopping container {container_name} ({container_id[:12]})")
            container.stop(timeout=10)
            logger.info(f"Removing container {container_name} ({container_id[:12]})")
            container.remove(force=True)
            logger.info(f"✅ Container {container_name} cleaned up successfully")
            return True
        except docker.errors.NotFound:
            logger.warning(f"Container {container_name} ({container_id[:12]}) not found, may already be removed")
            return True
        except Exception as e:
            logger.error(f"Failed to cleanup container {container_name}: {e}")
            return False

    except Exception as e:
        logger.error(f"Error during container cleanup for topology {topology_id}: {e}")
        return False


# ==================== Project Endpoints ====================

@app.post("/api/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    """Create a new project"""
    db_project = Project(
        id=str(uuid.uuid4()),
        name=project.name,
        description=project.description,
        owner=project.owner
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)

    # Automatically create a default topology for the project
    default_topology = Topology(
        id=str(uuid.uuid4()),
        project_id=db_project.id,
        name=f"{project.name} - Main Topology",
        description="Default topology"
    )
    db.add(default_topology)
    db.commit()
    db.refresh(default_topology)

    logger.info(f"Created project: {db_project.id} with default topology: {default_topology.id}")
    rabbitmq_publisher.publish("project.created", {
        "project_id": db_project.id,
        "topology_id": default_topology.id
    })

    return db_project


@app.get("/api/projects", response_model=List[ProjectResponse])
async def list_projects(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List all projects"""
    projects = db.query(Project).offset(skip).limit(limit).all()
    return projects


@app.get("/api/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, db: Session = Depends(get_db)):
    """Get a specific project"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@app.put("/api/projects/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: str, project_update: ProjectUpdate, db: Session = Depends(get_db)):
    """Update a project"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project_update.name is not None:
        project.name = project_update.name
    if project_update.description is not None:
        project.description = project_update.description

    db.commit()
    db.refresh(project)

    logger.info(f"Updated project: {project_id}")
    rabbitmq_publisher.publish("project.updated", {"project_id": project_id})

    return project


@app.delete("/api/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: str, db: Session = Depends(get_db)):
    """Delete a project and cleanup all associated topology containers"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get all topologies for this project and cleanup their containers
    topologies = db.query(Topology).filter(Topology.project_id == project_id).all()
    logger.info(f"Cleaning up {len(topologies)} topology containers for project {project_id}")

    for topology in topologies:
        logger.info(f"Cleaning up container for topology {topology.id}")
        await cleanup_emulation_container(topology.id)

    # Delete project (will cascade delete topologies)
    db.delete(project)
    db.commit()

    logger.info(f"✅ Deleted project: {project_id}")
    rabbitmq_publisher.publish("project.deleted", {"project_id": project_id})


# ==================== Topology Endpoints ====================

@app.post("/api/topologies", response_model=TopologyResponse, status_code=status.HTTP_201_CREATED)
async def create_topology(topology: TopologyCreate, db: Session = Depends(get_db)):
    """Create a new topology"""
    # Verify project exists
    project = db.query(Project).filter(Project.id == topology.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Create topology
    topology_id = str(uuid.uuid4())
    db_topology = Topology(
        id=topology_id,
        project_id=topology.project_id,
        name=topology.name,
        description=topology.description
    )
    db.add(db_topology)

    # Map node names to generated DB IDs so links can reference either names or IDs.
    node_name_to_id: Dict[str, str] = {}

    # Create nodes
    for node in topology.nodes:
        node_id = str(uuid.uuid4())
        node_name_to_id[str(node.name)] = node_id
        db_node = Node(
            id=node_id,
            topology_id=topology_id,
            name=node.name,
            device_type=node.device_type,
            x=node.x,
            y=node.y,
            properties=node.properties
        )
        db.add(db_node)

    # Create links
    for link in topology.links:
        source = str(link.source_node_id)
        target = str(link.target_node_id)
        if source in node_name_to_id:
            source = node_name_to_id[source]
        if target in node_name_to_id:
            target = node_name_to_id[target]

        # If the link doesn't resolve to nodes we just created, fail fast with a clear error
        # instead of a 500 from the DB foreign key constraint.
        if source not in node_name_to_id.values() or target not in node_name_to_id.values():
            raise HTTPException(
                status_code=400,
                detail=(
                    "Link endpoints must reference existing nodes by name. "
                    f"Unknown endpoints: source={link.source_node_id!r}, target={link.target_node_id!r}"
                ),
            )
        db_link = Link(
            id=str(uuid.uuid4()),
            topology_id=topology_id,
            source_node_id=source,
            target_node_id=target,
            source_port=link.source_port,
            target_port=link.target_port,
            bandwidth=link.bandwidth,
            delay=link.delay,
            loss=link.loss,
            max_queue_size=link.max_queue_size,
            properties=link.properties
        )
        db.add(db_link)

    # Create controllers
    for controller in topology.controllers:
        db_controller = Controller(
            id=str(uuid.uuid4()),
            topology_id=topology_id,
            name=controller.name,
            controller_type=controller.controller_type,
            ip=controller.ip,
            port=controller.port,
            properties=controller.properties
        )
        db.add(db_controller)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Invalid topology payload: {exc.orig}") from exc
    db.refresh(db_topology)

    logger.info(f"Created topology: {topology_id}")
    rabbitmq_publisher.publish("topology.created", {
        "topology_id": topology_id,
        "project_id": topology.project_id
    })

    await topology_ws.broadcast(
        topology_id,
        {"type": "topology.updated", "payload": {"topology_id": topology_id, "action": "created"}},
    )
    return db_topology


def _replace_topology_contents_from_definition(
    *,
    db: Session,
    topology: Topology,
    topology_def: TopologyDefinition,
) -> Topology:
    """
    Replace nodes/links/controllers for an existing topology from a TopologyDefinition.

    Supports link endpoints referencing nodes either by node name or by an `id` field
    included in the imported node objects.
    """
    # Update high-level fields
    topology.name = topology_def.name
    topology.description = topology_def.description

    # Merge metadata to avoid unintentionally dropping non-import data (e.g., p4 programs).
    if isinstance(topology_def.metadata, dict):
        topology.topology_metadata = {**(topology.topology_metadata or {}), **topology_def.metadata}

    # Remove existing contents. Delete links first to avoid FK issues.
    db.query(Link).filter(Link.topology_id == topology.id).delete(synchronize_session=False)
    db.query(Controller).filter(Controller.topology_id == topology.id).delete(synchronize_session=False)
    db.query(Node).filter(Node.topology_id == topology.id).delete(synchronize_session=False)
    db.flush()

    # Validate payload shapes using the existing create schemas (gives consistent errors).
    imported_nodes_raw: list[dict[str, Any]] = [
        dict(n) for n in (topology_def.nodes or []) if isinstance(n, dict)
    ]
    imported_node_id_by_name: dict[str, str] = {
        str(n.get("name")): str(n.get("id"))
        for n in imported_nodes_raw
        if n.get("name") and n.get("id")
    }

    nodes = [NodeCreate(**node) for node in (topology_def.nodes or [])]
    links = [LinkCreate(**link) for link in (topology_def.links or [])]
    controllers = [ControllerCreate(**ctrl) for ctrl in (topology_def.controllers or [])]

    # Map imported node identifiers -> new DB node IDs.
    node_identifier_to_id: Dict[str, str] = {}
    created_node_ids: set[str] = set()

    for node in nodes:
        node_id = str(uuid.uuid4())
        created_node_ids.add(node_id)
        node_identifier_to_id[str(node.name)] = node_id

        imported_id = imported_node_id_by_name.get(str(node.name))
        if imported_id:
            node_identifier_to_id[str(imported_id)] = node_id

        db_node = Node(
            id=node_id,
            topology_id=topology.id,
            name=node.name,
            device_type=node.device_type,
            x=node.x,
            y=node.y,
            properties=node.properties,
        )
        db.add(db_node)

    # Create links
    for link in links:
        source_raw = str(link.source_node_id)
        target_raw = str(link.target_node_id)
        source = node_identifier_to_id.get(source_raw, source_raw)
        target = node_identifier_to_id.get(target_raw, target_raw)

        if source not in created_node_ids or target not in created_node_ids:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Link endpoints must reference existing nodes by name or imported id. "
                    f"Unknown endpoints: source={source_raw!r}, target={target_raw!r}"
                ),
            )

        db_link = Link(
            id=str(uuid.uuid4()),
            topology_id=topology.id,
            source_node_id=source,
            target_node_id=target,
            source_port=link.source_port,
            target_port=link.target_port,
            bandwidth=link.bandwidth,
            delay=link.delay,
            loss=link.loss,
            max_queue_size=link.max_queue_size,
            properties=link.properties,
        )
        db.add(db_link)

    # Create controllers
    for ctrl in controllers:
        db_controller = Controller(
            id=str(uuid.uuid4()),
            topology_id=topology.id,
            name=ctrl.name,
            controller_type=ctrl.controller_type,
            ip=ctrl.ip,
            port=ctrl.port,
            properties=ctrl.properties,
        )
        db.add(db_controller)

    topology.version = int(topology.version or 0) + 1
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Invalid topology payload: {exc.orig}") from exc
    db.refresh(topology)
    return topology


@app.get("/api/topologies", response_model=List[TopologyResponse])
async def list_topologies(
    project_id: str = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all topologies, optionally filtered by project"""
    query = db.query(Topology)
    if project_id:
        query = query.filter(Topology.project_id == project_id)
    topologies = query.offset(skip).limit(limit).all()

    orchestrator_url = os.getenv("ORCHESTRATOR_SERVICE_URL", "http://orchestrator-service:8002")
    active_emulations = await _fetch_active_emulations(orchestrator_url, timeout_seconds=2.0)
    active_by_topology: dict[str, dict[str, Any]] = {}
    for emu in active_emulations:
        tid = emu.get("topology_id")
        if isinstance(tid, str) and tid:
            active_by_topology[tid] = emu

    # Fetch container info for each topology (from single orchestrator call)
    topology_list = []
    for topology in topologies:
        emu = active_by_topology.get(topology.id) or {}
        emu_status = (emu or {}).get("status")
        emu_status_str = str(emu_status or "").lower()
        derived_status = topology.emulation_status
        if emu_status_str == "running":
            derived_status = EmulationStatus.RUNNING
        elif emu_status_str in ("stopped", "exited", "dead"):
            derived_status = EmulationStatus.STOPPED
        derived_is_active = bool(topology.is_active or emu_status_str == "running")
        topology_dict = {
            "id": topology.id,
            "project_id": topology.project_id,
            "name": topology.name,
            "description": topology.description,
            "version": topology.version,
            "is_active": derived_is_active,
            "emulation_status": derived_status,
            "emulation_id": emu.get("emulation_id"),
            "created_at": topology.created_at,
            "updated_at": topology.updated_at,
            "nodes": topology.nodes,
            "links": topology.links,
            "controllers": topology.controllers,
            "container_id": emu.get("container_id"),
            "container_name": emu.get("container_name"),
        }
        topology_list.append(topology_dict)

    return topology_list


@app.get("/api/topologies/{topology_id}", response_model=TopologyResponse)
async def get_topology(topology_id: str, db: Session = Depends(get_db)):
    """Get a specific topology with all its components"""
    topology = db.query(Topology).filter(Topology.id == topology_id).first()
    if not topology:
        raise HTTPException(status_code=404, detail="Topology not found")

    orchestrator_url = os.getenv("ORCHESTRATOR_SERVICE_URL", "http://orchestrator-service:8002")
    active_emulations = await _fetch_active_emulations(orchestrator_url, timeout_seconds=2.0)
    container_info = await get_container_info(topology_id, active_emulations=active_emulations)
    emu_status = (container_info or {}).get("status")
    emu_status_str = str(emu_status or "").lower()
    derived_status = topology.emulation_status
    if emu_status_str == "running":
        derived_status = EmulationStatus.RUNNING
    elif emu_status_str in ("stopped", "exited", "dead"):
        derived_status = EmulationStatus.STOPPED
    derived_is_active = bool(topology.is_active or emu_status_str == "running")

    # Convert to dict and add container info
    topology_dict = {
        "id": topology.id,
        "project_id": topology.project_id,
        "name": topology.name,
        "description": topology.description,
        "version": topology.version,
        "is_active": derived_is_active,
        "emulation_status": derived_status,
        "emulation_id": container_info.get("emulation_id"),
        "created_at": topology.created_at,
        "updated_at": topology.updated_at,
        "nodes": topology.nodes,
        "links": topology.links,
        "controllers": topology.controllers,
        "container_id": container_info.get("container_id"),
        "container_name": container_info.get("container_name"),
    }
    return topology_dict


@app.put("/api/topologies/{topology_id}", response_model=TopologyResponse)
async def update_topology(
    topology_id: str,
    topology_update: dict,
    db: Session = Depends(get_db)
):
    """Update a topology including nodes and links"""
    topology = db.query(Topology).filter(Topology.id == topology_id).first()
    if not topology:
        raise HTTPException(status_code=404, detail="Topology not found")

    # Update basic info
    if 'name' in topology_update and topology_update['name'] is not None:
        topology.name = topology_update['name']
    if 'description' in topology_update and topology_update['description'] is not None:
        topology.description = topology_update['description']

    # Delete existing links FIRST (before nodes, due to foreign key constraints)
    if 'links' in topology_update or 'nodes' in topology_update:
        db.query(Link).filter(Link.topology_id == topology_id).delete()
    
    # Delete existing nodes SECOND
    if 'nodes' in topology_update:
        db.query(Node).filter(Node.topology_id == topology_id).delete()

    # Create new nodes FIRST
    if 'nodes' in topology_update:
        for node_data in topology_update['nodes']:
            db_node = Node(
                id=node_data.get('id', str(uuid.uuid4())),
                topology_id=topology_id,
                name=node_data['name'],
                device_type=node_data['device_type'],
                x=node_data.get('x', 0),
                y=node_data.get('y', 0),
                properties=node_data.get('properties', {})
            )
            db.add(db_node)
        # Flush to persist nodes before creating links
        db.flush()

    # Create new links SECOND (after nodes exist in DB)
    if 'links' in topology_update:
        for link_data in topology_update['links']:
            # Always generate new UUID for links (ignore React Flow edge IDs - they're too long)
            db_link = Link(
                id=str(uuid.uuid4()),
                topology_id=topology_id,
                source_node_id=link_data['source_node_id'],
                target_node_id=link_data['target_node_id'],
                source_port=link_data.get('source_port'),
                target_port=link_data.get('target_port'),
                bandwidth=link_data.get('bandwidth', 1000),
                delay=link_data.get('delay', 0),
                loss=link_data.get('loss', 0),
                max_queue_size=link_data.get('max_queue_size'),
                properties=link_data.get('properties', {})
            )
            db.add(db_link)

    # Increment version
    topology.version += 1

    db.commit()
    db.refresh(topology)

    logger.info(f"Updated topology: {topology_id} to version {topology.version}")
    rabbitmq_publisher.publish("topology.updated", {
        "topology_id": topology_id,
        "version": topology.version
    })

    await topology_ws.broadcast(
        topology_id,
        {"type": "topology.updated", "payload": {"topology_id": topology_id, "action": "updated"}},
    )
    return topology


@app.post("/api/topologies/{topology_id}/apply", response_model=TopologyResponse)
async def apply_topology_changes(
    topology_id: str,
    request: TopologyApplyRequest,
    db: Session = Depends(get_db)
):
    """Apply a staged diff to the topology and persist changes atomically."""
    topology = db.query(Topology).filter(Topology.id == topology_id).first()
    if not topology:
        raise HTTPException(status_code=404, detail="Topology not found")

    change_set = request.changes or TopologyChangeSet()
    if change_set.is_empty():
        raise HTTPException(status_code=400, detail="No staged changes provided")

    nodes = db.query(Node).filter(Node.topology_id == topology_id).all()
    links = db.query(Link).filter(Link.topology_id == topology_id).all()

    nodes_by_id = {node.id: node for node in nodes}
    nodes_by_name = {node.name: node for node in nodes if node.name}
    links_by_id = {link.id: link for link in links}

    def resolve_node(identifier: NodeIdentifier) -> Optional[Node]:
        if identifier.id and identifier.id in nodes_by_id:
            return nodes_by_id[identifier.id]
        if identifier.name:
            return nodes_by_name.get(identifier.name)
        return None

    def resolve_link(identifier: LinkIdentifier) -> Optional[Link]:
        if identifier.id and identifier.id in links_by_id:
            return links_by_id[identifier.id]
        if identifier.source_node_id and identifier.target_node_id:
            for link in links_by_id.values():
                if (
                    link.source_node_id == identifier.source_node_id
                    and link.target_node_id == identifier.target_node_id
                ):
                    return link
        return None

    try:
        # Remove links before nodes to satisfy FK constraints
        for link_ref in change_set.remove_links:
            link = resolve_link(link_ref)
            if not link:
                raise HTTPException(
                    status_code=404,
                    detail=f"Unable to resolve link for removal: {link_ref}"
                )
            links_by_id.pop(link.id, None)
            db.delete(link)

        # Remove devices along with any orphaned links
        for node_ref in change_set.remove_devices:
            node = resolve_node(node_ref)
            if not node:
                raise HTTPException(
                    status_code=404,
                    detail=f"Unable to resolve node for removal: {node_ref}"
                )

            db.query(Link).filter(
                (Link.source_node_id == node.id) | (Link.target_node_id == node.id)
            ).delete(synchronize_session=False)

            links_by_id = {
                link_id: link_obj
                for link_id, link_obj in links_by_id.items()
                if link_obj.source_node_id != node.id and link_obj.target_node_id != node.id
            }

            nodes_by_id.pop(node.id, None)
            nodes_by_name.pop(node.name, None)
            db.delete(node)

        db.flush()

        # Add devices
        for node_delta in change_set.add_devices:
            node_id = node_delta.id or str(uuid.uuid4())
            node_properties = dict(node_delta.properties or {})
            db_node = Node(
                id=node_id,
                topology_id=topology_id,
                name=node_delta.name,
                device_type=node_delta.device_type.value if hasattr(node_delta.device_type, "value") else node_delta.device_type,
                x=node_delta.x,
                y=node_delta.y,
                properties=node_properties
            )
            db.add(db_node)
            nodes_by_id[node_id] = db_node
            nodes_by_name[db_node.name] = db_node

        db.flush()

        # Update existing devices
        for update in change_set.update_devices:
            node = nodes_by_id.get(update.id)
            if not node:
                raise HTTPException(
                    status_code=404,
                    detail=f"Node not found for update: {update.id}"
                )

            if update.name is not None:
                if node.name in nodes_by_name:
                    nodes_by_name.pop(node.name, None)
                node.name = update.name
                nodes_by_name[node.name] = node
            if update.x is not None:
                node.x = update.x
            if update.y is not None:
                node.y = update.y
            if update.properties is not None:
                node.properties = dict(update.properties)

        db.flush()

        # Add links
        for link_delta in change_set.add_links:
            if link_delta.source_node_id not in nodes_by_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid source node for link add: {link_delta.source_node_id}"
                )
            if link_delta.target_node_id not in nodes_by_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid target node for link add: {link_delta.target_node_id}"
                )

            link_id = link_delta.id or str(uuid.uuid4())
            link_properties = dict(link_delta.properties or {})
            db_link = Link(
                id=link_id,
                topology_id=topology_id,
                source_node_id=link_delta.source_node_id,
                target_node_id=link_delta.target_node_id,
                source_port=link_delta.source_port,
                target_port=link_delta.target_port,
                bandwidth=link_delta.bandwidth,
                delay=link_delta.delay,
                loss=link_delta.loss,
                max_queue_size=link_delta.max_queue_size,
                properties=link_properties
            )
            db.add(db_link)
            links_by_id[link_id] = db_link

        db.flush()

        # Update existing links
        for update in change_set.update_links:
            link = links_by_id.get(update.id) or resolve_link(LinkIdentifier(id=update.id))
            if not link:
                raise HTTPException(
                    status_code=404,
                    detail=f"Link not found for update: {update.id}"
                )

            if update.source_node_id:
                if update.source_node_id not in nodes_by_id:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid source node for link update: {update.source_node_id}"
                    )
                link.source_node_id = update.source_node_id
            if update.target_node_id:
                if update.target_node_id not in nodes_by_id:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid target node for link update: {update.target_node_id}"
                    )
                link.target_node_id = update.target_node_id
            if update.bandwidth is not None:
                link.bandwidth = update.bandwidth
            if update.delay is not None:
                link.delay = update.delay
            if update.loss is not None:
                link.loss = update.loss
            if update.max_queue_size is not None:
                link.max_queue_size = update.max_queue_size
            if update.status is not None:
                link.status = update.status
            if update.properties is not None:
                link.properties = dict(update.properties)

        if request.commit:
            topology.version += 1

        db.commit()

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to apply topology changes: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to apply topology changes") from exc

    updated_topology = db.query(Topology).filter(Topology.id == topology_id).first()
    await topology_ws.broadcast(
        topology_id,
        {"type": "topology.updated", "payload": {"topology_id": topology_id, "action": "applied"}},
    )
    return updated_topology


# ==================== P4 Draft Endpoints (stored in topology metadata) ====================

@app.get(
    "/api/topologies/{topology_id}/p4/programs",
    response_model=List[P4ProgramDraftResponse],
)
async def list_topology_p4_programs(topology_id: str, db: Session = Depends(get_db)):
    topology = db.query(Topology).filter(Topology.id == topology_id).first()
    if not topology:
        raise HTTPException(status_code=404, detail="Topology not found")

    meta = _ensure_topology_metadata(topology)
    drafts = _ensure_p4_drafts(meta)

    items: list[dict] = []
    for draft_id, raw in drafts.items():
        if not isinstance(raw, dict):
            continue
        now = datetime.utcnow().isoformat()
        normalized = {
            "draft_id": str(raw.get("draft_id") or draft_id),
            "name": str(raw.get("name") or "Untitled"),
            "source_code": str(raw.get("source_code") or ""),
            "target": str(raw.get("target") or "bmv2"),
            "architecture": str(raw.get("architecture") or "v1model"),
            "compiled_program_id": raw.get("compiled_program_id"),
            "created_at": str(raw.get("created_at") or now),
            "updated_at": str(raw.get("updated_at") or now),
        }
        if normalized["source_code"]:
            items.append(normalized)

    items.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
    return [P4ProgramDraftResponse(**item) for item in items]


@app.get(
    "/api/topologies/{topology_id}/p4/programs/{draft_id}",
    response_model=P4ProgramDraftResponse,
)
async def get_topology_p4_program(topology_id: str, draft_id: str, db: Session = Depends(get_db)):
    topology = db.query(Topology).filter(Topology.id == topology_id).first()
    if not topology:
        raise HTTPException(status_code=404, detail="Topology not found")

    meta = _ensure_topology_metadata(topology)
    drafts = _ensure_p4_drafts(meta)
    raw = drafts.get(draft_id)
    if not isinstance(raw, dict):
        raise HTTPException(status_code=404, detail="P4 draft not found")

    now = datetime.utcnow().isoformat()
    normalized = {
        "draft_id": str(raw.get("draft_id") or draft_id),
        "name": str(raw.get("name") or "Untitled"),
        "source_code": str(raw.get("source_code") or ""),
        "target": str(raw.get("target") or "bmv2"),
        "architecture": str(raw.get("architecture") or "v1model"),
        "compiled_program_id": raw.get("compiled_program_id"),
        "created_at": str(raw.get("created_at") or now),
        "updated_at": str(raw.get("updated_at") or now),
    }
    return P4ProgramDraftResponse(**normalized)


@app.post(
    "/api/topologies/{topology_id}/p4/programs",
    response_model=P4ProgramDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upsert_topology_p4_program(
    topology_id: str,
    payload: P4ProgramDraftUpsert,
    db: Session = Depends(get_db),
):
    topology = db.query(Topology).filter(Topology.id == topology_id).first()
    if not topology:
        raise HTTPException(status_code=404, detail="Topology not found")

    meta = _ensure_topology_metadata(topology)
    drafts = _ensure_p4_drafts(meta)

    now = datetime.utcnow().isoformat()
    draft_id = (payload.draft_id or "").strip() or str(uuid.uuid4())
    existing = drafts.get(draft_id) if isinstance(drafts.get(draft_id), dict) else None
    created_at = str((existing or {}).get("created_at") or now)

    record = {
        "draft_id": draft_id,
        "name": payload.name,
        "source_code": payload.source_code,
        "target": payload.target,
        "architecture": payload.architecture,
        "compiled_program_id": payload.compiled_program_id,
        "created_at": created_at,
        "updated_at": now,
    }

    drafts[draft_id] = record
    topology.topology_metadata = {**meta, "p4_programs": dict(drafts)}
    db.commit()
    db.refresh(topology)

    return P4ProgramDraftResponse(**record)


@app.delete(
    "/api/topologies/{topology_id}/p4/programs/{draft_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_topology_p4_program(topology_id: str, draft_id: str, db: Session = Depends(get_db)):
    topology = db.query(Topology).filter(Topology.id == topology_id).first()
    if not topology:
        raise HTTPException(status_code=404, detail="Topology not found")

    meta = _ensure_topology_metadata(topology)
    drafts = _ensure_p4_drafts(meta)

    if draft_id not in drafts:
        raise HTTPException(status_code=404, detail="P4 draft not found")

    drafts.pop(draft_id, None)
    topology.topology_metadata = {**meta, "p4_programs": dict(drafts)}
    db.commit()
    return None


@app.delete("/api/topologies/{topology_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topology(topology_id: str, db: Session = Depends(get_db)):
    """Delete a topology and cleanup its emulation container"""
    topology = db.query(Topology).filter(Topology.id == topology_id).first()
    if not topology:
        raise HTTPException(status_code=404, detail="Topology not found")

    # Cleanup emulation container if it exists (even if topology is_active is False)
    logger.info(f"Cleaning up emulation container for topology {topology_id}")
    await cleanup_emulation_container(topology_id)

    # Delete topology from database
    db.delete(topology)
    db.commit()

    logger.info(f"✅ Deleted topology: {topology_id}")
    rabbitmq_publisher.publish("topology.deleted", {"topology_id": topology_id})


@app.post("/api/topologies/{topology_id}/stop", status_code=status.HTTP_200_OK)
async def stop_topology_emulation(topology_id: str, db: Session = Depends(get_db)):
    """Stop the emulation for a topology and cleanup its container"""
    topology = db.query(Topology).filter(Topology.id == topology_id).first()
    if not topology:
        raise HTTPException(status_code=404, detail="Topology not found")

    # Cleanup emulation container
    logger.info(f"Stopping emulation and cleaning up container for topology {topology_id}")
    cleanup_success = await cleanup_emulation_container(topology_id)

    if cleanup_success:
        # Update topology status
        topology.is_active = False
        topology.emulation_status = EmulationStatus.STOPPED
        db.commit()

        logger.info(f"✅ Stopped emulation for topology: {topology_id}")
        rabbitmq_publisher.publish("emulation.stopped", {
            "topology_id": topology_id,
            "cleanup": True
        })

        return {
            "success": True,
            "message": f"Emulation stopped and container cleaned up for topology {topology_id}",
            "topology_id": topology_id
        }
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to cleanup emulation container"
        )


# ==================== Node Endpoints ====================

@app.post("/api/topologies/{topology_id}/nodes", response_model=NodeResponse, status_code=status.HTTP_201_CREATED)
async def add_node(topology_id: str, node: NodeCreate, db: Session = Depends(get_db)):
    """Add a node to a topology"""
    topology = db.query(Topology).filter(Topology.id == topology_id).first()
    if not topology:
        raise HTTPException(status_code=404, detail="Topology not found")

    db_node = Node(
        id=str(uuid.uuid4()),
        topology_id=topology_id,
        name=node.name,
        device_type=node.device_type,
        x=node.x,
        y=node.y,
        properties=node.properties
    )
    db.add(db_node)
    topology.version += 1
    db.commit()
    db.refresh(db_node)

    logger.info(f"Added node {db_node.name} to topology {topology_id}")
    rabbitmq_publisher.publish("topology.node.added", {
        "topology_id": topology_id,
        "node_id": db_node.id,
        "node_name": db_node.name
    })

    await topology_ws.broadcast(
        topology_id,
        {
            "type": "topology.node.updated",
            "payload": {"id": db_node.id, "name": db_node.name, "action": "created"},
        },
    )
    return db_node


@app.get("/api/topologies/{topology_id}/nodes", response_model=List[NodeResponse])
async def list_nodes(topology_id: str, db: Session = Depends(get_db)):
    """List all nodes in a topology"""
    nodes = db.query(Node).filter(Node.topology_id == topology_id).all()
    return nodes


@app.get("/api/topologies/{topology_id}/nodes/{node_id}", response_model=NodeResponse)
async def get_node(topology_id: str, node_id: str, db: Session = Depends(get_db)):
    """Get a specific node"""
    node = db.query(Node).filter(
        Node.id == node_id,
        Node.topology_id == topology_id
    ).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


@app.put("/api/topologies/{topology_id}/nodes/{node_id}", response_model=NodeResponse)
async def update_node(
    topology_id: str,
    node_id: str,
    node_update: NodeUpdate,
    db: Session = Depends(get_db)
):
    """Update a node"""
    node = db.query(Node).filter(
        Node.id == node_id,
        Node.topology_id == topology_id
    ).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    if node_update.name is not None:
        node.name = node_update.name
    if node_update.x is not None:
        node.x = node_update.x
    if node_update.y is not None:
        node.y = node_update.y
    if node_update.properties is not None:
        node.properties = node_update.properties

    db.commit()
    db.refresh(node)

    logger.info(f"Updated node {node_id} in topology {topology_id}")
    rabbitmq_publisher.publish("topology.node.updated", {
        "topology_id": topology_id,
        "node_id": node_id
    })

    await topology_ws.broadcast(
        topology_id,
        {"type": "topology.node.updated", "payload": {"id": node_id, "name": node.name, "action": "updated"}},
    )
    return node


@app.delete("/api/topologies/{topology_id}/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_node(topology_id: str, node_id: str, db: Session = Depends(get_db)):
    """Delete a node from a topology"""
    node = db.query(Node).filter(
        Node.id == node_id,
        Node.topology_id == topology_id
    ).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    # Store node name before deletion for event
    node_name = node.name

    db.delete(node)
    db.commit()

    logger.info(f"Deleted node {node_id} from topology {topology_id}")
    rabbitmq_publisher.publish("topology.node.deleted", {
        "topology_id": topology_id,
        "node_id": node_id,
        "node_name": node_name  # Include node name for orchestrator
    })
    await topology_ws.broadcast(
        topology_id,
        {"type": "topology.node.updated", "payload": {"id": node_id, "name": node_name, "action": "deleted"}},
    )


# ==================== Link Endpoints ====================

@app.post("/api/topologies/{topology_id}/links", response_model=LinkResponse, status_code=status.HTTP_201_CREATED)
async def add_link(topology_id: str, link: LinkCreate, db: Session = Depends(get_db)):
    """Add a link to a topology"""
    topology = db.query(Topology).filter(Topology.id == topology_id).first()
    if not topology:
        raise HTTPException(status_code=404, detail="Topology not found")

    db_link = Link(
        id=str(uuid.uuid4()),
        topology_id=topology_id,
        source_node_id=link.source_node_id,
        target_node_id=link.target_node_id,
        source_port=link.source_port,
        target_port=link.target_port,
        bandwidth=link.bandwidth,
        delay=link.delay,
        loss=link.loss,
        max_queue_size=link.max_queue_size,
        properties=link.properties
    )
    db.add(db_link)
    topology.version += 1
    db.commit()
    db.refresh(db_link)

    logger.info(f"Added link to topology {topology_id}")
    rabbitmq_publisher.publish("topology.link.added", {
        "topology_id": topology_id,
        "link_id": db_link.id
    })

    await topology_ws.broadcast(
        topology_id,
        {
            "type": "topology.link.updated",
            "payload": {
                "id": db_link.id,
                "source": db_link.source_node_id,
                "target": db_link.target_node_id,
                "action": "created",
            },
        },
    )
    return db_link


@app.get("/api/topologies/{topology_id}/links", response_model=List[LinkResponse])
async def list_links(topology_id: str, db: Session = Depends(get_db)):
    """List all links in a topology"""
    links = db.query(Link).filter(Link.topology_id == topology_id).all()
    return links


@app.get("/api/topologies/{topology_id}/links/{link_id}", response_model=LinkResponse)
async def get_link(topology_id: str, link_id: str, db: Session = Depends(get_db)):
    """Get a specific link"""
    link = db.query(Link).filter(
        Link.id == link_id,
        Link.topology_id == topology_id
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    return link


@app.put("/api/topologies/{topology_id}/links/{link_id}", response_model=LinkResponse)
async def update_link(
    topology_id: str,
    link_id: str,
    link_update: LinkCreate,
    db: Session = Depends(get_db)
):
    """Update a link's properties"""
    link = db.query(Link).filter(
        Link.id == link_id,
        Link.topology_id == topology_id
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    # Update link properties
    if link_update.source_port is not None:
        link.source_port = link_update.source_port
    if link_update.target_port is not None:
        link.target_port = link_update.target_port
    if link_update.bandwidth is not None:
        link.bandwidth = link_update.bandwidth
    if link_update.delay is not None:
        link.delay = link_update.delay
    if link_update.loss is not None:
        link.loss = link_update.loss
    if link_update.max_queue_size is not None:
        link.max_queue_size = link_update.max_queue_size
    if link_update.properties is not None:
        link.properties = link_update.properties

    db.commit()
    db.refresh(link)

    logger.info(f"Updated link {link_id} in topology {topology_id}")
    rabbitmq_publisher.publish("topology.link.updated", {
        "topology_id": topology_id,
        "link_id": link_id
    })

    await topology_ws.broadcast(
        topology_id,
        {
            "type": "topology.link.updated",
            "payload": {
                "id": link_id,
                "source": link.source_node_id,
                "target": link.target_node_id,
                "action": "updated",
            },
        },
    )
    return link


@app.delete("/api/topologies/{topology_id}/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(topology_id: str, link_id: str, db: Session = Depends(get_db)):
    """Delete a link from a topology"""
    link = db.query(Link).filter(
        Link.id == link_id,
        Link.topology_id == topology_id
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    # Store link info before deletion for event
    source_node_id = link.source_node_id
    target_node_id = link.target_node_id

    db.delete(link)
    db.commit()

    logger.info(f"Deleted link {link_id} from topology {topology_id}")
    rabbitmq_publisher.publish("topology.link.deleted", {
        "topology_id": topology_id,
        "link_id": link_id,
        "source_node_id": source_node_id,
        "target_node_id": target_node_id
    })
    await topology_ws.broadcast(
        topology_id,
        {
            "type": "topology.link.updated",
            "payload": {"id": link_id, "source": source_node_id, "target": target_node_id, "action": "deleted"},
        },
    )


# ==================== Import/Export Endpoints ====================

@app.post("/api/topologies/import", response_model=TopologyResponse, status_code=status.HTTP_201_CREATED)
async def import_topology(
    project_id: str,
    topology_def: TopologyDefinition,
    topology_id: str | None = None,
    db: Session = Depends(get_db)
):
    """Import a topology from JSON definition"""
    if topology_id:
        topology = db.query(Topology).filter(Topology.id == topology_id).first()
        if not topology:
            raise HTTPException(status_code=404, detail="Topology not found")
        if topology.project_id != project_id:
            raise HTTPException(status_code=400, detail="Topology does not belong to the provided project_id")

        updated = _replace_topology_contents_from_definition(db=db, topology=topology, topology_def=topology_def)
        logger.info(f"Imported topology definition into existing topology via POST import: {topology_id}")
        rabbitmq_publisher.publish("topology.updated", {"topology_id": topology_id, "action": "imported"})
        await topology_ws.broadcast(
            topology_id,
            {"type": "topology.updated", "payload": {"topology_id": topology_id, "action": "imported"}},
        )
        return updated

    # Create topology from definition
    topology_create = TopologyCreate(
        project_id=project_id,
        name=topology_def.name,
        description=topology_def.description,
        topology_metadata=topology_def.metadata,
        nodes=[NodeCreate(**node) for node in topology_def.nodes],
        links=[LinkCreate(**link) for link in topology_def.links],
        controllers=[ControllerCreate(**ctrl) for ctrl in topology_def.controllers]
    )

    return await create_topology(topology_create, db)


@app.put("/api/topologies/{topology_id}/import", response_model=TopologyResponse, status_code=status.HTTP_200_OK)
async def import_topology_into_existing(
    topology_id: str,
    topology_def: TopologyDefinition,
    db: Session = Depends(get_db),
):
    """Import a topology definition and overwrite an existing topology (keeps the same topology_id)."""
    topology = db.query(Topology).filter(Topology.id == topology_id).first()
    if not topology:
        raise HTTPException(status_code=404, detail="Topology not found")

    updated = _replace_topology_contents_from_definition(db=db, topology=topology, topology_def=topology_def)

    logger.info(f"Imported topology definition into existing topology: {topology_id}")
    rabbitmq_publisher.publish("topology.updated", {"topology_id": topology_id, "action": "imported"})
    await topology_ws.broadcast(
        topology_id,
        {"type": "topology.updated", "payload": {"topology_id": topology_id, "action": "imported"}},
    )
    return updated


class TopologyImportAndStartRequest(BaseModel):
    project_id: str
    topology_id: str | None = None
    topology: TopologyDefinition
    options: Dict[str, Any] = Field(default_factory=dict)
    network_config: NetworkConfigurationDocument | None = None
    save_network_config: bool = True
    apply_network_config: bool = False


@app.post("/api/topologies/import-and-start")
async def import_topology_and_start(payload: TopologyImportAndStartRequest, db: Session = Depends(get_db)):
    """
    Import a topology definition (JSON) and immediately start an emulation for it.
    Optionally persists a network configuration and applies it after start.
    """
    topology_def = payload.topology

    if payload.topology_id:
        topology = db.query(Topology).filter(Topology.id == payload.topology_id).first()
        if not topology:
            raise HTTPException(status_code=404, detail="Topology not found")
        if topology.project_id != payload.project_id:
            raise HTTPException(status_code=400, detail="Topology does not belong to the provided project_id")
        topology = _replace_topology_contents_from_definition(db=db, topology=topology, topology_def=topology_def)
        rabbitmq_publisher.publish(
            "topology.updated",
            {"topology_id": topology.id, "action": "imported"},
        )
        await topology_ws.broadcast(
            topology.id,
            {"type": "topology.updated", "payload": {"topology_id": topology.id, "action": "imported"}},
        )
    else:
        topology_create = TopologyCreate(
            project_id=payload.project_id,
            name=topology_def.name,
            description=topology_def.description,
            topology_metadata=topology_def.metadata,
            nodes=[NodeCreate(**node) for node in topology_def.nodes],
            links=[LinkCreate(**link) for link in topology_def.links],
            controllers=[ControllerCreate(**ctrl) for ctrl in topology_def.controllers],
        )

        topology = await create_topology(topology_create, db)

    orchestrator_url = os.getenv("ORCHESTRATOR_SERVICE_URL", "http://orchestrator-service:8002")
    async with httpx.AsyncClient(timeout=90.0) as client:
        start_res = await client.post(
            f"{orchestrator_url}/api/emulation/start",
            json={"topology_id": topology.id, "options": payload.options or {}},
        )
    if start_res.status_code != 200:
        detail = None
        try:
            body = start_res.json() if start_res.content else {}
            if isinstance(body, dict):
                detail = body.get("detail") or body.get("message")
        except Exception:
            detail = None
        if not detail and start_res.text:
            detail = start_res.text.strip()
        raise HTTPException(
            status_code=502,
            detail=detail or f"Failed to start emulation: HTTP {start_res.status_code}",
        )
    start_data = start_res.json()

    config_saved = None
    if payload.network_config and payload.save_network_config:
        cfg_dict = payload.network_config.model_dump()
        cfg_dict["topology_id"] = topology.id
        version = _get_next_network_config_version(db, topology.id)
        item = NetworkConfiguration(
            id=str(uuid.uuid4()),
            topology_id=topology.id,
            name=payload.network_config.name or "Network Configuration",
            description=payload.network_config.description,
            version=version,
            config=cfg_dict,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        config_saved = {"config_id": item.id, "version": item.version}

    applied = None
    if payload.network_config and payload.apply_network_config:
        async with httpx.AsyncClient(timeout=120.0) as client:
            apply_res = await client.post(
                f"{orchestrator_url}/api/emulation/network-config/apply",
                json={"topology_id": topology.id, "config": payload.network_config.model_dump(), "dry_run": False},
            )
        applied = {"status_code": apply_res.status_code, "body": apply_res.json() if apply_res.content else None}

    return {
        "topology": topology,
        "emulation": start_data,
        "network_config_saved": config_saved,
        "network_config_applied": applied,
    }


@app.get("/api/topologies/{topology_id}/export", response_model=TopologyDefinition)
async def export_topology(topology_id: str, db: Session = Depends(get_db)):
    """Export a topology to JSON definition"""
    topology = db.query(Topology).filter(Topology.id == topology_id).first()
    if not topology:
        raise HTTPException(status_code=404, detail="Topology not found")

    # Build complete topology definition
    topology_def = TopologyDefinition(
        name=topology.name,
        description=topology.description or "",
        version="1.0",
        metadata=topology.topology_metadata,
        nodes=[
            {
                "name": node.name,
                "device_type": node.device_type.value,
                "x": node.x,
                "y": node.y,
                "properties": node.properties
            }
            for node in topology.nodes
        ],
        links=[
            {
                "source_node_id": link.source_node_id,
                "target_node_id": link.target_node_id,
                "source_port": link.source_port,
                "target_port": link.target_port,
                "bandwidth": link.bandwidth,
                "delay": link.delay,
                "loss": link.loss,
                "max_queue_size": link.max_queue_size,
                "properties": link.properties
            }
            for link in topology.links
        ],
        controllers=[
            {
                "name": ctrl.name,
                "controller_type": ctrl.controller_type,
                "ip": ctrl.ip,
                "port": ctrl.port,
                "properties": ctrl.properties
            }
            for ctrl in topology.controllers
        ]
    )

    return topology_def


# ==================== Network Configuration Endpoints ====================

def _get_next_network_config_version(db: Session, topology_id: str) -> int:
    latest = (
        db.query(NetworkConfiguration)
        .filter(NetworkConfiguration.topology_id == topology_id)
        .order_by(NetworkConfiguration.version.desc())
        .first()
    )
    return 1 if not latest else int(latest.version) + 1


@app.get("/api/network-configs/{topology_id}/versions", response_model=List[NetworkConfigListItem])
async def list_network_configs(topology_id: str, db: Session = Depends(get_db)):
    items = (
        db.query(NetworkConfiguration)
        .filter(NetworkConfiguration.topology_id == topology_id)
        .order_by(NetworkConfiguration.version.desc())
        .all()
    )
    return items


@app.get("/api/network-configs/{topology_id}", response_model=NetworkConfigResponse)
async def get_latest_network_config(topology_id: str, db: Session = Depends(get_db)):
    item = (
        db.query(NetworkConfiguration)
        .filter(NetworkConfiguration.topology_id == topology_id)
        .order_by(NetworkConfiguration.version.desc())
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="No network configuration found")
    return item


@app.get("/api/network-configs/{topology_id}/export", response_model=NetworkConfigurationDocument)
async def export_latest_network_config(topology_id: str, db: Session = Depends(get_db)):
    item = (
        db.query(NetworkConfiguration)
        .filter(NetworkConfiguration.topology_id == topology_id)
        .order_by(NetworkConfiguration.version.desc())
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="No network configuration found")
    return item.config


@app.post("/api/network-configs/{topology_id}", response_model=NetworkConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_network_config(topology_id: str, payload: NetworkConfigCreateRequest, db: Session = Depends(get_db)):
    topology = db.query(Topology).filter(Topology.id == topology_id).first()
    if not topology:
        raise HTTPException(status_code=404, detail="Topology not found")

    config_dict = payload.config.model_dump()
    config_dict["topology_id"] = topology_id

    version = _get_next_network_config_version(db, topology_id)
    item = NetworkConfiguration(
        id=str(uuid.uuid4()),
        topology_id=topology_id,
        name=payload.name or payload.config.name or "Network Configuration",
        description=payload.description or payload.config.description,
        version=version,
        config=config_dict,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    rabbitmq_publisher.publish("network.config.created", {
        "topology_id": topology_id,
        "config_id": item.id,
        "version": item.version,
    })
    return item


@app.get("/api/network-configs/{topology_id}/template", response_model=NetworkConfigurationDocument)
async def network_config_template(topology_id: str, db: Session = Depends(get_db)):
    topology = db.query(Topology).filter(Topology.id == topology_id).first()
    if not topology:
        raise HTTPException(status_code=404, detail="Topology not found")

    devices = []
    for node in topology.nodes:
        kind = getattr(node.device_type, "value", str(node.device_type))
        sysctls = {}
        if str(kind).lower() == "router":
            sysctls["net.ipv4.ip_forward"] = "1"
        devices.append(
            {
                "name": node.name,
                "kind": kind,
                "interfaces": [
                    {
                        "name": None,
                        "addresses": [],
                        "mac": None,
                        "mtu": None,
                        "up": True,
                        "reset_addresses": True,
                    }
                ],
                "default_gateway": None,
                "default_gateway6": None,
                "routes": [],
                "dns_servers": [],
                "sysctls": sysctls,
                "commands": [],
            }
        )

    return NetworkConfigurationDocument(
        topology_id=topology_id,
        name=f"{topology.name} · Network Config",
        devices=devices,
        metadata={"generated_from": "topology-service"},
    )


# ==================== Health Check ====================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "topology-service"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
